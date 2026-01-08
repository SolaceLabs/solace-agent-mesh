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

    def save(self, session: DBSession, task: ChatTask) -> ChatTask:
        """Save or update a chat task (upsert)."""
        existing = session.query(ChatTaskModel).filter(
            ChatTaskModel.id == task.id
        ).first()

        if existing:
            # Update existing task - store strings directly
            existing.user_message = task.user_message
            existing.message_bubbles = task.message_bubbles  # Already a string
            existing.task_metadata = task.task_metadata      # Already a string
            existing.updated_time = now_epoch_ms()
        else:
            # Create new task - store strings directly
            model = ChatTaskModel(
                id=task.id,
                session_id=task.session_id,
                user_id=task.user_id,
                user_message=task.user_message,
                message_bubbles=task.message_bubbles,  # Already a string
                task_metadata=task.task_metadata,      # Already a string
                created_time=task.created_time,
                updated_time=task.updated_time
            )
            session.add(model)

        session.flush()

        # Reload to get updated values
        model = session.query(ChatTaskModel).filter(
            ChatTaskModel.id == task.id
        ).first()

        return self._model_to_entity(model)

    def find_by_session(
        self,
        session: DBSession,
        session_id: SessionId,
        user_id: UserId
    ) -> List[ChatTask]:
        """Find all tasks for a session."""
        models = session.query(ChatTaskModel).filter(
            ChatTaskModel.session_id == session_id,
            ChatTaskModel.user_id == user_id
        ).order_by(ChatTaskModel.created_time.asc()).all()

        return [self._model_to_entity(m) for m in models]

    def find_by_id(
        self,
        session: DBSession,
        task_id: str,
        user_id: UserId
    ) -> Optional[ChatTask]:
        """Find a specific task."""
        model = session.query(ChatTaskModel).filter(
            ChatTaskModel.id == task_id,
            ChatTaskModel.user_id == user_id
        ).first()

        return self._model_to_entity(model) if model else None

    def delete_by_session(self, session: DBSession, session_id: SessionId) -> bool:
        """Delete all tasks for a session."""
        result = session.query(ChatTaskModel).filter(
            ChatTaskModel.session_id == session_id
        ).delete()
        session.flush()
        return result > 0

    def _model_to_entity(self, model: ChatTaskModel) -> ChatTask:
        """Convert SQLAlchemy model to domain entity."""
        # No deserialization - just pass strings through
        return ChatTask(
            id=model.id,
            session_id=model.session_id,
            user_id=model.user_id,
            user_message=model.user_message,
            message_bubbles=model.message_bubbles,  # String (opaque)
            task_metadata=model.task_metadata,      # String (opaque)
            created_time=model.created_time,
            updated_time=model.updated_time
        )
