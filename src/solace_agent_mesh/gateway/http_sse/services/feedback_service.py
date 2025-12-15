"""
Service layer for handling user feedback on chat messages.
"""

import json
import logging
import uuid
from typing import TYPE_CHECKING, Callable

from sqlalchemy.orm import Session as DBSession

from ..repository.entities import Feedback
from ..repository.feedback_repository import FeedbackRepository
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from ..utils.stim_utils import create_stim_from_task_data

# The FeedbackPayload is defined in the router, this creates a forward reference
# which is resolved at runtime.
if TYPE_CHECKING:
    from ..routers.feedback import FeedbackPayload
    from ..component import WebUIBackendComponent
    from ..repository.interfaces import ITaskRepository

log = logging.getLogger(__name__)

class FeedbackService:
    """Handles the business logic for processing user feedback."""

    def __init__(
        self,
        session_factory: Callable[[], DBSession] | None,
        component: "WebUIBackendComponent",
        task_repo: "ITaskRepository",
    ):
        """Initializes the FeedbackService."""
        self.session_factory = session_factory
        self.component = component
        self.task_repo = task_repo
        if self.session_factory:
            log.info("FeedbackService initialized with database persistence.")
        else:
            log.info(
                "FeedbackService initialized without database persistence (logging only)."
            )

    async def process_feedback(self, payload: "FeedbackPayload", user_id: str):
        """
        Processes and stores the feedback. If a repository is configured,
        it saves to the database. Otherwise, it logs the feedback.
        Also publishes feedback to a Solace topic if configured.
        Additionally updates the corresponding task's metadata with the feedback.
        """
        if self.session_factory:
            task_id = getattr(payload, "task_id", None)
            if not task_id:
                log.error(
                    "Feedback payload is missing 'task_id'. Cannot save to database. Payload: %s",
                    payload.model_dump_json(by_alias=True),
                )
                # We can still try to publish the event without saving to DB
            else:
                feedback_entity = Feedback(
                    id=str(uuid.uuid4()),
                    session_id=payload.session_id,
                    task_id=task_id,
                    user_id=user_id,
                    rating=payload.feedback_type,
                    comment=payload.feedback_text,
                    created_time=now_epoch_ms(),
                )

                db = self.session_factory()
                try:
                    repo = FeedbackRepository()
                    repo.save(db, feedback_entity)
                    db.commit()
                    log.info(
                        "Feedback from user '%s' for task '%s' saved to database.",
                        user_id,
                        task_id,
                    )
                except Exception as e:
                    log.exception(
                        "Failed to save feedback for user '%s' to database: %s",
                        user_id,
                        e,
                    )
                    db.rollback()
                finally:
                    db.close()

                # Update task metadata with feedback
                self._update_task_metadata_with_feedback(
                    task_id, user_id, payload.feedback_type, payload.feedback_text
                )
        else:
            log.warning(
                "Feedback received but no database repository is configured. "
                "Logging feedback only. Payload: %s",
                payload.model_dump_json(by_alias=True),
            )

        # --- New event publishing logic ---
        try:
            await self._publish_feedback_event(payload, user_id)
        except Exception as e:
            log.error(
                "Failed to publish feedback event for user '%s': %s", user_id, e
            )
            # Do not re-raise, as the primary operation (DB save) may have succeeded.

    def _update_task_metadata_with_feedback(
        self, task_id: str, user_id: str, feedback_type: str, feedback_text: str | None
    ):
        """
        Update the task's metadata with feedback information.
        
        Args:
            task_id: The task ID to update
            user_id: The user ID who submitted feedback
            feedback_type: Type of feedback ("up" or "down")
            feedback_text: Optional feedback text
        """
        if not self.session_factory:
            log.debug(
                "No session factory available, skipping task metadata update for task %s",
                task_id
            )
            return

        db = self.session_factory()
        try:
            from ..repository.chat_task_repository import ChatTaskRepository

            task_repo = ChatTaskRepository()
            task = task_repo.find_by_id(db, task_id, user_id)

            if task:
                # Update feedback in task metadata
                task.add_feedback(feedback_type, feedback_text)
                task_repo.save(db, task)
                db.commit()
                log.info(
                    "Updated task metadata with feedback for task '%s' by user '%s'",
                    task_id,
                    user_id
                )
            else:
                log.warning(
                    "Task '%s' not found for user '%s', cannot update task metadata with feedback",
                    task_id,
                    user_id
                )
        except Exception as e:
            log.warning(
                "Failed to update task metadata with feedback for task '%s': %s",
                task_id,
                e
            )
            db.rollback()
            # Don't re-raise - feedback was already saved to feedback table
        finally:
            db.close()

    async def _publish_feedback_event(self, payload: "FeedbackPayload", user_id: str):
        """Publishes the feedback as an event to the message broker if configured."""
        log_id = f"[FeedbackPublisher:{payload.task_id}]"
        config = self.component.get_config("feedback_publishing", {})

        if not config.get("enabled", False):
            log.debug("%s Feedback publishing is disabled. Skipping.", log_id)
            return

        # Construct base payload
        event_payload = {
            "feedback": {
                "task_id": payload.task_id,
                "session_id": payload.session_id,
                "feedback_type": payload.feedback_type,
                "feedback_text": payload.feedback_text,
                "user_id": user_id,
            }
        }

        include_task_info = config.get("include_task_info", "none")
        task_summary_data = None

        if include_task_info == "summary":
            log.debug("%s Including task summary.", log_id)
            db = self.session_factory()
            try:
                task_summary_data = self.task_repo.find_by_id(db, payload.task_id)
                if task_summary_data:
                    event_payload["task_summary"] = task_summary_data.model_dump()
            finally:
                db.close()

        elif include_task_info == "stim":
            log.debug("%s Including task stim data.", log_id)
            db = self.session_factory()
            try:
                task_with_events = self.task_repo.find_by_id_with_events(db, payload.task_id)
                if task_with_events:
                    task, events = task_with_events
                    stim_data = create_stim_from_task_data(task, events)
                    event_payload["task_stim_data"] = stim_data

                    # Check payload size
                    max_size = config.get("max_payload_size_bytes", 9000000)
                    try:
                        payload_bytes = json.dumps(event_payload).encode("utf-8")
                        if len(payload_bytes) > max_size:
                            log.warning(
                                "%s Stim payload size (%d bytes) exceeds limit (%d bytes). Falling back to summary.",
                                log_id,
                                len(payload_bytes),
                                max_size,
                            )
                            # Fallback to summary
                            del event_payload["task_stim_data"]
                            task_summary_data = self.task_repo.find_by_id(db, payload.task_id)
                            if task_summary_data:
                                event_payload[
                                    "task_summary"
                                ] = task_summary_data.model_dump()
                            event_payload["truncation_details"] = {
                                "strategy": "fallback_to_summary",
                                "reason": "payload_too_large",
                            }
                    except Exception as e:
                        log.error("%s Error checking payload size: %s", log_id, e)
                        # If we can't check size, better to not send a potentially huge message
                        if "task_stim_data" in event_payload:
                            del event_payload["task_stim_data"]
            finally:
                db.close()

        # Publish the event
        topic = config.get("topic", "sam/feedback/v1")
        try:
            log.info("%s Publishing feedback event to topic '%s'", log_id, topic)
            self.component.publish_a2a(topic, event_payload)
        except Exception as e:
            log.error(
                "%s Failed to publish feedback event to topic '%s': %s",
                log_id,
                topic,
                e,
            )
            # Don't re-raise, this is a non-critical operation.
