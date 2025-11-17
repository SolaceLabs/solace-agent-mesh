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
        """
        Initialize result handler.

        Args:
            session_factory: Factory function to create database sessions
            namespace: Namespace for A2A communication
            instance_id: Scheduler instance ID
        """
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[ResultHandler:{instance_id}]"

        # Track pending executions (a2a_task_id -> execution_id)
        self.pending_executions: Dict[str, str] = {}
        # Track execution session IDs (execution_id -> session_id) for artifact URIs
        self.execution_sessions: Dict[str, str] = {}
        self.pending_executions_lock = asyncio.Lock()

        log.info(f"{self.log_prefix} Initialized")

    async def register_execution(self, execution_id: str, a2a_task_id: str, session_id: str = None):
        """
        Register an execution to track its A2A task.

        Args:
            execution_id: Execution record ID
            a2a_task_id: Corresponding A2A task ID
            session_id: Session ID for artifact URIs (optional)
        """
        async with self.pending_executions_lock:
            self.pending_executions[a2a_task_id] = execution_id
            if session_id:
                self.execution_sessions[execution_id] = session_id
            log.debug(
                f"{self.log_prefix} Registered execution {execution_id} for A2A task {a2a_task_id} (session: {session_id})"
            )

    async def handle_response(self, message_data: Dict[str, Any]):
        """
        Handle an A2A response message.

        Args:
            message_data: Dictionary containing topic, payload, and user_properties
        """
        topic = message_data.get("topic", "")
        payload = message_data.get("payload", {})

        # Check if this is a scheduler response
        if not self._is_scheduler_response(topic):
            return

        log.debug(f"{self.log_prefix} Processing scheduler response from topic: {topic}")

        try:
            # Parse as JSON-RPC response
            rpc_response = JSONRPCResponse.model_validate(payload)

            # Extract A2A task ID
            a2a_task_id = a2a.get_response_id(rpc_response)
            if not a2a_task_id:
                log.warning(f"{self.log_prefix} Response missing task ID")
                return

            # Find corresponding execution
            async with self.pending_executions_lock:
                execution_id = self.pending_executions.get(a2a_task_id)

            if not execution_id:
                log.debug(
                    f"{self.log_prefix} No pending execution found for A2A task {a2a_task_id}"
                )
                return

            # Process result or error using helper functions
            result = a2a.get_response_result(rpc_response)
            error = a2a.get_response_error(rpc_response)
            
            if result:
                await self._handle_success(execution_id, result)
            elif error:
                await self._handle_error(execution_id, error)

            # Remove from pending
            async with self.pending_executions_lock:
                if a2a_task_id in self.pending_executions:
                    del self.pending_executions[a2a_task_id]

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling response: {e}",
                exc_info=True,
            )

    async def _handle_success(self, execution_id: str, result: Any):
        """
        Handle successful task completion.

        Args:
            execution_id: Execution record ID
            result: A2A task result
        """
        log.info(f"{self.log_prefix} Handling success for execution {execution_id}")

        try:
            # Extract result data
            result_summary = {}
            artifacts = []
            messages = []

            if isinstance(result, Task):
                # Extract status (contains the final message for RUN_BASED sessions)
                # Access result.status directly (it's a TaskStatus object, not TaskState enum)
                if result.status and result.status.message:
                    # Extract text from status message (this is where RUN_BASED text goes)
                    agent_text = a2a.get_text_from_message(result.status.message)
                    if agent_text:
                        result_summary["agent_response"] = agent_text[:1000]
                        messages.append({
                            "role": "agent",
                            "text": agent_text[:1000]
                        })
                    
                    # Extract file parts from status message
                    file_parts = a2a.get_file_parts_from_message(result.status.message)
                    for file_part in file_parts:
                        uri = a2a.get_uri_from_file_part(file_part)
                        if uri and uri not in artifacts:
                            artifacts.append(uri)
                
                # Also check history for PERSISTENT sessions (backward compatibility)
                history = a2a.get_task_history(result)
                if history:
                    for msg in history:
                        text = a2a.get_text_from_message(msg)
                        role = getattr(msg, 'role', 'unknown')
                        if text:
                            messages.append({
                                "role": str(role),
                                "text": text[:1000]
                            })
                        
                        file_parts = a2a.get_file_parts_from_message(msg)
                        for file_part in file_parts:
                            uri = a2a.get_uri_from_file_part(file_part)
                            if uri and uri not in artifacts:
                                artifacts.append(uri)
                
                if messages:
                    result_summary["messages"] = messages

                # Extract metadata
                metadata = a2a.get_task_metadata(result)
                if metadata:
                    result_summary["metadata"] = metadata
                
                # Store task status state
                task_state = a2a.get_task_status(result)  # Returns TaskState enum
                if task_state:
                    result_summary["task_status"] = str(task_state)
                
                # Extract artifacts from task
                task_artifacts = a2a.get_task_artifacts(result)
                if task_artifacts:
                    # Get session ID from execution tracking
                    session_id = self.execution_sessions.get(execution_id)
                    
                    for artifact in task_artifacts:
                        artifact_id = a2a.get_artifact_id(artifact)
                        if artifact_id:
                            # Create artifact object with name and viewable API URI
                            # Use the special /scheduled/ endpoint that bypasses session validation
                            if session_id:
                                artifact_uri = f"/api/v1/artifacts/scheduled/{session_id}/{artifact_id}"
                            else:
                                # Fallback to artifact:// scheme if no session ID
                                artifact_uri = f"artifact://{artifact_id}"
                                log.warning(
                                    f"{self.log_prefix} No session ID found for execution {execution_id}, using fallback URI"
                                )
                            
                            artifact_obj = {
                                "name": artifact_id,
                                "uri": artifact_uri
                            }
                            # Check if not already added (by ID)
                            if not any(a.get("name") == artifact_id for a in artifacts if isinstance(a, dict)):
                                artifacts.append(artifact_obj)
                                log.debug(
                                    f"{self.log_prefix} Added artifact '{artifact_id}' with URI: {artifact_uri}"
                                )

            # Update execution record
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

            # Clean up session tracking
            if execution_id in self.execution_sessions:
                del self.execution_sessions[execution_id]
            
            log.info(
                f"{self.log_prefix} Execution {execution_id} marked as completed with {len(messages)} messages and {len(artifacts)} artifacts"
            )

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling success for execution {execution_id}: {e}",
                exc_info=True,
            )

    async def _handle_error(self, execution_id: str, error: JSONRPCError):
        """
        Handle task execution error.

        Args:
            execution_id: Execution record ID
            error: A2A error object
        """
        log.warning(
            f"{self.log_prefix} Handling error for execution {execution_id}: {error.message}"
        )

        try:
            # Update execution record
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

            log.info(f"{self.log_prefix} Execution {execution_id} marked as failed")

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling error for execution {execution_id}: {e}",
                exc_info=True,
            )

    def _is_scheduler_response(self, topic: str) -> bool:
        """
        Check if a topic is a scheduler response topic.

        Args:
            topic: Solace topic string

        Returns:
            True if this is a scheduler response topic
        """
        # Response topics: {namespace}a2a/v1/scheduler/response/{any_instance_id}
        # Note: namespace already has trailing slash
        response_prefix = f"{self.namespace}a2a/v1/scheduler/response/"
        result = topic.startswith(response_prefix)
        if result:
            log.debug(f"{self.log_prefix} Topic {topic} matches scheduler response pattern")
        return result

    async def cleanup_stale_executions(self, timeout_seconds: int = 7200):
        """
        Clean up executions that have been running too long.

        Args:
            timeout_seconds: Maximum execution time before considering stale
        """
        log.info(f"{self.log_prefix} Cleaning up stale executions")

        try:
            cutoff_time = now_epoch_ms() - (timeout_seconds * 1000)

            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                # Find running executions older than cutoff
                from sqlalchemy import select
                from ...repository.models import ScheduledTaskExecutionModel

                stmt = select(ScheduledTaskExecutionModel).where(
                    ScheduledTaskExecutionModel.status == ExecutionStatus.RUNNING,
                    ScheduledTaskExecutionModel.started_at < cutoff_time,
                )

                stale_executions = session.execute(stmt).scalars().all()

                for execution in stale_executions:
                    log.warning(
                        f"{self.log_prefix} Found stale execution {execution.id}, marking as timeout"
                    )
                    update_data = {
                        "status": ExecutionStatus.TIMEOUT,
                        "completed_at": now_epoch_ms(),
                        "error_message": f"Execution exceeded timeout of {timeout_seconds} seconds",
                    }
                    repo.update_execution(session, execution.id, update_data)

                    # Remove from pending
                    if execution.a2a_task_id:
                        async with self.pending_executions_lock:
                            if execution.a2a_task_id in self.pending_executions:
                                del self.pending_executions[execution.a2a_task_id]

                session.commit()

                if stale_executions:
                    log.info(
                        f"{self.log_prefix} Cleaned up {len(stale_executions)} stale executions"
                    )

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error cleaning up stale executions: {e}",
                exc_info=True,
            )

    def get_pending_count(self) -> int:
        """Get count of pending executions."""
        return len(self.pending_executions)