"""
Service for logging A2A tasks and events to the database.
"""

import copy
import uuid
from typing import Any, Callable, Dict

from a2a.types import Task as A2ATask
from solace_ai_connector.common.log import log
from sqlalchemy.orm import Session as DBSession

from ....common import a2a
from ..repository.entities import Task, TaskEvent
from ..repository.task_repository import TaskRepository
from ..shared import now_epoch_ms


class TaskLoggerService:
    """Service for logging A2A tasks and events to the database."""

    def __init__(
        self, session_factory: Callable[[], DBSession] | None, config: Dict[str, Any]
    ):
        self.session_factory = session_factory
        self.config = config
        self.log_identifier = "[TaskLoggerService]"
        log.info(f"{self.log_identifier} Initialized.")

    def log_event(self, event_data: Dict[str, Any]):
        """
        Parses a raw A2A message and logs it as a task event.
        Creates or updates the master task record as needed.
        """
        if not self.config.get("enabled", False):
            return

        if not self.session_factory:
            log.warning(
                f"{self.log_identifier} Task logging is enabled but no database is configured. Skipping event."
            )
            return

        topic = event_data.get("topic")
        payload = event_data.get("payload")
        user_properties = event_data.get("user_properties", {})

        if not topic or not payload:
            log.warning(
                f"{self.log_identifier} Received event with missing topic or payload."
            )
            return

        # Basic filtering
        if "/discovery/agentcards" in topic:
            return

        db = self.session_factory()
        try:
            repo = TaskRepository(db)

            # Infer details from the message
            direction, task_id, user_id = self._infer_event_details(
                topic, payload, user_properties
            )

            if not task_id:
                log.debug(
                    f"{self.log_identifier} Could not determine task_id for event on topic {topic}. Skipping."
                )
                return

            # Check if we should log this event type
            if not self._should_log_event(topic, payload):
                log.debug(
                    f"{self.log_identifier} Event on topic {topic} is configured to be skipped."
                )
                return

            # Sanitize payload before storing
            sanitized_payload = self._sanitize_payload(payload)

            # Check for existing task or create a new one
            task = repo.find_by_id(task_id)
            if not task:
                if direction == "request":
                    initial_text = self._extract_initial_text(payload)
                    new_task = Task(
                        id=task_id,
                        user_id=user_id or "unknown",
                        start_time=now_epoch_ms(),
                        initial_request_text=initial_text[:1024]
                        if initial_text
                        else None,  # Truncate
                    )
                    repo.save_task(new_task)
                    log.info(
                        f"{self.log_identifier} Created new task record for ID: {task_id}"
                    )
                else:
                    # We received an event for a task we haven't seen the start of.
                    # This can happen if the logger starts mid-conversation. Create a placeholder.
                    placeholder_task = Task(
                        id=task_id,
                        user_id=user_id or "unknown",
                        start_time=now_epoch_ms(),
                        initial_request_text="[Task started before logger was active]",
                    )
                    repo.save_task(placeholder_task)
                    log.info(
                        f"{self.log_identifier} Created placeholder task record for ID: {task_id}"
                    )

            # Create and save the event
            task_event = TaskEvent(
                id=str(uuid.uuid4()),
                task_id=task_id,
                user_id=user_id,
                created_time=now_epoch_ms(),
                topic=topic,
                direction=direction,
                payload=sanitized_payload,
            )
            repo.save_event(task_event)

            # If it's a final event, update the master task record
            final_status = self._get_final_status(payload)
            if final_status:
                task_to_update = repo.find_by_id(task_id)
                if task_to_update:
                    task_to_update.end_time = now_epoch_ms()
                    task_to_update.status = final_status
                    repo.save_task(task_to_update)
                    log.info(
                        f"{self.log_identifier} Finalized task record for ID: {task_id} with status: {final_status}"
                    )
            db.commit()
        except Exception as e:
            log.exception(
                f"{self.log_identifier} Error logging event on topic {topic}: {e}"
            )
            db.rollback()
        finally:
            db.close()

    def _infer_event_details(
        self, topic: str, payload: Dict, user_props: Dict
    ) -> tuple[str, str | None, str | None]:
        """Infers direction, task_id, and user_id from message details."""
        direction = "unknown"
        task_id = None
        user_id = user_props.get("userId")

        if "request" in topic:
            direction = "request"
            task_id = payload.get("id")
        elif "response" in topic or "status" in topic:
            direction = "response" if "response" in topic else "status_update"
            task_id = self._extract_task_id_from_response(payload)

        if not user_id:
            user_config = user_props.get("a2aUserConfig", {})
            if isinstance(user_config, dict):
                user_profile = user_config.get("user_profile", {})
                if isinstance(user_profile, dict):
                    user_id = user_profile.get("id")

        return direction, str(task_id) if task_id else None, user_id

    def _extract_task_id_from_response(self, payload: Dict) -> str | None:
        """Extracts task ID from a JSON-RPC response payload."""
        if "result" in payload and isinstance(payload["result"], dict):
            result = payload["result"]
            return result.get("task_id") or result.get("id")
        if "error" in payload and isinstance(payload["error"], dict):
            error_data = payload["error"].get("data", {})
            if isinstance(error_data, dict):
                return error_data.get("taskId")
        return None

    def _extract_initial_text(self, payload: Dict) -> str | None:
        """Extracts the initial text from a send message request."""
        try:
            message = a2a.get_message_from_send_request(payload)
            if message:
                return a2a.get_text_from_message(message)
        except Exception:
            return None
        return None

    def _get_final_status(self, payload: Dict) -> str | None:
        """Checks if a payload represents a final task status and returns the state."""
        try:
            if "result" in payload and isinstance(payload["result"], dict):
                result = payload["result"]
                # Check if it's a final Task object
                if "status" in result and "state" in result["status"]:
                    task = A2ATask.model_validate(result)
                    return task.status.state.value
            elif "error" in payload:
                return "failed"
        except Exception:
            return None
        return None

    def _should_log_event(self, topic: str, payload: Dict) -> bool:
        """Determines if an event should be logged based on configuration."""
        if not self.config.get("log_status_updates", True):
            if "status" in topic:
                return False
        if not self.config.get("log_artifact_events", True):
            if (
                "result" in payload
                and isinstance(payload["result"], dict)
                and payload["result"].get("kind") == "artifact-update"
            ):
                return False
        return True

    def _sanitize_payload(self, payload: Dict) -> Dict:
        """Strips or truncates file content from payload based on configuration."""
        new_payload = copy.deepcopy(payload)

        def walk_and_sanitize(node):
            if isinstance(node, dict):
                for key, value in list(node.items()):
                    if key == "parts" and isinstance(value, list):
                        new_parts = []
                        for part in value:
                            if isinstance(part, dict) and "file" in part:
                                if not self.config.get("log_file_parts", True):
                                    continue  # Skip this part entirely

                                file_dict = part.get("file")
                                if (
                                    isinstance(file_dict, dict)
                                    and "bytes" in file_dict
                                ):
                                    max_bytes = self.config.get(
                                        "max_file_part_size_bytes", 102400
                                    )
                                    file_bytes_b64 = file_dict.get("bytes")
                                    if isinstance(file_bytes_b64, str):
                                        if (len(file_bytes_b64) * 3 / 4) > max_bytes:
                                            file_dict[
                                                "bytes"
                                            ] = f"[Content stripped, size > {max_bytes} bytes]"
                                new_parts.append(part)
                            else:
                                walk_and_sanitize(part)
                                new_parts.append(part)
                        node["parts"] = new_parts
                    else:
                        walk_and_sanitize(value)
            elif isinstance(node, list):
                for item in node:
                    walk_and_sanitize(item)

        walk_and_sanitize(new_payload)
        return new_payload
