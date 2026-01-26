"""
Service for logging A2A tasks and events to the database.
"""

import copy
import json
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
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

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
                # Extract parent_task_id and background execution metadata
                parent_task_id = None
                background_execution_enabled = False
                max_execution_time_ms = None
                
                log.info(
                    f"{self.log_identifier} Creating new task {task_id}: direction={direction}, "
                    f"parsed_event_type={type(parsed_event).__name__}"
                )
                
                if direction == "request" and isinstance(parsed_event, A2ARequest):
                    message = a2a.get_message_from_send_request(parsed_event)
                    log.info(f"{self.log_identifier} Message extracted: {message is not None}")
                    
                    if message:
                        log.info(f"{self.log_identifier} Message metadata: {message.metadata}")
                        
                        if message.metadata:
                            parent_task_id = message.metadata.get("parentTaskId")
                            background_execution_enabled = message.metadata.get("backgroundExecutionEnabled", False)
                            # Default to 1 hour (3600000ms) if background execution is enabled but no timeout specified
                            max_execution_time_ms = message.metadata.get("maxExecutionTimeMs")
                            if background_execution_enabled and max_execution_time_ms is None:
                                max_execution_time_ms = 3600000  # 1 hour default
                        else:
                            log.warning(
                                f"{self.log_identifier} Message has no metadata for task {task_id}"
                            )
                    else:
                        log.warning(
                            f"{self.log_identifier} Could not extract message from request for task {task_id}"
                        )

                if direction == "request":
                    initial_text = self._extract_initial_text(parsed_event)
                    current_time = now_epoch_ms()
                    new_task = Task(
                        id=task_id,
                        user_id=user_id or "unknown",
                        parent_task_id=parent_task_id,
                        start_time=current_time,
                        initial_request_text=(
                            initial_text[:1024] if initial_text else None
                        ),  # Truncate
                        execution_mode="background" if background_execution_enabled else "foreground",
                        last_activity_time=current_time,
                        background_execution_enabled=background_execution_enabled,
                        max_execution_time_ms=max_execution_time_ms,
                    )
                    repo.save_task(db, new_task)
                    log.info(
                        f"{self.log_identifier} Created new task record for ID: {task_id}"
                        + (f" with parent: {parent_task_id}" if parent_task_id else "")
                        + (f" (background execution enabled)" if background_execution_enabled else "")
                    )
                else:
                    # We received an event for a task we haven't seen the start of.
                    # This can happen if the logger starts mid-conversation. Create a placeholder.
                    current_time = now_epoch_ms()
                    placeholder_task = Task(
                        id=task_id,
                        user_id=user_id or "unknown",
                        parent_task_id=parent_task_id,
                        start_time=current_time,
                        initial_request_text="[Task started before logger was active]",
                        execution_mode="foreground",
                        last_activity_time=current_time,
                        background_execution_enabled=False,
                    )
                    repo.save_task(db, placeholder_task)
                    log.info(
                        f"{self.log_identifier} Created placeholder task record for ID: {task_id}"
                    )
            else:
                # Update last activity time for existing task
                task.last_activity_time = now_epoch_ms()
                repo.save_task(db, task)

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
                    current_time = now_epoch_ms()
                    task_to_update.end_time = current_time
                    task_to_update.status = final_status
                    task_to_update.last_activity_time = current_time
                    
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
                    
                    # For background tasks, save chat messages when task completes
                    # Only save for top-level tasks (no parent_task_id) to avoid duplicates
                    # Sub-tasks (delegated by orchestrator) have parent_task_id set and contain system prompts
                    if task_to_update.background_execution_enabled and not task_to_update.parent_task_id:
                        self._save_chat_messages_for_background_task(db, task_id, task_to_update, repo)
                        
                        # Note: The frontend will detect task completion through:
                        # 1. SSE final_response event (if connected to that task)
                        # 2. Session list refresh triggered by the ChatProvider
                        # 3. Database status check when loading sessions
                        log.info(
                            f"{self.log_identifier} Background task {task_id} completed and chat messages saved"
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
        # Ignore discovery messages (agents and gateways)
        if "/discovery/" in topic:
            return None
        # Ignore trust manager trust card messages
        if "/trust/" in topic:
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

    def _save_chat_messages_for_background_task(
        self, db: DBSession, task_id: str, task: Task, repo: TaskRepository
    ) -> None:
        """
        Save chat messages for a completed background task by reconstructing them from task events.
        This ensures chat history is available when users return to a session after a background task completes.
        Uses upsert to avoid duplicates.
        """
        try:
            # Get all events for this task
            task_with_events = repo.find_by_id_with_events(db, task_id)
            if not task_with_events:
                log.warning(
                    f"{self.log_identifier} Could not find task {task_id} with events for chat message saving"
                )
                return
            
            _, events = task_with_events
            
            # Extract session_id and user_id from the task's initial request
            session_id = None
            user_id = task.user_id
            agent_name = None
            user_message_text = task.initial_request_text
            
            # Parse events to extract session context and reconstruct messages
            message_bubbles = []
            artifacts = []  # Track artifacts - only from final task response to avoid duplicates
            rag_data = []  # Track RAG metadata from tool results
            accumulated_agent_text = []  # Accumulate text from all status updates
            accumulated_agent_parts = []  # Accumulate parts from all status updates
            
            for event in events:
                try:
                    payload = event.payload
                    
                    # Extract session_id from the first request event
                    if event.direction == "request" and not session_id:
                        if "params" in payload and isinstance(payload["params"], dict):
                            message = payload["params"].get("message", {})
                            if isinstance(message, dict):
                                session_id = message.get("contextId")
                                # Extract agent name from metadata
                                metadata = message.get("metadata", {})
                                if isinstance(metadata, dict):
                                    agent_name = metadata.get("agent_name")
                                
                                # Add user message bubble
                                parts = message.get("parts", [])
                                
                                # Filter out the gateway timestamp part (first part if it starts with "Request received by gateway")
                                filtered_parts = []
                                for i, part in enumerate(parts):
                                    if part.get("kind") == "text":
                                        text = part.get("text", "")
                                        # Skip the first part if it's the gateway timestamp
                                        if i == 0 and text.startswith("Request received by gateway at:"):
                                            continue
                                        filtered_parts.append(part)
                                    else:
                                        filtered_parts.append(part)
                                
                                text_parts = [p.get("text", "") for p in filtered_parts if p.get("kind") == "text"]
                                combined_text = "".join(text_parts)
                                
                                if combined_text or any(p.get("kind") == "file" for p in filtered_parts):
                                    message_bubbles.append({
                                        "id": f"msg-{uuid.uuid4()}",
                                        "type": "user",
                                        "text": combined_text,
                                        "parts": filtered_parts,
                                    })
                    
                    # Collect text content AND RAG metadata from status events
                    # Text is accumulated to reconstruct the full agent response
                    elif event.direction == "status":
                        if "result" in payload:
                            result = payload["result"]
                            
                            # Extract text content from status updates
                            status = result.get("status", {})
                            if isinstance(status, dict):
                                message = status.get("message", {})
                                if isinstance(message, dict):
                                    parts = message.get("parts", [])
                                    for part in parts:
                                        if isinstance(part, dict):
                                            part_kind = part.get("kind")
                                            if part_kind == "text":
                                                text = part.get("text", "")
                                                if text:
                                                    accumulated_agent_text.append(text)
                                                    accumulated_agent_parts.append(part)
                                            elif part_kind == "data":
                                                # Extract RAG metadata from tool_result data parts
                                                data = part.get("data", {})
                                                if isinstance(data, dict):
                                                    data_type = data.get("type")
                                                    
                                                    if data_type == "tool_result":
                                                        result_data = data.get("result_data", {})
                                                        if isinstance(result_data, dict) and "rag_metadata" in result_data:
                                                            rag_metadata = result_data["rag_metadata"]
                                                            if isinstance(rag_metadata, dict):
                                                                # Add taskId to the RAG metadata
                                                                rag_metadata["taskId"] = task_id
                                                                rag_data.append(rag_metadata)
                                                                log.info(
                                                                    f"{self.log_identifier} Extracted RAG metadata for task {task_id}: "
                                                                    f"searchType={rag_metadata.get('searchType')}, "
                                                                    f"sources_count={len(rag_metadata.get('sources', []))}"
                                                                )
                                                    elif data_type == "artifact_creation_progress":
                                                        # Handle cancelled artifacts with rolled back text
                                                        if data.get("status") == "cancelled":
                                                            rolled_back_text = data.get("rolled_back_text")
                                                            if rolled_back_text:
                                                                accumulated_agent_text.append(rolled_back_text)
                                                                log.info(
                                                                    f"{self.log_identifier} Extracted rolled_back_text from cancelled artifact event for task {task_id}"
                                                                )
                                                
                                                accumulated_agent_parts.append(part)
                                            else:
                                                # Accumulate other non-text, non-data parts
                                                accumulated_agent_parts.append(part)
                    
                    # Extract artifacts and any additional text from final task response
                    elif event.direction == "response":
                        if "result" in payload:
                            result = payload["result"]
                            
                            # Only process final task response (kind="task")
                            if isinstance(result, dict) and result.get("kind") == "task":
                                # Extract artifacts from task metadata
                                metadata = result.get("metadata", {})
                                if isinstance(metadata, dict):
                                    # Try both 'produced_artifacts' and 'artifact_manifest'
                                    artifact_list = metadata.get("produced_artifacts") or metadata.get("artifact_manifest", [])
                                    if isinstance(artifact_list, list):
                                        for artifact_info in artifact_list:
                                            if isinstance(artifact_info, dict):
                                                # Handle both 'name' and 'filename' keys
                                                artifact_name = artifact_info.get("name") or artifact_info.get("filename")
                                                # Skip web_content_ artifacts (temporary files from deep research)
                                                if artifact_name and not artifact_name.startswith("web_content_"):
                                                    artifacts.append({
                                                        "kind": "artifact",
                                                        "status": "completed",
                                                        "name": artifact_name,
                                                        "file": {
                                                            "name": artifact_name,
                                                            "mime_type": artifact_info.get("mime_type"),
                                                            "uri": f"artifact://{session_id}/{artifact_name}" if session_id else f"artifact://unknown/{artifact_name}"
                                                        }
                                                    })
                                
                                # Final task object - extract any additional text not in status updates
                                status = result.get("status", {})
                                if isinstance(status, dict):
                                    message = status.get("message", {})
                                    if isinstance(message, dict):
                                        parts = message.get("parts", [])
                                        
                                        # Extract RAG metadata from tool_result data parts in final response
                                        for part in parts:
                                            if isinstance(part, dict) and part.get("kind") == "data":
                                                data = part.get("data", {})
                                                if isinstance(data, dict) and data.get("type") == "tool_result":
                                                    result_data = data.get("result_data", {})
                                                    if isinstance(result_data, dict) and "rag_metadata" in result_data:
                                                        rag_metadata = result_data["rag_metadata"]
                                                        if isinstance(rag_metadata, dict):
                                                            # Add taskId to the RAG metadata
                                                            rag_metadata["taskId"] = task_id
                                                            # Avoid duplicates
                                                            if rag_metadata not in rag_data:
                                                                rag_data.append(rag_metadata)
                                                                log.info(
                                                                    f"{self.log_identifier} Extracted RAG metadata from final response for task {task_id}: "
                                                                    f"searchType={rag_metadata.get('searchType')}, "
                                                                    f"sources_count={len(rag_metadata.get('sources', []))}"
                                                                )
                                        
                                        
                except Exception as e:
                    log.warning(
                        f"{self.log_identifier} Error parsing event for chat message reconstruction: {e}"
                    )
                    continue
            
            # After processing all events, create the agent message bubble from accumulated content
            if accumulated_agent_text or artifacts:
                combined_text = "".join(accumulated_agent_text).strip()
                
                # Check if artifact markers are already in the texts
                import re
                existing_markers = set()
                marker_pattern = r'«artifact_return:([^»]+)»'
                for match in re.finditer(marker_pattern, combined_text):
                    # Normalize the artifact name (strip version suffix)
                    artifact_ref = match.group(1)
                    if ':' in artifact_ref:
                        base_name = artifact_ref.rsplit(':', 1)[0]
                        try:
                            int(artifact_ref.rsplit(':', 1)[1])
                            # Add the base name (without version) to existing markers
                            # so we don't add a duplicate marker later
                            existing_markers.add(base_name)
                        except ValueError:
                            # Not a version number, treat the whole thing as the artifact name
                            existing_markers.add(artifact_ref)
                    else:
                        existing_markers.add(artifact_ref)
                
                # Only add artifact markers if they're not already present
                for artifact in artifacts:
                    artifact_name = artifact['name']
                    if artifact_name not in existing_markers:
                        combined_text += f"«artifact_return:{artifact_name}»"
                        log.info(
                            f"{self.log_identifier} Adding artifact marker for {artifact_name}"
                        )
                    else:
                        log.info(
                            f"{self.log_identifier} Skipping duplicate artifact marker for {artifact_name} (already in text)"
                        )
                
                # Filter out data parts from accumulated parts
                content_parts = [p for p in accumulated_agent_parts if p.get("kind") != "data"]
                
                message_bubbles.append({
                    "id": f"msg-{uuid.uuid4()}",
                    "type": "agent",
                    "text": combined_text,
                    "parts": content_parts,  # Only content parts, no artifacts
                })
                
            
            # Only save if we have a session_id and at least one message
            if not session_id:
                log.warning(
                    f"{self.log_identifier} Could not extract session_id for task {task_id}, skipping chat message save"
                )
                return
            
            if not message_bubbles:
                log.warning(
                    f"{self.log_identifier} No message bubbles reconstructed for task {task_id}, skipping chat message save"
                )
                return
            
            # Import here to avoid circular dependency
            from ..repository.chat_task_repository import ChatTaskRepository
            from ..repository.entities import ChatTask
            from ..repository.session_repository import SessionRepository
            
            # Check if the session exists in this database
            session_repo = SessionRepository()
            if not session_repo.exists(db, session_id):
                log.debug(
                    f"{self.log_identifier} Session {session_id} not found in webui_gateway database "
                    f"Skipping chat message save for task {task_id}"
                )
                return
            
            # Build task metadata including RAG data if present
            task_metadata_dict = {
                "schema_version": 1,
                "status": task.status,
                "agent_name": agent_name,
            }
            
            # Include RAG data if we found any
            if rag_data:
                task_metadata_dict["rag_data"] = rag_data
                log.info(
                    f"{self.log_identifier} Including {len(rag_data)} RAG data entries in task metadata for {task_id}"
                )
            
            # Create and save the chat task
            chat_task = ChatTask(
                id=task_id,
                session_id=session_id,
                user_id=user_id,
                user_message=user_message_text,
                message_bubbles=json.dumps(message_bubbles),
                task_metadata=json.dumps(task_metadata_dict),
                created_time=task.start_time,
                updated_time=task.end_time,
            )
            
            chat_task_repo = ChatTaskRepository()
            chat_task_repo.save(db, chat_task)
            
            log.info(
                f"{self.log_identifier} Saved chat messages for background task {task_id} "
                f"(session: {session_id}, {len(message_bubbles)} message bubbles)"
            )
            
        except Exception as e:
            log.error(
                f"{self.log_identifier} Failed to save chat messages for background task {task_id}: {e}",
                exc_info=True
            )
