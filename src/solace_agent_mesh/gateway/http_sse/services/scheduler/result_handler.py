"""
Result handler for scheduled task executions.
Processes A2A responses and updates execution records.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from a2a.types import Task, JSONRPCResponse, JSONRPCError
from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.common import a2a
from ...repository.models import ExecutionStatus, ScheduledTaskExecutionModel
from ...repository.scheduled_task_repository import ScheduledTaskRepository
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


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
        self.pending_executions_lock = asyncio.Lock()

        log.info(f"{self.log_prefix} Initialized")

    async def register_execution(self, execution_id: str, a2a_task_id: str, session_id: str = None):
        """Register an execution to track its A2A task."""
        async with self.pending_executions_lock:
            self.pending_executions[a2a_task_id] = execution_id
            if session_id:
                self.execution_sessions[execution_id] = session_id

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
            log.error(f"{self.log_prefix} Error handling response: {e}", exc_info=True)

    async def _handle_success(self, execution_id: str, result: Any):
        """Handle successful task completion."""
        log.info(f"{self.log_prefix} Handling success for execution {execution_id}")

        try:
            result_summary = {}
            artifacts = []
            messages = []

            if isinstance(result, Task):
                if result.status and result.status.message:
                    agent_text = a2a.get_text_from_message(result.status.message)
                    if agent_text:
                        result_summary["agent_response"] = agent_text[:1000]
                        messages.append({"role": "agent", "text": agent_text[:1000]})

                    file_parts = a2a.get_file_parts_from_message(result.status.message)
                    for file_part in file_parts:
                        uri = a2a.get_uri_from_file_part(file_part)
                        if uri and uri not in artifacts:
                            artifacts.append(uri)

                history = a2a.get_task_history(result)
                if history:
                    for msg in history:
                        text = a2a.get_text_from_message(msg)
                        role = getattr(msg, 'role', 'unknown')
                        if text:
                            messages.append({"role": str(role), "text": text[:1000]})
                        file_parts = a2a.get_file_parts_from_message(msg)
                        for file_part in file_parts:
                            uri = a2a.get_uri_from_file_part(file_part)
                            if uri and uri not in artifacts:
                                artifacts.append(uri)

                if messages:
                    result_summary["messages"] = messages

                metadata = a2a.get_task_metadata(result)
                if metadata:
                    result_summary["metadata"] = metadata

                task_state = a2a.get_task_status(result)
                if task_state:
                    result_summary["task_status"] = str(task_state)

                task_artifacts = a2a.get_task_artifacts(result)
                if task_artifacts:
                    session_id = self.execution_sessions.get(execution_id)
                    for artifact in task_artifacts:
                        artifact_id = a2a.get_artifact_id(artifact)
                        if artifact_id:
                            if session_id:
                                artifact_uri = f"/api/v1/artifacts/scheduled/{session_id}/{artifact_id}"
                            else:
                                artifact_uri = f"artifact://{artifact_id}"
                            artifact_obj = {"name": artifact_id, "uri": artifact_uri}
                            if not any(a.get("name") == artifact_id for a in artifacts if isinstance(a, dict)):
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
                session.commit()

            # FIX: Clean up session tracking (was only done on success before,
            # now also done in _handle_error to prevent memory leak)
            self.execution_sessions.pop(execution_id, None)

            log.info(
                f"{self.log_prefix} Execution {execution_id} completed with "
                f"{len(messages)} messages and {len(artifacts)} artifacts"
            )

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling success for execution {execution_id}: {e}",
                exc_info=True,
            )

    async def _handle_error(self, execution_id: str, error: JSONRPCError):
        """Handle task execution error."""
        log.warning(
            f"{self.log_prefix} Handling error for execution {execution_id}: {error.message}"
        )

        try:
            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                update_data = {
                    "status": ExecutionStatus.FAILED,
                    "completed_at": now_epoch_ms(),
                    "error_message": f"{error.message} (Code: {error.code})",
                    "result_summary": {"error_code": error.code, "error_data": error.data},
                }
                repo.update_execution(session, execution_id, update_data)
                session.commit()

            # FIX: Clean up execution_sessions dict on error too (prevents memory leak)
            self.execution_sessions.pop(execution_id, None)

            log.info(f"{self.log_prefix} Execution {execution_id} marked as failed")

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling error for execution {execution_id}: {e}",
                exc_info=True,
            )

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
                        "error_message": f"Execution exceeded timeout of {timeout_seconds} seconds",
                    }
                    repo.update_execution(session, execution.id, update_data)

                    if execution.a2a_task_id:
                        async with self.pending_executions_lock:
                            self.pending_executions.pop(execution.a2a_task_id, None)
                            self.execution_sessions.pop(execution.id, None)

                session.commit()

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error cleaning up stale executions: {e}",
                exc_info=True,
            )

    def get_pending_count(self) -> int:
        """Get count of pending executions."""
        return len(self.pending_executions)
