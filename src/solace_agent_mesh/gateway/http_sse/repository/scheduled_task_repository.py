"""
Scheduled task repository implementation using SQLAlchemy.
"""

from typing import List, Optional
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session as DBSession, joinedload

from ..shared.pagination import PaginationParams
from ..shared.types import UserId
from ..shared import now_epoch_ms
from .models import (
    ScheduledTaskModel,
    ScheduledTaskExecutionModel,
    ScheduleType,
    ExecutionStatus,
)


class ScheduledTaskRepository:
    """Repository for scheduled task operations."""

    def create_task(
        self,
        session: DBSession,
        task_data: dict,
    ) -> ScheduledTaskModel:
        """
        Create a new scheduled task.

        Args:
            session: Database session
            task_data: Dictionary with task data

        Returns:
            Created ScheduledTaskModel
        """
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
        """
        Update an existing scheduled task.

        Args:
            session: Database session
            task_id: Task ID to update
            update_data: Dictionary with fields to update

        Returns:
            Updated ScheduledTaskModel or None if not found
        """
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return None

        # Update fields
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
        """
        Find a scheduled task by ID.

        Args:
            session: Database session
            task_id: Task ID
            user_id: Optional user ID for access control

        Returns:
            ScheduledTaskModel or None if not found
        """
        query = select(ScheduledTaskModel).where(
            ScheduledTaskModel.id == task_id,
            ScheduledTaskModel.deleted_at == None,
        )

        if user_id:
            query = query.where(
                or_(
                    ScheduledTaskModel.user_id == user_id,
                    ScheduledTaskModel.user_id == None,  # Namespace-level tasks
                )
            )

        result = session.execute(query).scalar_one_or_none()
        return result

    def find_by_namespace(
        self,
        session: DBSession,
        namespace: str,
        user_id: Optional[str] = None,
        include_namespace_tasks: bool = True,
        enabled_only: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> List[ScheduledTaskModel]:
        """
        Find scheduled tasks by namespace.

        Args:
            session: Database session
            namespace: Namespace to filter by
            user_id: Optional user ID to filter user-specific tasks
            include_namespace_tasks: Include namespace-level tasks (user_id=NULL)
            enabled_only: Only return enabled tasks
            pagination: Optional pagination parameters

        Returns:
            List of ScheduledTaskModel
        """
        query = select(ScheduledTaskModel).where(
            ScheduledTaskModel.namespace == namespace,
            ScheduledTaskModel.deleted_at == None,
        )

        # User filtering
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

        # Order by next run time
        query = query.order_by(ScheduledTaskModel.next_run_at.asc())

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        result = session.execute(query).scalars().all()
        return list(result)

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

        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        return session.execute(count_query).scalar()

    def soft_delete(
        self,
        session: DBSession,
        task_id: str,
        deleted_by: str,
    ) -> bool:
        """
        Soft delete a scheduled task.

        Args:
            session: Database session
            task_id: Task ID to delete
            deleted_by: User ID performing the deletion

        Returns:
            True if deleted, False if not found
        """
        task = session.get(ScheduledTaskModel, task_id)
        if not task or task.deleted_at:
            return False

        task.deleted_at = now_epoch_ms()
        task.deleted_by = deleted_by
        task.enabled = False  # Also disable the task
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

        result = session.execute(query).scalars().all()
        return list(result)

    def count_executions_by_task(
        self,
        session: DBSession,
        task_id: str,
    ) -> int:
        """Count executions for a specific task."""
        from sqlalchemy import func
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
        """
        Find recent executions across all tasks in a namespace.

        Args:
            session: Database session
            namespace: Namespace to filter by
            user_id: Optional user ID for filtering
            limit: Maximum number of executions to return

        Returns:
            List of recent executions
        """
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

        query = query.order_by(ScheduledTaskExecutionModel.scheduled_for.desc()).limit(
            limit
        )

        result = session.execute(query).scalars().all()
        return list(result)

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

        result = session.execute(query).scalars().all()
        return list(result)

    def cleanup_old_executions(
        self,
        session: DBSession,
        cutoff_time_ms: int,
        batch_size: int = 1000,
    ) -> int:
        """
        Delete old execution records.

        Args:
            session: Database session
            cutoff_time_ms: Delete executions older than this (epoch ms)
            batch_size: Number of records to delete per batch

        Returns:
            Total number of executions deleted
        """
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