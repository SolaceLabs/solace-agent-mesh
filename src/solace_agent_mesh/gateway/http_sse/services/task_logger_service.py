"""
Service for logging A2A tasks and events to the database.
"""

import copy
import logging
import uuid
from typing import Any, Callable, Dict, Union

from a2a.types import (
    A2ARequest,
    JSONRPCError,
    JSONRPCResponse,
    Task as A2ATask,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
from sqlalchemy.orm import Session as DBSession

from ....common import a2a
from ..repository.entities import Task, TaskEvent
from ..repository.task_repository import TaskRepository
from ..shared import now_epoch_ms

log = logging.getLogger(__name__)

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

        if "discovery" in topic:
            # Ignore discovery messages
            return

        # Parse the event into a Pydantic model first.
        parsed_event = self._parse_a2a_event(topic, payload)
        if parsed_event is None:
            # Parsing failed or event should be ignored.
            return

        db = self.session_factory()
        try:
            repo = TaskRepository()

            # Infer details from the parsed event
            direction, task_id, user_id = self._infer_event_details(
                topic, parsed_event, user_properties
            )

            if not task_id:
                log.debug(
                    f"{self.log_identifier} Could not determine task_id for event on topic {topic}. Skipping."
                )
                return

            # Check if we should log this event type
            if not self._should_log_event(topic, parsed_event):
                log.debug(
                    f"{self.log_identifier} Event on topic {topic} is configured to be skipped."
                )
                return

            # Sanitize the original raw payload before storing
            sanitized_payload = self._sanitize_payload(payload)

            # Check for existing task or create a new one
            task = repo.find_by_id(db, task_id)
            if not task:
                if direction == "request":
                    initial_text = self._extract_initial_text(parsed_event)
                    new_task = Task(
                        id=task_id,
                        user_id=user_id or "unknown",
                        start_time=now_epoch_ms(),
                        initial_request_text=(
                            initial_text[:1024] if initial_text else None
                        ),  # Truncate
                    )
                    repo.save_task(db, new_task)
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
                    repo.save_task(db, placeholder_task)
                    log.info(
                        f"{self.log_identifier} Created placeholder task record for ID: {task_id}"
                    )

            # Create and save the event using the sanitized raw payload
            task_event = TaskEvent(
                id=str(uuid.uuid4()),
                task_id=task_id,
                user_id=user_id,
                created_time=now_epoch_ms(),
                topic=topic,
                direction=direction,
                payload=sanitized_payload,
            )
            repo.save_event(db, task_event)

            # If it's a final event, update the master task record
            final_status = self._get_final_status(parsed_event)
            if final_status:
                task_to_update = repo.find_by_id(db, task_id)
                if task_to_update:
                    task_to_update.end_time = now_epoch_ms()
                    task_to_update.status = final_status
                    
                    # Extract and store token usage if present
                    if isinstance(parsed_event, A2ATask) and parsed_event.metadata:
                        token_usage = parsed_event.metadata.get("token_usage")
                        if token_usage and isinstance(token_usage, dict):
                            task_to_update.total_input_tokens = token_usage.get("total_input_tokens")
                            task_to_update.total_output_tokens = token_usage.get("total_output_tokens")
                            task_to_update.total_cached_input_tokens = token_usage.get("total_cached_input_tokens")
                            task_to_update.token_usage_details = token_usage
                            log.info(
                                f"{self.log_identifier} Stored token usage for task {task_id}: "
                                f"input={token_usage.get('total_input_tokens')}, "
                                f"output={token_usage.get('total_output_tokens')}, "
                                f"cached={token_usage.get('total_cached_input_tokens')}"
                            )

                    repo.save_task(db, task_to_update)
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

    def _parse_a2a_event(self, topic: str, payload: dict) -> Union[
        A2ARequest,
        A2ATask,
        TaskStatusUpdateEvent,
        TaskArtifactUpdateEvent,
        JSONRPCError,
        None,
    ]:
        """
        Safely parses a raw A2A message payload into a Pydantic model.
        Returns the parsed model or None if parsing fails or is not applicable.
        """
        # Ignore discovery messages
        if "/discovery/agentcards" in topic:
            return None

        try:
            # Check if it's a response (has 'result' or 'error')
            if "result" in payload or "error" in payload:
                rpc_response = JSONRPCResponse.model_validate(payload)
                error = a2a.get_response_error(rpc_response)
                if error:
                    return error
                result = a2a.get_response_result(rpc_response)
                if result:
                    # The result is already a parsed Pydantic model
                    return result
            # Check if it's a request
            elif "method" in payload:
                return A2ARequest.model_validate(payload)

            log.warning(
                f"{self.log_identifier} Payload for topic '{topic}' is not a recognizable JSON-RPC request or response. Payload: {payload}"
            )
            return None

        except Exception as e:
            log.error(
                f"{self.log_identifier} Failed to parse A2A event for topic '{topic}': {e}. Payload: {payload}"
            )
            return None

    def _infer_event_details(
        self, topic: str, parsed_event: Any, user_props: Dict | None
    ) -> tuple[str, str | None, str | None]:
        """Infers direction, task_id, and user_id from a parsed A2A event."""
        direction = "unknown"
        task_id = None
        # Ensure user_props is a dict, not None
        user_props = user_props or {}
        user_id = user_props.get("userId")

        if isinstance(parsed_event, A2ARequest):
            direction = "request"
            task_id = a2a.get_request_id(parsed_event)
        elif isinstance(
            parsed_event, (A2ATask, TaskStatusUpdateEvent, TaskArtifactUpdateEvent)
        ):
            direction = "response" if isinstance(parsed_event, A2ATask) else "status"
            task_id = getattr(parsed_event, "task_id", None) or getattr(
                parsed_event, "id", None
            )
        elif isinstance(parsed_event, JSONRPCError):
            direction = "error"
            if isinstance(parsed_event.data, dict):
                task_id = parsed_event.data.get("taskId")

        if not user_id:
            user_config = user_props.get("a2aUserConfig") or user_props.get("a2a_user_config")
            if isinstance(user_config, dict):
                user_profile = user_config.get("user_profile", {})
                if isinstance(user_profile, dict):
                    user_id = user_profile.get("id")

        return direction, str(task_id) if task_id else None, user_id

    def _extract_initial_text(self, parsed_event: Any) -> str | None:
        """Extracts the initial text from a send message request."""
        try:
            if isinstance(parsed_event, A2ARequest):
                message = a2a.get_message_from_send_request(parsed_event)
                if message:
                    return a2a.get_text_from_message(message)
        except Exception:
            return None
        return None

    def _get_final_status(self, parsed_event: Any) -> str | None:
        """Checks if a parsed event represents a final task status and returns the state."""
        if isinstance(parsed_event, A2ATask):
            return parsed_event.status.state.value
        elif isinstance(parsed_event, JSONRPCError):
            return "failed"
        return None

    def _should_log_event(self, topic: str, parsed_event: Any) -> bool:
        """Determines if an event should be logged based on configuration."""
        if not self.config.get("log_status_updates", True):
            if "status" in topic:
                return False
        if not self.config.get("log_artifact_events", True):
            if isinstance(parsed_event, TaskArtifactUpdateEvent):
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
                                if isinstance(file_dict, dict) and "bytes" in file_dict:
                                    max_bytes = self.config.get(
                                        "max_file_part_size_bytes", 102400
                                    )
                                    file_bytes_b64 = file_dict.get("bytes")
                                    if isinstance(file_bytes_b64, str):
                                        if (len(file_bytes_b64) * 3 / 4) > max_bytes:
                                            file_dict["bytes"] = (
                                                f"[Content stripped, size > {max_bytes} bytes]"
                                            )
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
