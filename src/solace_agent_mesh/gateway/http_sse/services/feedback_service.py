"""
Service layer for handling user feedback on chat messages.
"""

import uuid
from typing import TYPE_CHECKING

from solace_ai_connector.common.log import log

from ..repository.entities import Feedback
from ..repository.interfaces import IFeedbackRepository
from ..shared import now_epoch_ms

# The FeedbackPayload is defined in the router, this creates a forward reference
# which is resolved at runtime.
if TYPE_CHECKING:
    from ..routers.feedback import FeedbackPayload


class FeedbackService:
    """Handles the business logic for processing user feedback."""

    def __init__(self, feedback_repository: IFeedbackRepository | None = None):
        """Initializes the FeedbackService."""
        self.repo = feedback_repository
        if self.repo:
            log.info("FeedbackService initialized with database persistence.")
        else:
            log.info(
                "FeedbackService initialized without database persistence (logging only)."
            )

    async def process_feedback(self, payload: "FeedbackPayload", user_id: str):
        """
        Processes and stores the feedback. If a repository is configured,
        it saves to the database. Otherwise, it logs the feedback.
        """
        if not self.repo:
            log.warning(
                "Feedback received but no database repository is configured. "
                "Logging feedback only. Payload: %s",
                payload.model_dump_json(by_alias=True),
            )
            return

        # The payload will be updated to include task_id in a later phase.
        task_id = getattr(payload, "task_id", None)
        if not task_id:
            log.error(
                "Feedback payload is missing 'task_id'. Cannot save to database. Payload: %s",
                payload.model_dump_json(by_alias=True),
            )
            return

        feedback_entity = Feedback(
            id=str(uuid.uuid4()),
            session_id=payload.session_id,
            task_id=task_id,
            user_id=user_id,
            rating=payload.feedback_type,
            comment=payload.feedback_text,
            created_time=now_epoch_ms(),
        )

        try:
            self.repo.save(feedback_entity)
            log.info(
                "Feedback from user '%s' for task '%s' saved to database.",
                user_id,
                task_id,
            )
        except Exception as e:
            log.exception(
                "Failed to save feedback for user '%s' to database: %s", user_id, e
            )
