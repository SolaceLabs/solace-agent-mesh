"""
CRUD service layer for scheduled tasks.
Sits between the router and repository, following the SessionService pattern.
Manages transactions, business logic, and scheduler coordination.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session as DBSession

from ..repository.scheduled_task_repository import ScheduledTaskRepository
from ..shared import now_epoch_ms
from ..shared.pagination import PaginationParams

log = logging.getLogger(__name__)


class ScheduledTaskService:
    """Service layer for scheduled task CRUD operations."""

    def __init__(self, scheduler_service=None):
        self.repo = ScheduledTaskRepository()
        self.scheduler_service = scheduler_service

    @property
    def namespace(self) -> str:
        """Expose scheduler namespace without requiring callers to reach through."""
        return self.scheduler_service.namespace if self.scheduler_service else ""

    def create_task(
        self,
        db: DBSession,
        request_data: Dict[str, Any],
        namespace: str,
        user_id: str,
        user_level: bool = True,
    ) -> Any:
        """Create a new scheduled task and optionally schedule it."""
        task_data = {
            "id": str(uuid.uuid4()),
            **request_data,
            "namespace": namespace,
            "user_id": user_id if user_level else None,
            "created_by": user_id,
            "source": "ui",
            "created_at": now_epoch_ms(),
            "updated_at": now_epoch_ms(),
        }

        task = self.repo.create_task(db, task_data)
        db.commit()
        return task

    async def schedule_task(self, task, fire_immediately: bool = False) -> None:
        """Schedule a task in APScheduler (public interface)."""
        if self.scheduler_service:
            await self.scheduler_service.schedule_task(task, fire_immediately=fire_immediately)

    async def unschedule_task(self, task_id: str) -> None:
        """Remove a task from APScheduler (public interface)."""
        if self.scheduler_service:
            await self.scheduler_service.unschedule_task(task_id)

    def get_task(
        self,
        db: DBSession,
        task_id: str,
        user_id: Optional[str] = None,
    ) -> Any:
        """Get a single task, optionally filtered by user ownership."""
        return self.repo.find_by_id(db, task_id, user_id=user_id)

    def list_tasks(
        self,
        db: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        include_namespace_tasks: bool = True,
        enabled_only: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> tuple:
        """List tasks with pagination. Returns (tasks, total_count)."""
        tasks = self.repo.find_by_namespace(
            db,
            namespace=namespace,
            user_id=user_id,
            include_namespace_tasks=include_namespace_tasks,
            enabled_only=enabled_only,
            pagination=pagination,
        )
        total = self.repo.count_by_namespace(
            db,
            namespace=namespace,
            user_id=user_id,
            include_namespace_tasks=include_namespace_tasks,
            enabled_only=enabled_only,
        )
        return tasks, total

    def update_task(
        self,
        db: DBSession,
        task_id: str,
        update_data: Dict[str, Any],
    ) -> Any:
        """Update a task and commit."""
        updated = self.repo.update_task(db, task_id, update_data)
        db.commit()
        return updated

    async def update_and_reschedule(
        self,
        db: DBSession,
        task_id: str,
        update_data: Dict[str, Any],
    ) -> Any:
        """Update a task. If schedule fields changed and task is enabled, reschedule."""
        updated_task = self.update_task(db, task_id, update_data)

        schedule_changed = any(
            k in update_data for k in ("schedule_type", "schedule_expression", "timezone")
        )
        if schedule_changed and updated_task and updated_task.enabled:
            try:
                await self.unschedule_task(task_id)
                await self.schedule_task(updated_task)
            except Exception as e:
                log.error("Failed to reschedule task %s: %s", task_id, e)

        return updated_task

    def delete_task(
        self,
        db: DBSession,
        task_id: str,
        deleted_by: str,
    ) -> bool:
        """Soft delete a task and commit."""
        deleted = self.repo.soft_delete(db, task_id, deleted_by)
        db.commit()
        return deleted

    def enable_task(self, db: DBSession, task_id: str) -> Any:
        """Enable a task and commit."""
        task = self.repo.enable_task(db, task_id)
        db.commit()
        return task

    def disable_task(self, db: DBSession, task_id: str) -> Any:
        """Disable a task and commit."""
        task = self.repo.disable_task(db, task_id)
        db.commit()
        return task

    def get_task_executions(
        self,
        db: DBSession,
        task_id: str,
        pagination: Optional[PaginationParams] = None,
        scheduled_after: Optional[int] = None,
        scheduled_before: Optional[int] = None,
    ) -> tuple:
        """Get executions for a task, optionally bounded by `scheduled_for`
        in epoch ms. Returns (executions, total_count)."""
        executions = self.repo.find_executions_by_task(
            db, task_id, pagination, scheduled_after=scheduled_after, scheduled_before=scheduled_before
        )
        total = self.repo.count_executions_by_task(
            db, task_id, scheduled_after=scheduled_after, scheduled_before=scheduled_before
        )
        return executions, total

    def get_recent_executions(
        self,
        db: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List:
        """Get recent executions across all tasks in a namespace."""
        return self.repo.find_recent_executions(db, namespace, user_id=user_id, limit=limit)

    def get_execution_by_a2a_task_id(self, db: DBSession, a2a_task_id: str) -> Any:
        """Find an execution by its A2A task ID."""
        return self.repo.find_execution_by_a2a_task_id(db, a2a_task_id)

    def get_execution(self, db: DBSession, execution_id: str) -> Any:
        """Find a single execution by id."""
        return self.repo.find_execution_by_id(db, execution_id)

    def delete_execution(self, db: DBSession, execution_id: str) -> bool:
        """Hard delete a single execution and commit."""
        deleted = self.repo.delete_execution(db, execution_id)
        db.commit()
        return deleted
