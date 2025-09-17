"""
Message repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.enums import MessageType, SenderType
from ..shared.types import PaginationInfo, SessionId
from .entities import Message
from .interfaces import IMessageRepository
from .models import MessageModel


class MessageRepository(IMessageRepository):
    """SQLAlchemy implementation of message repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def find_by_session(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        """Find all messages in a session."""
        query = self.db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        )

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.order_by(MessageModel.created_time.asc()).all()
        return [self._model_to_entity(model) for model in models]

    def save(self, message: Message) -> Message:
        """Save or update a message."""
        model = (
            self.db.query(MessageModel).filter(MessageModel.id == message.id).first()
        )

        if model:
            # Update existing
            model.message = message.message
            model.sender_type = message.sender_type.value
            model.sender_name = message.sender_name
        else:
            # Create new
            model = MessageModel(
                id=message.id,
                session_id=message.session_id,
                message=message.message,
                sender_type=message.sender_type.value,
                sender_name=message.sender_name,
                created_time=message.created_time,
            )
            self.db.add(model)

        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete_by_session(self, session_id: SessionId) -> bool:
        """Delete all messages in a session."""
        result = (
            self.db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .delete()
        )
        self.db.commit()
        return result > 0

    def _model_to_entity(self, model: MessageModel) -> Message:
        """Convert SQLAlchemy model to domain entity."""
        return Message(
            id=model.id,
            session_id=model.session_id,
            message=model.message,
            sender_type=SenderType(model.sender_type),
            sender_name=model.sender_name,
            message_type=MessageType.TEXT,  # Default for now
            created_time=model.created_time,
        )
