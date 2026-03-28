"""
Result handler for scheduled task executions.
Processes A2A responses and updates execution records.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from a2a.types import Task, JSONRPCResponse, JSONRPCError
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


class ResultHandler:
    """
    Handles A2A task responses for scheduled task executions.
    Updates execution records with results, artifacts, and errors.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        namespace: str,
        instance_id: str,
    ):
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[ResultHandler:{instance_id}]"

        self.pending_executions: Dict[str, str] = {}
        self.execution_sessions: Dict[str, str] = {}
        self.completion_events: Dict[str, asyncio.Event] = {}
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
        """Handle an A2A response message."""
        topic = message_data.get("topic", "")
        payload = message_data.get("payload", {})

        if not self._is_scheduler_response(topic):
            return

        try:
            rpc_response = JSONRPCResponse.model_validate(payload)
            a2a_task_id = a2a.get_response_id(rpc_response)
            if not a2a_task_id:
                return

            async with self.pending_executions_lock:
                execution_id = self.pending_executions.get(a2a_task_id)

            if not execution_id:
                return

            result = a2a.get_response_result(rpc_response)
            error = a2a.get_response_error(rpc_response)

            if result:
                await self._handle_success(execution_id, result)
            elif error:
                await self._handle_error(execution_id, error)

            # Remove from pending
            async with self.pending_executions_lock:
                self.pending_executions.pop(a2a_task_id, None)

        except Exception as e:
            log.error("%s Error handling response: %s", self.log_prefix, e, exc_info=True)

    async def _handle_success(self, execution_id: str, result: Any):
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
                            if not any(
                                (a.get("name") if isinstance(a, dict) else None) == art_name
                                for a in artifacts
                            ):
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
                                if not any(
                                    (a.get("name") if isinstance(a, dict) else None) == art_name
                                    for a in artifacts
                                ):
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
                                    if not any(
                                        (a.get("name") if isinstance(a, dict) else None) == art_name
                                        for a in artifacts
                                    ):
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
                            if not any(
                                (a.get("name") if isinstance(a, dict) else None) == artifact_id
                                for a in artifacts
                            ):
                                artifacts.append(artifact_obj)

            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                update_data = {
                    "status": ExecutionStatus.COMPLETED,
                    "completed_at": now_epoch_ms(),
                    "result_summary": result_summary,
                    "artifacts": artifacts if artifacts else None,
                }
                repo.update_execution(session, execution_id, update_data)

                # Create ChatTask so content appears in the chat session view
                execution = repo.find_execution_by_id(session, execution_id)
                if execution:
                    self._save_chat_task(session, execution, full_messages, artifacts=artifacts, rag_data=rag_data)

                session.commit()

            log.info(
                "%s Execution %s completed with %s messages and %s artifacts",
                self.log_prefix, execution_id, len(messages), len(artifacts),
            )

        except Exception as e:
            log.error(
                "%s Error handling success for execution %s: %s",
                self.log_prefix, execution_id, e,
                exc_info=True,
            )
        finally:
            # Always clean up session tracking and signal completion
            async with self.pending_executions_lock:
                self.execution_sessions.pop(execution_id, None)
                event = self.completion_events.pop(execution_id, None)
            if event:
                event.set()

    async def _handle_error(self, execution_id: str, error: JSONRPCError):
        """Handle task execution error."""
        log.warning(
            "%s Handling error for execution %s: %s",
            self.log_prefix, execution_id, _sanitize_error_message(error.message),
        )

        try:
            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                update_data = {
                    "status": ExecutionStatus.FAILED,
                    "completed_at": now_epoch_ms(),
                    "error_message": _sanitize_error_message(error.message),
                    "result_summary": {"error_code": error.code},
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
            # Always clean up session tracking and signal completion
            async with self.pending_executions_lock:
                self.execution_sessions.pop(execution_id, None)
                event = self.completion_events.pop(execution_id, None)
            if event:
                event.set()

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
        """
        try:
            from ...repository.models import ChatTaskModel

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
            log.info(
                "%s Created ChatTask for execution %s in session %s",
                self.log_prefix, execution.id, session_id,
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

    async def cleanup_stale_executions(self, timeout_seconds: int = 7200):
        """Clean up executions that have been running too long."""
        try:
            cutoff_time = now_epoch_ms() - (timeout_seconds * 1000)

            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                from sqlalchemy import select
                from ...repository.models import ScheduledTaskExecutionModel

                stmt = select(ScheduledTaskExecutionModel).where(
                    ScheduledTaskExecutionModel.status == ExecutionStatus.RUNNING,
                    ScheduledTaskExecutionModel.started_at < cutoff_time,
                )
                stale_executions = session.execute(stmt).scalars().all()

                for execution in stale_executions:
                    update_data = {
                        "status": ExecutionStatus.TIMEOUT,
                        "completed_at": now_epoch_ms(),
                        "error_message": "Execution exceeded the configured timeout",
                    }
                    repo.update_execution(session, execution.id, update_data)

                    if execution.a2a_task_id:
                        async with self.pending_executions_lock:
                            self.pending_executions.pop(execution.a2a_task_id, None)
                            self.execution_sessions.pop(execution.id, None)
                            event = self.completion_events.pop(execution.id, None)
                        if event:
                            event.set()

                session.commit()

        except Exception as e:
            log.error(
                "%s Error cleaning up stale executions: %s",
                self.log_prefix, e,
                exc_info=True,
            )

    def get_pending_count(self) -> int:
        """Get count of pending executions."""
        return len(self.pending_executions)
