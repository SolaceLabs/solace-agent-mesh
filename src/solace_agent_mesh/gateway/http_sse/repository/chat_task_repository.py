"""
ChatTask repository implementation using SQLAlchemy.
"""

from typing import List, Optional

from sqlalchemy.orm import Session as DBSession

from ..shared import now_epoch_ms
from ..shared.types import SessionId, UserId
from .entities import ChatTask
from .interfaces import IChatTaskRepository
from .models import ChatTaskModel


class ChatTaskRepository(IChatTaskRepository):
    """SQLAlchemy implementation of chat task repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def save(self, task: ChatTask) -> ChatTask:
        """Save or update a chat task (upsert)."""
        existing = self.db.query(ChatTaskModel).filter(
            ChatTaskModel.id == task.id
        ).first()

        if existing:
            # Update existing task
            existing.user_message = task.user_message
            existing.message_bubbles = task.message_bubbles
            existing.task_metadata = task.task_metadata
            existing.updated_time = now_epoch_ms()
        else:
            # Create new task
            model = ChatTaskModel(
                id=task.id,
                session_id=task.session_id,
                user_id=task.user_id,
                user_message=task.user_message,
                message_bubbles=task.message_bubbles,
                task_metadata=task.task_metadata,
                created_time=task.created_time,
                updated_time=task.updated_time
            )
            self.db.add(model)

        self.db.commit()

        # Reload to get updated values
        model = self.db.query(ChatTaskModel).filter(
            ChatTaskModel.id == task.id
        ).first()

        return self._model_to_entity(model)

    def find_by_session(
        self,
        session_id: SessionId,
        user_id: UserId
    ) -> List[ChatTask]:
        """Find all tasks for a session."""
        models = self.db.query(ChatTaskModel).filter(
            ChatTaskModel.session_id == session_id,
            ChatTaskModel.user_id == user_id
        ).order_by(ChatTaskModel.created_time.asc()).all()

        return [self._model_to_entity(m) for m in models]

    def find_by_id(
        self,
        task_id: str,
        user_id: UserId
    ) -> Optional[ChatTask]:
        """Find a specific task."""
        model = self.db.query(ChatTaskModel).filter(
            ChatTaskModel.id == task_id,
            ChatTaskModel.user_id == user_id
        ).first()

        return self._model_to_entity(model) if model else None

    def delete_by_session(self, session_id: SessionId) -> bool:
        """Delete all tasks for a session."""
        result = self.db.query(ChatTaskModel).filter(
            ChatTaskModel.session_id == session_id
        ).delete()
        self.db.commit()
        return result > 0

    def _model_to_entity(self, model: ChatTaskModel) -> ChatTask:
        """Convert SQLAlchemy model to domain entity."""
        return ChatTask.model_validate(model)
