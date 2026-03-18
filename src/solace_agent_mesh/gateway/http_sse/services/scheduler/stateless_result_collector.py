"""
Stateless result collector for Kubernetes deployments.
Uses database as source of truth instead of in-memory state.
"""

import logging
from typing import Any, Callable, Dict, Optional

from a2a.types import Task, JSONRPCResponse, JSONRPCError
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.common import a2a
from ...repository.models import ExecutionStatus, ScheduledTaskExecutionModel
from ...repository.scheduled_task_repository import ScheduledTaskRepository
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


class StatelessResultCollector:
    """
    Stateless result collector that uses database as source of truth.
    Suitable for Kubernetes deployments with multiple replicas.
    
    Unlike the original ResultHandler, this does not maintain any in-memory
    state for pending executions. All state is stored in and retrieved from
    the database, making it safe for horizontal scaling.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        namespace: str,
        instance_id: str,
    ):
        """
        Initialize stateless result collector.

        Args:
            session_factory: Factory function to create database sessions
            namespace: Namespace for A2A communication
            instance_id: Collector instance ID (for logging)
        """
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.log_prefix = f"[StatelessResultCollector:{instance_id}]"

        log.info(f"{self.log_prefix} Initialized (stateless mode)")

    async def handle_response(self, message_data: Dict[str, Any]):
        """
        Handle an A2A response message without in-memory state.

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

            # Find corresponding execution in database (not in-memory)
            execution = await self._find_pending_execution(a2a_task_id)
            if not execution:
                log.debug(
                    f"{self.log_prefix} No pending execution found for A2A task {a2a_task_id}"
                )
                return

            # Process result or error
            result = a2a.get_response_result(rpc_response)
            error = a2a.get_response_error(rpc_response)
            
            if result:
                await self._handle_success(execution.id, result)
            elif error:
                await self._handle_error(execution.id, error)

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error handling response: {e}",
                exc_info=True,
            )

    async def _find_pending_execution(
        self, a2a_task_id: str
    ) -> Optional[ScheduledTaskExecutionModel]:
        """
        Find a pending or running execution by A2A task ID.
        
        This queries the database instead of checking in-memory state,
        making it stateless and safe for multiple replicas.

        Args:
            a2a_task_id: The A2A task ID to search for

        Returns:
            ScheduledTaskExecutionModel if found, None otherwise
        """
        try:
            with self.session_factory() as session:
                stmt = select(ScheduledTaskExecutionModel).where(
                    ScheduledTaskExecutionModel.a2a_task_id == a2a_task_id,
                    ScheduledTaskExecutionModel.status.in_([
                        ExecutionStatus.PENDING,
                        ExecutionStatus.RUNNING
                    ])
                )
                execution = session.execute(stmt).scalar_one_or_none()
                
                if execution:
                    log.debug(
                        f"{self.log_prefix} Found execution {execution.id} for A2A task {a2a_task_id}"
                    )
                
                return execution

        except Exception as e:
            log.error(
                f"{self.log_prefix} Error finding execution for {a2a_task_id}: {e}",
                exc_info=True,
            )
            return None

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
                if result.status and result.status.message:
                    # Extract text from status message
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
                
                # Also check history for PERSISTENT sessions
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
                task_state = a2a.get_task_status(result)
                if task_state:
                    result_summary["task_status"] = str(task_state)
                
                # Extract artifacts from task
                task_artifacts = a2a.get_task_artifacts(result)
                if task_artifacts:
                    for artifact in task_artifacts:
                        artifact_id = a2a.get_artifact_id(artifact)
                        if artifact_id:
                            # Create artifact object with viewable API URI
                            artifact_obj = {
                                "name": artifact_id,
                                "uri": f"artifact://{artifact_id}"
                            }
                            if not any(a.get("name") == artifact_id for a in artifacts if isinstance(a, dict)):
                                artifacts.append(artifact_obj)

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