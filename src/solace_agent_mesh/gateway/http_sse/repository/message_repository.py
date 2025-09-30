"""
Message repository implementation using SQLAlchemy.
"""

from sqlalchemy.orm import Session as DBSession

from ..shared.base_repository import PaginatedRepository
from ..shared.enums import MessageType, SenderType
from ..shared.types import PaginationInfo, SessionId
from .entities import Message
from .interfaces import IMessageRepository
from .models import MessageModel, CreateMessageModel, UpdateMessageModel


class MessageRepository(PaginatedRepository[MessageModel, Message], IMessageRepository):
    """SQLAlchemy implementation of message repository using BaseRepository."""

    def __init__(self, db: DBSession):
        super().__init__(MessageModel, Message)
        self.db = db

    @property
    def entity_name(self) -> str:
        """Return the entity name for error messages."""
        return "message"

    def find_by_session(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        """Find all messages in a session."""
        query = self.db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        )
        query = query.order_by(MessageModel.created_time.asc())

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        models = query.all()
        return [self._convert_model_to_entity(model) for model in models]

    def save(self, message: Message) -> Message:
        """Save or update a message."""
        existing_model = self.db.query(MessageModel).filter(MessageModel.id == message.id).first()

        if existing_model:
            update_model = UpdateMessageModel(
                message=message.message,
                sender_type=message.sender_type.value,
                sender_name=message.sender_name,
            )
            return self.update(self.db, message.id, update_model.model_dump())
        else:
            create_model = CreateMessageModel(
                id=message.id,
                session_id=message.session_id,
                message=message.message,
                sender_type=message.sender_type.value,
                sender_name=message.sender_name,
                created_time=message.created_time,
            )
            return self.create(self.db, create_model.model_dump())

    def delete_by_session(self, session_id: SessionId) -> bool:
        """Delete all messages in a session."""
        result = (
            self.db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .delete()
        )
        return result > 0

    def _convert_model_to_entity(self, model: MessageModel) -> Message:
        """Convert SQLAlchemy model to domain entity with enum handling."""
        return Message(
            id=model.id,
            session_id=model.session_id,
            message=model.message,
            sender_type=SenderType(model.sender_type),
            sender_name=model.sender_name,
            message_type=MessageType.TEXT,  # Default for now
            created_time=model.created_time,
        )
