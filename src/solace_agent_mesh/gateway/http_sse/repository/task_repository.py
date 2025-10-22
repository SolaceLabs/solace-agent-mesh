"""
Task repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.pagination import PaginationParams
from ..shared.types import UserId
from .entities import Task, TaskEvent
from .interfaces import ITaskRepository
from .models import TaskEventModel, TaskModel


class TaskRepository(ITaskRepository):
    """SQLAlchemy implementation of task repository."""

    def save_task(self, session: DBSession, task: Task) -> Task:
        """Create or update a task."""
        model = session.query(TaskModel).filter(TaskModel.id == task.id).first()

        if model:
            model.end_time = task.end_time
            model.status = task.status
            model.total_input_tokens = task.total_input_tokens
            model.total_output_tokens = task.total_output_tokens
            model.total_cached_input_tokens = task.total_cached_input_tokens
            model.token_usage_details = task.token_usage_details
        else:
            model = TaskModel(
                id=task.id,
                user_id=task.user_id,
                start_time=task.start_time,
                end_time=task.end_time,
                status=task.status,
                initial_request_text=task.initial_request_text,
                total_input_tokens=task.total_input_tokens,
                total_output_tokens=task.total_output_tokens,
                total_cached_input_tokens=task.total_cached_input_tokens,
                token_usage_details=task.token_usage_details,
            )
            session.add(model)

        session.flush()
        session.refresh(model)
        return self._task_model_to_entity(model)

    def save_event(self, session: DBSession, event: TaskEvent) -> TaskEvent:
        """Save a task event."""
        model = TaskEventModel(
            id=event.id,
            task_id=event.task_id,
            user_id=event.user_id,
            created_time=event.created_time,
            topic=event.topic,
            direction=event.direction,
            payload=event.payload,
        )
        session.add(model)
        session.flush()
        session.refresh(model)
        return self._event_model_to_entity(model)

    def find_by_id(self, session: DBSession, task_id: str) -> Task | None:
        """Find a task by its ID."""
        model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        return self._task_model_to_entity(model) if model else None

    def find_by_id_with_events(
        self, session: DBSession, task_id: str
    ) -> tuple[Task, list[TaskEvent]] | None:
        """Find a task with all its events."""
        task_model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task_model:
            return None

        event_models = (
            session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .order_by(TaskEventModel.created_time.asc())
            .all()
        )

        task = self._task_model_to_entity(task_model)
        events = [self._event_model_to_entity(model) for model in event_models]
        return task, events

    def search(
        self,
        session: DBSession,
        user_id: UserId,
        start_date: int | None = None,
        end_date: int | None = None,
        pagination: PaginationParams | None = None,
    ) -> list[Task]:
        """Search for tasks with filters."""
        query = session.query(TaskModel)
        if user_id != "*":
            query = query.filter(TaskModel.user_id == user_id)

        if start_date:
            query = query.filter(TaskModel.start_time >= start_date)
        if end_date:
            query = query.filter(TaskModel.start_time <= end_date)

        query = query.order_by(TaskModel.start_time.desc())

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        models = query.all()
        return [self._task_model_to_entity(model) for model in models]

    def delete_tasks_older_than(self, session: DBSession, cutoff_time_ms: int, batch_size: int) -> int:
        """
        Delete tasks (and their events via cascade) older than the cutoff time.
        Uses batch deletion to avoid long-running transactions.

        Args:
            cutoff_time_ms: Epoch milliseconds - tasks with start_time before this will be deleted
            batch_size: Number of tasks to delete per batch

        Returns:
            Total number of tasks deleted

        Note:
            This method commits each batch internally due to the nature of batch processing.
            Each batch is an atomic operation to prevent long-running transactions.
        """
        total_deleted = 0

        while True:
            task_ids_to_delete = (
                session.query(TaskModel.id)
                .filter(TaskModel.start_time < cutoff_time_ms)
                .limit(batch_size)
                .all()
            )

            if not task_ids_to_delete:
                break

            ids = [task_id[0] for task_id in task_ids_to_delete]

            deleted_count = (
                session.query(TaskModel)
                .filter(TaskModel.id.in_(ids))
                .delete(synchronize_session=False)
            )

            session.commit()
            total_deleted += deleted_count

            if deleted_count < batch_size:
                break

        return total_deleted

    def _task_model_to_entity(self, model: TaskModel) -> Task:
        """Convert SQLAlchemy task model to domain entity."""
        return Task.model_validate(model)

    def _event_model_to_entity(self, model: TaskEventModel) -> TaskEvent:
        """Convert SQLAlchemy event model to domain entity."""
        return TaskEvent.model_validate(model)
