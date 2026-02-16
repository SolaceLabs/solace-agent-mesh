"""
Checkpoint service for stateless agent operation.

Handles persistence and retrieval of task coordination state when agents
are paused waiting for peer responses. Uses the ADK session database.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker, Session

from .checkpoint_models import (
    AgentPausedTask,
    AgentPeerSubTask,
    AgentParallelInvocation,
)

log = logging.getLogger(__name__)


class CheckpointService:
    """Database operations for stateless agent checkpointing."""

    def __init__(self, engine):
        """
        Initialize with a SQLAlchemy engine (shared with ADK session service).

        Args:
            engine: SQLAlchemy engine connected to the ADK session database.
        """
        self.engine = engine
        self.SessionFactory = sessionmaker(bind=engine)

    def _get_session(self) -> Session:
        return self.SessionFactory()

    def checkpoint_task(
        self,
        task_context: "TaskExecutionContext",
        agent_name: str,
    ) -> None:
        """
        Persist task state to DB in a single transaction.

        Writes the paused task record, all peer sub-task entries,
        and parallel invocation tracking state.
        """
        checkpoint_data = task_context.to_checkpoint_dict()
        now = time.time()

        session = self._get_session()
        try:
            # 1. Insert paused task record
            paused_task = AgentPausedTask(
                logical_task_id=checkpoint_data["task_id"],
                agent_name=agent_name,
                a2a_context=json.dumps(checkpoint_data["a2a_context"]),
                effective_session_id=checkpoint_data["a2a_context"].get(
                    "effective_session_id"
                ),
                user_id=checkpoint_data["a2a_context"].get("user_id"),
                current_invocation_id=checkpoint_data.get("current_invocation_id"),
                produced_artifacts=json.dumps(
                    checkpoint_data.get("produced_artifacts", [])
                ),
                artifact_signals_to_return=json.dumps(
                    checkpoint_data.get("artifact_signals_to_return", [])
                ),
                response_buffer=checkpoint_data.get("run_based_response_buffer", ""),
                flags=json.dumps(checkpoint_data.get("flags", {})),
                security_context=json.dumps(
                    checkpoint_data.get("security_context", {})
                ),
                token_usage=json.dumps(checkpoint_data.get("token_usage", {})),
                checkpointed_at=now,
            )
            session.add(paused_task)

            # 2. Insert peer sub-task entries
            for sub_task_id, correlation_data in checkpoint_data.get(
                "active_peer_sub_tasks", {}
            ).items():
                timeout_sec = correlation_data.get("timeout_seconds")
                timeout_deadline = now + timeout_sec if timeout_sec else None
                peer_sub_task = AgentPeerSubTask(
                    sub_task_id=sub_task_id,
                    logical_task_id=checkpoint_data["task_id"],
                    invocation_id=correlation_data.get("invocation_id", ""),
                    correlation_data=json.dumps(correlation_data),
                    timeout_deadline=timeout_deadline,
                    created_at=now,
                )
                session.add(peer_sub_task)

            # 3. Insert parallel invocation tracking
            for invocation_id, inv_state in checkpoint_data.get(
                "parallel_tool_calls", {}
            ).items():
                parallel_inv = AgentParallelInvocation(
                    logical_task_id=checkpoint_data["task_id"],
                    invocation_id=invocation_id,
                    total_expected=inv_state.get("total", 0),
                    completed_count=inv_state.get("completed", 0),
                    results=json.dumps(inv_state.get("results", [])),
                )
                session.add(parallel_inv)

            session.commit()
            log.info(
                "Checkpointed task %s with %d peer sub-tasks and %d parallel invocations",
                checkpoint_data["task_id"],
                len(checkpoint_data.get("active_peer_sub_tasks", {})),
                len(checkpoint_data.get("parallel_tool_calls", {})),
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def claim_peer_sub_task(self, sub_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Atomically claim a peer sub-task completion.

        Deletes the row and returns its correlation_data if it exists.
        Returns None if already claimed (row doesn't exist).
        This is the distributed equivalent of dict.pop().
        """
        session = self._get_session()
        try:
            row = (
                session.query(AgentPeerSubTask)
                .filter(AgentPeerSubTask.sub_task_id == sub_task_id)
                .with_for_update()
                .first()
            )
            if row is None:
                return None

            correlation_data = json.loads(row.correlation_data)
            # Include the logical_task_id and invocation_id from the row
            # so callers don't need a separate lookup
            correlation_data["logical_task_id"] = row.logical_task_id
            correlation_data["invocation_id"] = row.invocation_id

            session.delete(row)
            session.commit()
            return correlation_data
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_parallel_result(
        self,
        logical_task_id: str,
        invocation_id: str,
        result: Dict[str, Any],
    ) -> Tuple[int, int]:
        """
        Atomically increment completion counter and append result.

        Returns (completed_count, total_expected) after the update.
        """
        session = self._get_session()
        try:
            row = (
                session.query(AgentParallelInvocation)
                .filter(
                    AgentParallelInvocation.logical_task_id == logical_task_id,
                    AgentParallelInvocation.invocation_id == invocation_id,
                )
                .with_for_update()
                .first()
            )
            if row is None:
                log.error(
                    "No parallel invocation record found for task=%s invocation=%s",
                    logical_task_id,
                    invocation_id,
                )
                return (0, 0)

            # Append result to the JSON array
            current_results = json.loads(row.results)
            current_results.append(result)
            row.results = json.dumps(current_results)
            row.completed_count = row.completed_count + 1

            completed = row.completed_count
            total = row.total_expected

            session.commit()
            return (completed, total)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_parallel_results(
        self, logical_task_id: str, invocation_id: str
    ) -> List[Dict[str, Any]]:
        """Get accumulated results for a parallel invocation."""
        session = self._get_session()
        try:
            row = (
                session.query(AgentParallelInvocation)
                .filter(
                    AgentParallelInvocation.logical_task_id == logical_task_id,
                    AgentParallelInvocation.invocation_id == invocation_id,
                )
                .first()
            )
            if row is None:
                return []
            return json.loads(row.results)
        finally:
            session.close()

    def get_peer_sub_task(self, sub_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Non-destructive read of a peer sub-task's correlation data.
        Used for intermediate status updates (timeout reset path).
        """
        session = self._get_session()
        try:
            row = (
                session.query(AgentPeerSubTask)
                .filter(AgentPeerSubTask.sub_task_id == sub_task_id)
                .first()
            )
            if row is None:
                return None
            correlation_data = json.loads(row.correlation_data)
            correlation_data["logical_task_id"] = row.logical_task_id
            correlation_data["invocation_id"] = row.invocation_id
            return correlation_data
        finally:
            session.close()

    def reset_timeout_deadline(self, sub_task_id: str, new_deadline: float) -> bool:
        """
        Reset the timeout deadline for a peer sub-task.
        Returns True if the row was found and updated.
        """
        session = self._get_session()
        try:
            row = (
                session.query(AgentPeerSubTask)
                .filter(AgentPeerSubTask.sub_task_id == sub_task_id)
                .first()
            )
            if row is None:
                return False
            row.timeout_deadline = new_deadline
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def restore_task(self, logical_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a checkpointed task's state for reconstruction.
        Returns a dict suitable for TaskExecutionContext.from_checkpoint_dict().
        """
        session = self._get_session()
        try:
            row = (
                session.query(AgentPausedTask)
                .filter(AgentPausedTask.logical_task_id == logical_task_id)
                .first()
            )
            if row is None:
                return None

            return {
                "task_id": row.logical_task_id,
                "a2a_context": json.loads(row.a2a_context),
                "current_invocation_id": row.current_invocation_id,
                "produced_artifacts": json.loads(row.produced_artifacts or "[]"),
                "artifact_signals_to_return": json.loads(
                    row.artifact_signals_to_return or "[]"
                ),
                "run_based_response_buffer": row.response_buffer or "",
                "flags": json.loads(row.flags or "{}"),
                "security_context": json.loads(row.security_context or "{}"),
                "token_usage": json.loads(row.token_usage or "{}"),
            }
        finally:
            session.close()

    def cleanup_task(self, logical_task_id: str) -> None:
        """
        Delete all checkpoint records for a completed/resumed task.
        CASCADE on foreign keys handles peer_sub_tasks and parallel_invocations.
        """
        session = self._get_session()
        try:
            # Delete peer sub-tasks and parallel invocations explicitly
            # in case the DB doesn't support CASCADE (e.g., SQLite without
            # PRAGMA foreign_keys=ON)
            session.query(AgentPeerSubTask).filter(
                AgentPeerSubTask.logical_task_id == logical_task_id
            ).delete()
            session.query(AgentParallelInvocation).filter(
                AgentParallelInvocation.logical_task_id == logical_task_id
            ).delete()
            session.query(AgentPausedTask).filter(
                AgentPausedTask.logical_task_id == logical_task_id
            ).delete()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_peer_sub_tasks_for_task(
        self, logical_task_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all peer sub-tasks for a given task.
        Used for cancellation — need to send cancel requests to all tracked peers.
        """
        session = self._get_session()
        try:
            rows = (
                session.query(AgentPeerSubTask)
                .filter(AgentPeerSubTask.logical_task_id == logical_task_id)
                .all()
            )
            return [
                {
                    "sub_task_id": row.sub_task_id,
                    "invocation_id": row.invocation_id,
                    "correlation_data": json.loads(row.correlation_data),
                }
                for row in rows
            ]
        finally:
            session.close()

    def sweep_expired_timeouts(
        self, agent_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find peer sub-tasks with expired timeout deadlines.

        Returns a list of dicts with sub_task_id and logical_task_id
        for the sweeper to process. Each must still be individually
        claimed via claim_peer_sub_task() for atomicity.
        """
        now = time.time()
        session = self._get_session()
        try:
            rows = (
                session.query(AgentPeerSubTask)
                .join(
                    AgentPausedTask,
                    AgentPeerSubTask.logical_task_id
                    == AgentPausedTask.logical_task_id,
                )
                .filter(
                    AgentPausedTask.agent_name == agent_name,
                    AgentPeerSubTask.timeout_deadline.isnot(None),
                    AgentPeerSubTask.timeout_deadline < now,
                )
                .limit(limit)
                .all()
            )
            return [
                {
                    "sub_task_id": row.sub_task_id,
                    "logical_task_id": row.logical_task_id,
                    "invocation_id": row.invocation_id,
                }
                for row in rows
            ]
        finally:
            session.close()
