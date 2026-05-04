"""
Result handler for scheduled task executions.
Processes A2A responses and updates execution records.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from a2a.types import Task, TaskState, TaskStatusUpdateEvent, JSONRPCResponse, JSONRPCError
from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.common import a2a
from ...repository.models import ExecutionStatus, ScheduledTaskExecutionModel
from ...repository.scheduled_task_repository import ScheduledTaskRepository
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)

_MAX_USER_ERROR_LENGTH = 256


def _sanitize_error_message(message: str) -> str:
    """Strip internal details from error messages before persisting for the frontend."""
    if not message:
        return "Task execution failed"
    sanitized = message.split("\n")[0].strip()
    if len(sanitized) > _MAX_USER_ERROR_LENGTH:
        sanitized = sanitized[:_MAX_USER_ERROR_LENGTH] + "..."
    return sanitized or "Task execution failed"


def _rag_entry_key(entry: dict) -> str:
    """Return a stable deduplication key for a RAG metadata entry.

    Uses the source URL when available; falls back to a content hash.
    """
    source = entry.get("source_url") or entry.get("url") or entry.get("source")
    if source:
        return source
    return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def _artifact_name_exists(artifacts: list, name: str) -> bool:
    """Check if an artifact with the given name already exists in the list."""
    return any(
        (a.get("name") if isinstance(a, dict) else None) == name
        for a in artifacts
    )


class ResultHandler:
    """
    Handles A2A task responses for scheduled task executions.
    Updates execution records with results, artifacts, and errors.
    Also accumulates RAG metadata from intermediate status updates
    so that inline citations are available when the final response arrives.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        namespace: str,
        instance_id: str,
        sse_manager: Optional[Any] = None,
    ):
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[ResultHandler:{instance_id}]"
        self.sse_manager = sse_manager

        self.pending_executions: Dict[str, str] = {}
        self.execution_sessions: Dict[str, str] = {}
        self.completion_events: Dict[str, asyncio.Event] = {}
        # Accumulates RAG metadata from intermediate status updates keyed by a2a_task_id.
        # Populated by _handle_status_update() before the final response arrives.
        self._accumulated_rag_data: Dict[str, list] = {}
        self.pending_executions_lock = asyncio.Lock()

        log.info("%s Initialized", self.log_prefix)

    async def register_execution(self, execution_id: str, a2a_task_id: str, session_id: str = None):
        """Register an execution to track its A2A task."""
        async with self.pending_executions_lock:
            self.pending_executions[a2a_task_id] = execution_id
            if session_id:
                self.execution_sessions[execution_id] = session_id
            event = asyncio.Event()
            self.completion_events[execution_id] = event
        return event

    async def wait_for_completion(self, execution_id: str):
        """Wait for an execution to complete (signalled by handle_response)."""
        async with self.pending_executions_lock:
            event = self.completion_events.get(execution_id)
        if event:
            await event.wait()

    async def handle_response(self, message_data: Dict[str, Any]):
        """Handle an A2A response or status message.

        Status messages carry intermediate data (RAG metadata, progress signals)
        that must be accumulated *before* the final response arrives.  Response
        messages carry the final Task result or error.
        """
        topic = message_data.get("topic", "")
        payload = message_data.get("payload", {})

        is_response = self._is_scheduler_response(topic)
        is_status = self._is_scheduler_status(topic)

        if not is_response and not is_status:
            return

        try:
            rpc_response = JSONRPCResponse.model_validate(payload)
            a2a_task_id = a2a.get_response_id(rpc_response)
            if not a2a_task_id:
                return

            result = a2a.get_response_result(rpc_response)
            error = a2a.get_response_error(rpc_response)

            if is_status and result:
                # Intermediate status update – accumulate RAG data without
                # completing the execution.  Status handling only needs
                # a2a_task_id, so it must run before the execution_id guard.
                await self._handle_status_update(a2a_task_id, result)
                return

            async with self.pending_executions_lock:
                execution_id = self.pending_executions.get(a2a_task_id)

            if not execution_id:
                return

            if is_response:
                if result:
                    await self._handle_success(execution_id, result, a2a_task_id)
                elif error:
                    await self._handle_error(execution_id, error, a2a_task_id)

                # Remove from pending
                async with self.pending_executions_lock:
                    self.pending_executions.pop(a2a_task_id, None)

        except Exception as e:
            log.error("%s Error handling response: %s", self.log_prefix, e, exc_info=True)

    # ------------------------------------------------------------------
    # Status-update accumulation
    # ------------------------------------------------------------------

    async def _handle_status_update(self, a2a_task_id: str, result: Any):
        """Extract and accumulate RAG metadata from an intermediate status update.

        When an orchestrator delegates to a peer agent that performs a web search,
        the peer sends RAG metadata as data parts inside ``TaskStatusUpdateEvent``
        messages.  The orchestrator forwards these to the scheduler's status topic.
        By accumulating them here we ensure they are available when the final
        response arrives – regardless of whether the TaskLoggerService has
        persisted them to the database yet.

        Also detects ``input_required`` and ``auth_required`` states which require
        user interaction that is impossible in a scheduled (non-interactive)
        execution, and fails the execution immediately.
        """
        if not isinstance(result, TaskStatusUpdateEvent):
            return

        status_msg = getattr(result, "status", None)
        if not status_msg:
            return

        # Scheduled tasks are non-interactive — if the agent requests user
        # interaction (OAuth consent, input prompts, etc.) we must fail fast
        # instead of blocking indefinitely.
        if status_msg.state in (TaskState.input_required, TaskState.auth_required):
            log.warning(
                "%s Scheduled task %s requires user interaction (state=%s) — failing execution",
                self.log_prefix, a2a_task_id, status_msg.state.value,
            )
            async with self.pending_executions_lock:
                execution_id = self.pending_executions.pop(a2a_task_id, None)
            if execution_id:
                error = JSONRPCError(
                    code=-32001,
                    message=(
                        "Task requires user authentication or input which is not "
                        "available in scheduled (non-interactive) executions. "
                        "Please ensure the required tool credentials are "
                        "pre-configured before scheduling this task."
                    ),
                )
                await self._handle_error(execution_id, error, a2a_task_id)
            return

        message = getattr(status_msg, "message", None)
        if not message:
            return

        data_parts = a2a.get_data_parts_from_message(message)
        if not data_parts:
            return

        new_entries: List[dict] = []
        for data_part in data_parts:
            data = a2a.get_data_from_data_part(data_part)
            if not isinstance(data, dict) or data.get("type") != "tool_result":
                continue
            result_data = data.get("result_data", {})
            if isinstance(result_data, dict) and "rag_metadata" in result_data:
                rag_metadata = result_data["rag_metadata"]
                if isinstance(rag_metadata, dict):
                    new_entries.append(rag_metadata)

        if new_entries:
            async with self.pending_executions_lock:
                existing = self._accumulated_rag_data.setdefault(a2a_task_id, [])
                existing_keys = {_rag_entry_key(e) for e in existing}
                for entry in new_entries:
                    key = _rag_entry_key(entry)
                    if key not in existing_keys:
                        existing.append(entry)
                        existing_keys.add(key)
            log.info(
                "%s Accumulated %d RAG metadata entries from status update for task %s (total: %d)",
                self.log_prefix,
                len(new_entries),
                a2a_task_id,
                len(self._accumulated_rag_data.get(a2a_task_id, [])),
            )

    async def _cleanup_execution(self, execution_id: str, a2a_task_id: str):
        """Clean up session tracking, accumulated data, and signal completion."""
        async with self.pending_executions_lock:
            self.execution_sessions.pop(execution_id, None)
            self._accumulated_rag_data.pop(a2a_task_id, None)
            event = self.completion_events.pop(execution_id, None)
        if event:
            event.set()

    async def _handle_success(self, execution_id: str, result: Any, a2a_task_id: str):
        """Handle successful task completion."""
        log.info("%s Handling success for execution %s", self.log_prefix, execution_id)

        try:
            result_summary = {}
            artifacts = []
            rag_data = []
            messages = []  # Truncated for result_summary storage
            full_messages = []  # Full text for chat bubble display

            if isinstance(result, Task):
                if result.status and result.status.message:
                    agent_text = a2a.get_text_from_message(result.status.message)
                    if agent_text:
                        result_summary["agent_response"] = agent_text[:1000]
                        messages.append({"role": "agent", "text": agent_text[:1000]})
                        full_messages.append({"role": "agent", "text": agent_text})

                    # Extract RAG metadata from data parts (inline citations)
                    data_parts = a2a.get_data_parts_from_message(result.status.message)
                    for data_part in data_parts:
                        data = a2a.get_data_from_data_part(data_part)
                        if isinstance(data, dict) and data.get("type") == "tool_result":
                            result_data = data.get("result_data", {})
                            if isinstance(result_data, dict) and "rag_metadata" in result_data:
                                rag_metadata = result_data["rag_metadata"]
                                if isinstance(rag_metadata, dict):
                                    rag_data.append(rag_metadata)

                    file_parts = a2a.get_file_parts_from_message(result.status.message)
                    for file_part in file_parts:
                        uri = a2a.get_uri_from_file_part(file_part)
                        if uri:
                            art_name = uri.rsplit("/", 1)[-1] if "/" in uri else uri
                            if not _artifact_name_exists(artifacts, art_name):
                                artifacts.append({
                                    "name": art_name,
                                    "uri": uri,
                                })

                history = a2a.get_task_history(result)
                if history:
                    for msg in history:
                        text = a2a.get_text_from_message(msg)
                        role = getattr(msg, 'role', 'unknown')
                        if text:
                            messages.append({"role": str(role), "text": text[:1000]})
                            full_messages.append({"role": str(role), "text": text})
                        file_parts = a2a.get_file_parts_from_message(msg)
                        for file_part in file_parts:
                            uri = a2a.get_uri_from_file_part(file_part)
                            if uri:
                                art_name = uri.rsplit("/", 1)[-1] if "/" in uri else uri
                                if not _artifact_name_exists(artifacts, art_name):
                                    artifacts.append({
                                        "name": art_name,
                                        "uri": uri,
                                    })
                        # Extract RAG metadata from history messages too
                        history_data_parts = a2a.get_data_parts_from_message(msg)
                        for data_part in history_data_parts:
                            data = a2a.get_data_from_data_part(data_part)
                            if isinstance(data, dict) and data.get("type") == "tool_result":
                                result_data = data.get("result_data", {})
                                if isinstance(result_data, dict) and "rag_metadata" in result_data:
                                    rag_metadata = result_data["rag_metadata"]
                                    if isinstance(rag_metadata, dict) and rag_metadata not in rag_data:
                                        rag_data.append(rag_metadata)

                if messages:
                    result_summary["messages"] = messages

                task_state = a2a.get_task_status(result)
                if task_state:
                    result_summary["task_status"] = str(task_state)

                # Extract artifacts from task metadata (produced_artifacts manifest)
                # Agents attach artifact manifests to metadata, not bundled in the response
                async with self.pending_executions_lock:
                    session_id = self.execution_sessions.get(execution_id)
                task_metadata = a2a.get_task_metadata(result)
                if task_metadata and isinstance(task_metadata, dict):
                    artifact_list = task_metadata.get("produced_artifacts") or task_metadata.get("artifact_manifest", [])
                    if isinstance(artifact_list, list):
                        for artifact_info in artifact_list:
                            if isinstance(artifact_info, dict):
                                art_name = artifact_info.get("name") or artifact_info.get("filename")
                                if art_name and not art_name.startswith("web_content_"):
                                    art_uri = f"artifact://{session_id}/{art_name}" if session_id else f"artifact://unknown/{art_name}"
                                    artifact_obj = {
                                        "kind": "artifact",
                                        "status": "completed",
                                        "name": art_name,
                                        "file": {
                                            "name": art_name,
                                            "mime_type": artifact_info.get("mime_type"),
                                            "uri": art_uri,
                                        },
                                    }
                                    # Preserve the version from the produced_artifacts
                                    # manifest so the artifact can be pinned to the
                                    # exact version produced by this execution.
                                    art_version = artifact_info.get("version")
                                    if art_version is not None:
                                        artifact_obj["version"] = art_version
                                    if not _artifact_name_exists(artifacts, art_name):
                                        artifacts.append(artifact_obj)

                # Also check task_artifacts (bundled artifacts, if any)
                task_artifacts = a2a.get_task_artifacts(result)
                if task_artifacts:
                    for artifact in task_artifacts:
                        artifact_id = a2a.get_artifact_id(artifact)
                        if artifact_id:
                            if session_id:
                                artifact_uri = f"artifact://{session_id}/{artifact_id}"
                            else:
                                artifact_uri = f"artifact://{artifact_id}"
                            artifact_obj = {
                                "kind": "artifact",
                                "status": "completed",
                                "name": artifact_id,
                                "file": {
                                    "name": artifact_id,
                                    "uri": artifact_uri,
                                },
                            }
                            if not _artifact_name_exists(artifacts, artifact_id):
                                artifacts.append(artifact_obj)

            # Merge in-memory accumulated RAG data (from status updates received
            # before this final response) so that inline citations are available
            # even when the TaskLoggerService hasn't persisted them yet.
            if a2a_task_id:
                async with self.pending_executions_lock:
                    accumulated = self._accumulated_rag_data.pop(a2a_task_id, [])
                existing_keys = {_rag_entry_key(e) for e in rag_data}
                for entry in accumulated:
                    key = _rag_entry_key(entry)
                    if key not in existing_keys:
                        rag_data.append(entry)
                        existing_keys.add(key)
                if accumulated:
                    log.info(
                        "%s Merged %d accumulated RAG entries for execution %s",
                        self.log_prefix, len(accumulated), execution_id,
                    )

            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                # Merge with the existing result_summary (seeded with
                # xRequestId at row insert) rather than overwriting, so
                # the run's correlation id remains visible in run history.
                existing_execution = repo.find_execution_by_id(session, execution_id)
                existing_summary = (
                    existing_execution.result_summary if existing_execution else None
                ) or {}
                merged_summary = {**existing_summary, **result_summary}
                update_data = {
                    "status": ExecutionStatus.COMPLETED,
                    "completed_at": now_epoch_ms(),
                    "result_summary": merged_summary,
                    "artifacts": artifacts if artifacts else None,
                }
                repo.update_execution(session, execution_id, update_data)

                # Create ChatTask so content appears in the chat session view
                execution = repo.find_execution_by_id(session, execution_id)
                if execution:
                    self._save_chat_task(session, execution, full_messages, artifacts=artifacts, rag_data=rag_data)

                session.commit()

            log.info(
                "%s Execution %s completed with %s messages, %s artifacts, and %s RAG entries",
                self.log_prefix, execution_id, len(messages), len(artifacts), len(rag_data),
            )

        except Exception as e:
            log.error(
                "%s Error handling success for execution %s: %s",
                self.log_prefix, execution_id, e,
                exc_info=True,
            )
        finally:
            await self._cleanup_execution(execution_id, a2a_task_id)

    async def _handle_error(self, execution_id: str, error: JSONRPCError, a2a_task_id: str):
        """Handle task execution error."""
        log.warning(
            "%s Handling error for execution %s: %s",
            self.log_prefix, execution_id, _sanitize_error_message(error.message),
        )

        try:
            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                # Preserve the seeded xRequestId by merging into the
                # existing result_summary instead of overwriting.
                existing_execution = repo.find_execution_by_id(session, execution_id)
                existing_summary = (
                    existing_execution.result_summary if existing_execution else None
                ) or {}
                merged_summary = {**existing_summary, "error_code": error.code}
                update_data = {
                    "status": ExecutionStatus.FAILED,
                    "completed_at": now_epoch_ms(),
                    "error_message": _sanitize_error_message(error.message),
                    "result_summary": merged_summary,
                }
                repo.update_execution(session, execution_id, update_data)

                # Create ChatTask so error appears in the chat session view
                execution = repo.find_execution_by_id(session, execution_id)
                if execution:
                    error_messages = [{"role": "agent", "text": _sanitize_error_message(error.message)}]
                    self._save_chat_task(session, execution, error_messages, is_error=True)

                session.commit()

            log.info("%s Execution %s marked as failed", self.log_prefix, execution_id)

        except Exception as e:
            log.error(
                "%s Error handling error for execution %s: %s",
                self.log_prefix, execution_id, e,
                exc_info=True,
            )
        finally:
            await self._cleanup_execution(execution_id, a2a_task_id)

    def _save_chat_task(
        self,
        db_session: DBSession,
        execution: ScheduledTaskExecutionModel,
        messages: list,
        artifacts: list = None,
        is_error: bool = False,
        rag_data: list = None,
    ):
        """Create a ChatTask record so scheduled execution content appears in the chat UI.

        The chat view loads messages from the chat_tasks table. Without this,
        scheduled sessions appear in the list but show no content.

        Also updates the session's ``updated_time`` so the session appears at
        the top of the "Recent Chats" list (ordered by ``updated_time DESC``).
        """
        try:
            from ...repository.models import ChatTaskModel, SessionModel

            session_id = f"scheduled_{execution.id}"

            # Look up the scheduled task to get the user prompt
            task = execution.scheduled_task
            user_message = ""
            if task and task.task_message:
                for part in task.task_message:
                    if part.get("type") == "text":
                        user_message = part.get("text", "")
                        break

            user_id = task.created_by if task else "system-scheduler"

            # Build message bubbles in the format the frontend expects
            bubbles = []

            # User message bubble (the scheduled prompt)
            if user_message:
                bubbles.append({
                    "id": str(uuid.uuid4()),
                    "type": "user",
                    "text": user_message,
                })

            # Agent response bubbles with artifact parts (same format as regular chat)
            for msg in messages:
                role = msg.get("role", "agent")
                text = msg.get("text", "")
                if role == "agent" and text:
                    # Build parts array: text + artifact parts
                    parts = [{"kind": "text", "text": text}]

                    # Append artifact markers to text and artifact parts
                    # Same approach as TaskLoggerService and ChatProvider serialization
                    artifact_text = ""
                    if artifacts:
                        for art in artifacts:
                            if isinstance(art, dict) and art.get("kind") == "artifact":
                                # Already in the right format from metadata extraction
                                art_name = art.get("name", "")
                                if art_name:
                                    artifact_text += f"\n\u00abartifact_return:{art_name}\u00bb"
                                    parts.append(art)
                            elif isinstance(art, dict):
                                art_name = art.get("name", "")
                                art_uri = art.get("uri", "")
                                if art_name:
                                    artifact_text += f"\n\u00abartifact_return:{art_name}\u00bb"
                                    parts.append({
                                        "kind": "artifact",
                                        "status": "completed",
                                        "name": art_name,
                                        "file": {
                                            "name": art_name,
                                            "uri": art_uri,
                                        },
                                    })

                    bubbles.append({
                        "id": str(uuid.uuid4()),
                        "type": "agent",
                        "text": text + artifact_text,
                        "parts": parts,
                        "isError": is_error,
                    })

            if not bubbles:
                return

            now = now_epoch_ms()
            task_metadata_dict = {
                "schema_version": 1,
                "status": "error" if is_error else "completed",
                "agent_name": task.target_agent_name if task else None,
                "source": "scheduler",
            }

            # Merge RAG data: from A2A result (if any) + from task_events logged by TaskLoggerService
            all_rag_data = list(rag_data) if rag_data else []
            a2a_task_id = execution.a2a_task_id or ""

            # Extract RAG data from task_events (intermediate status updates contain data parts
            # with rag_metadata that aren't present in the final aggregated response buffer)
            try:
                events_rag = self._extract_rag_from_task_events(db_session, a2a_task_id)
                for entry in events_rag:
                    if entry not in all_rag_data:
                        all_rag_data.append(entry)
            except Exception as e:
                log.warning(
                    "%s Failed to extract RAG data from task events for execution %s: %s",
                    self.log_prefix, execution.id, e,
                )

            if all_rag_data:
                for entry in all_rag_data:
                    if "taskId" not in entry:
                        entry["taskId"] = a2a_task_id
                task_metadata_dict["rag_data"] = all_rag_data
                log.info(
                    "%s Including %s RAG data entries for execution %s",
                    self.log_prefix, len(all_rag_data), execution.id,
                )
            task_metadata = json.dumps(task_metadata_dict)

            chat_task = ChatTaskModel(
                id=execution.a2a_task_id or str(uuid.uuid4()),
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                message_bubbles=json.dumps(bubbles),
                task_metadata=task_metadata,
                created_time=now,
                updated_time=now,
            )
            db_session.add(chat_task)

            # Update the session's updated_time so it appears at the top of
            # the "Recent Chats" list (ordered by updated_time DESC).
            # Without this, the session keeps its creation-time timestamp and
            # may not surface in the sidebar after the task completes.
            session_record = db_session.get(SessionModel, session_id)
            if session_record:
                session_record.updated_time = now
                log.debug(
                    "%s Updated session %s updated_time to %s",
                    self.log_prefix, session_id, now,
                )

            log.info(
                "%s Created ChatTask for execution %s in session %s",
                self.log_prefix, execution.id, session_id,
            )

            # Push a real-time notification to the user so the frontend
            # refreshes the "Recent Chats" sidebar immediately.
            if self.sse_manager and user_id:
                try:
                    notify_task = asyncio.create_task(
                        self.sse_manager.send_user_notification(
                            user_id=user_id,
                            event_type="session_created",
                            event_data={
                                "session_id": session_id,
                                "task_name": task.name if task else None,
                                "execution_id": execution.id,
                            },
                        )
                    )

                    def _on_notify_done(t: asyncio.Task) -> None:
                        if t.cancelled():
                            return
                        exc = t.exception()
                        if exc:
                            log.warning(
                                "%s Notification task failed for execution %s: %s",
                                self.log_prefix, execution.id, exc,
                            )

                    notify_task.add_done_callback(_on_notify_done)
                except Exception as notify_err:
                    log.warning(
                        "%s Failed to send session_created notification for execution %s: %s",
                        self.log_prefix, execution.id, notify_err,
                    )

        except Exception as e:
            log.warning(
                "%s Failed to create ChatTask for execution %s: %s",
                self.log_prefix, execution.id, e,
            )

    def _extract_rag_from_task_events(self, db_session: DBSession, task_id: str) -> list:
        """Extract RAG metadata from task_events stored by TaskLoggerService.

        The intermediate streaming status updates contain data parts with
        rag_metadata that are not present in the final aggregated Task response.
        """
        from ...repository.task_repository import TaskRepository

        repo = TaskRepository()
        task_with_events = repo.find_by_id_with_events(db_session, task_id)
        if not task_with_events:
            return []

        _, events = task_with_events
        rag_data = []

        for event in events:
            try:
                payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
                if event.direction != "status" or "result" not in payload:
                    continue

                result = payload["result"]
                status = result.get("status", {})
                if not isinstance(status, dict):
                    continue

                message = status.get("message", {})
                if not isinstance(message, dict):
                    continue

                for part in message.get("parts", []):
                    if not isinstance(part, dict) or part.get("kind") != "data":
                        continue
                    data = part.get("data", {})
                    if isinstance(data, dict) and data.get("type") == "tool_result":
                        result_data = data.get("result_data", {})
                        if isinstance(result_data, dict) and "rag_metadata" in result_data:
                            rag_metadata = result_data["rag_metadata"]
                            if isinstance(rag_metadata, dict) and rag_metadata not in rag_data:
                                rag_data.append(rag_metadata)
            except Exception:
                continue

        return rag_data

    def _is_scheduler_response(self, topic: str) -> bool:
        """Check if a topic is a scheduler response topic."""
        response_prefix = f"{self.namespace}a2a/v1/scheduler/response/"
        return topic.startswith(response_prefix)

    def _is_scheduler_status(self, topic: str) -> bool:
        """Check if a topic is a scheduler status topic."""
        status_prefix = f"{self.namespace}a2a/v1/scheduler/status/"
        return topic.startswith(status_prefix)

    def get_pending_count(self) -> int:
        """Get count of pending executions."""
        return len(self.pending_executions)
