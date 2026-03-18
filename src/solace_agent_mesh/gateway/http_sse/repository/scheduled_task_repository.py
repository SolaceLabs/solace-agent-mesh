"""
Scheduled task repository implementation using SQLAlchemy.
"""

from typing import List, Optional
from sqlalchemy import and_, or_, select, func
from sqlalchemy.orm import Session as DBSession

from ..shared.pagination import PaginationParams
from ..shared import now_epoch_ms
from .models import (
    ScheduledTaskModel,
    ScheduledTaskExecutionModel,
    ExecutionStatus,
)


class ScheduledTaskRepository:
    """Repository for scheduled task operations."""

    def create_task(
        self,
        session: DBSession,
        task_data: dict,
    ) -> ScheduledTaskModel:
        """Create a new scheduled task with app-level uniqueness check."""
        # Check for existing active task with same (namespace, name)
        existing = session.execute(
            select(ScheduledTaskModel).where(
                ScheduledTaskModel.namespace == task_data.get("namespace"),
                ScheduledTaskModel.name == task_data.get("name"),
                ScheduledTaskModel.deleted_at == None,
            )
        ).scalar_one_or_none()

        if existing:
            raise ValueError(
                f"An active scheduled task with name '{task_data['name']}' "
                f"already exists in namespace '{task_data['namespace']}'"
            )

        task = ScheduledTaskModel(**task_data)
        session.add(task)
        session.flush()
        session.refresh(task)
        return task

    def update_task(
        self,
        session: DBSession,
        task_id: str,
        update_data: dict,
    ) -> Optional[ScheduledTaskModel]:
        """Update an existing scheduled task."""
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return None

        for key, value in update_data.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = now_epoch_ms()
        session.flush()
        session.refresh(task)
        return task

    def find_by_id(
        self,
        session: DBSession,
        task_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[ScheduledTaskModel]:
        """Find a scheduled task by ID."""
        query = select(ScheduledTaskModel).where(
            ScheduledTaskModel.id == task_id,
            ScheduledTaskModel.deleted_at == None,
        )

        if user_id:
            query = query.where(
                or_(
                    ScheduledTaskModel.user_id == user_id,
                    ScheduledTaskModel.user_id == None,
                )
            )

        return session.execute(query).scalar_one_or_none()

    def find_by_namespace(
        self,
        session: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        include_namespace_tasks: bool = True,
        enabled_only: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> List[ScheduledTaskModel]:
        """Find scheduled tasks by namespace."""
        query = select(ScheduledTaskModel).where(
            ScheduledTaskModel.namespace == namespace,
            ScheduledTaskModel.deleted_at == None,
        )

        if user_id:
            if include_namespace_tasks:
                query = query.where(
                    or_(
                        ScheduledTaskModel.user_id == user_id,
                        ScheduledTaskModel.user_id == None,
                    )
                )
            else:
                query = query.where(ScheduledTaskModel.user_id == user_id)

        if enabled_only:
            query = query.where(ScheduledTaskModel.enabled == True)

        query = query.order_by(ScheduledTaskModel.next_run_at.asc())

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        return list(session.execute(query).scalars().all())

    def count_by_namespace(
        self,
        session: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        include_namespace_tasks: bool = True,
        enabled_only: bool = False,
    ) -> int:
        """Count scheduled tasks by namespace."""
        query = select(ScheduledTaskModel).where(
            ScheduledTaskModel.namespace == namespace,
            ScheduledTaskModel.deleted_at == None,
        )

        if user_id:
            if include_namespace_tasks:
                query = query.where(
                    or_(
                        ScheduledTaskModel.user_id == user_id,
                        ScheduledTaskModel.user_id == None,
                    )
                )
            else:
                query = query.where(ScheduledTaskModel.user_id == user_id)

        if enabled_only:
            query = query.where(ScheduledTaskModel.enabled == True)

        count_query = select(func.count()).select_from(query.subquery())
        return session.execute(count_query).scalar()

    def soft_delete(
        self,
        session: DBSession,
        task_id: str,
        deleted_by: str,
    ) -> bool:
        """Soft delete a scheduled task."""
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return False

        task.deleted_at = now_epoch_ms()
        task.deleted_by = deleted_by
        task.enabled = False
        session.flush()
        return True

    def enable_task(
        self,
        session: DBSession,
        task_id: str,
    ) -> Optional[ScheduledTaskModel]:
        """Enable a scheduled task."""
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return None

        task.enabled = True
        task.updated_at = now_epoch_ms()
        session.flush()
        session.refresh(task)
        return task

    def disable_task(
        self,
        session: DBSession,
        task_id: str,
    ) -> Optional[ScheduledTaskModel]:
        """Disable a scheduled task."""
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return None

        task.enabled = False
        task.updated_at = now_epoch_ms()
        session.flush()
        session.refresh(task)
        return task

    # Execution methods

    def create_execution(
        self,
        session: DBSession,
        execution_data: dict,
    ) -> ScheduledTaskExecutionModel:
        """Create a new task execution record."""
        execution = ScheduledTaskExecutionModel(**execution_data)
        session.add(execution)
        session.flush()
        session.refresh(execution)
        return execution

    def update_execution(
        self,
        session: DBSession,
        execution_id: str,
        update_data: dict,
    ) -> Optional[ScheduledTaskExecutionModel]:
        """Update an execution record."""
        execution = session.get(ScheduledTaskExecutionModel, execution_id)
        if not execution:
            return None

        for key, value in update_data.items():
            if hasattr(execution, key):
                setattr(execution, key, value)

        session.flush()
        session.refresh(execution)
        return execution

    def find_execution_by_id(
        self,
        session: DBSession,
        execution_id: str,
    ) -> Optional[ScheduledTaskExecutionModel]:
        """Find an execution by ID."""
        return session.get(ScheduledTaskExecutionModel, execution_id)

    def find_execution_by_a2a_task_id(
        self,
        session: DBSession,
        a2a_task_id: str,
    ) -> Optional[ScheduledTaskExecutionModel]:
        """Find an execution by A2A task ID (for cross-linking)."""
        return session.execute(
            select(ScheduledTaskExecutionModel).where(
                ScheduledTaskExecutionModel.a2a_task_id == a2a_task_id,
            )
        ).scalar_one_or_none()

    def find_executions_by_task(
        self,
        session: DBSession,
        task_id: str,
        pagination: Optional[PaginationParams] = None,
    ) -> List[ScheduledTaskExecutionModel]:
        """Find all executions for a specific task."""
        query = (
            select(ScheduledTaskExecutionModel)
            .where(ScheduledTaskExecutionModel.scheduled_task_id == task_id)
            .order_by(ScheduledTaskExecutionModel.scheduled_for.desc())
        )

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        return list(session.execute(query).scalars().all())

    def count_executions_by_task(
        self,
        session: DBSession,
        task_id: str,
    ) -> int:
        """Count executions for a specific task."""
        query = select(func.count()).where(
            ScheduledTaskExecutionModel.scheduled_task_id == task_id
        )
        return session.execute(query).scalar()

    def find_recent_executions(
        self,
        session: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ScheduledTaskExecutionModel]:
        """Find recent executions across all tasks in a namespace."""
        query = (
            select(ScheduledTaskExecutionModel)
            .join(ScheduledTaskModel)
            .where(ScheduledTaskModel.namespace == namespace)
        )

        if user_id:
            query = query.where(
                or_(
                    ScheduledTaskModel.user_id == user_id,
                    ScheduledTaskModel.user_id == None,
                )
            )

        query = query.order_by(ScheduledTaskExecutionModel.scheduled_for.desc()).limit(limit)
        return list(session.execute(query).scalars().all())

    def find_running_executions(
        self,
        session: DBSession,
        namespace: str,
    ) -> List[ScheduledTaskExecutionModel]:
        """Find all currently running executions in a namespace."""
        query = (
            select(ScheduledTaskExecutionModel)
            .join(ScheduledTaskModel)
            .where(
                ScheduledTaskModel.namespace == namespace,
                ScheduledTaskExecutionModel.status == ExecutionStatus.RUNNING,
            )
            .order_by(ScheduledTaskExecutionModel.started_at.desc())
        )
        return list(session.execute(query).scalars().all())

    def delete_oldest_executions(
        self,
        session: DBSession,
        task_id: str,
        keep_count: int = 100,
    ) -> int:
        """Delete oldest executions for a task, keeping only keep_count most recent."""
        # Get IDs to keep (most recent)
        keep_ids_query = (
            select(ScheduledTaskExecutionModel.id)
            .where(ScheduledTaskExecutionModel.scheduled_task_id == task_id)
            .order_by(ScheduledTaskExecutionModel.scheduled_for.desc())
            .limit(keep_count)
        )
        keep_ids = [row[0] for row in session.execute(keep_ids_query).all()]

        if not keep_ids:
            return 0

        # Delete all others
        deleted = (
            session.query(ScheduledTaskExecutionModel)
            .filter(
                ScheduledTaskExecutionModel.scheduled_task_id == task_id,
                ~ScheduledTaskExecutionModel.id.in_(keep_ids),
            )
            .delete(synchronize_session=False)
        )
        return deleted

    def cleanup_old_executions(
        self,
        session: DBSession,
        cutoff_time_ms: int,
        batch_size: int = 1000,
    ) -> int:
        """Delete old execution records."""
        total_deleted = 0

        while True:
            execution_ids = (
                session.query(ScheduledTaskExecutionModel.id)
                .filter(ScheduledTaskExecutionModel.scheduled_for < cutoff_time_ms)
                .limit(batch_size)
                .all()
            )

            if not execution_ids:
                break

            ids = [exec_id[0] for exec_id in execution_ids]

            deleted_count = (
                session.query(ScheduledTaskExecutionModel)
                .filter(ScheduledTaskExecutionModel.id.in_(ids))
                .delete(synchronize_session=False)
            )

            session.commit()
            total_deleted += deleted_count

            if deleted_count < batch_size:
                break

        return total_deleted
