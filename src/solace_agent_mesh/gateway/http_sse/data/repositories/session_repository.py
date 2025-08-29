"""
Session repository interface and implementation.
"""

from abc import abstractmethod

from sqlalchemy.orm import Session

from ...shared.types import PaginationInfo, SessionId, UserId
from ..models.session_models import ChatMessage
from ..models.session_models import Session as SessionModel
from .base_repository import BaseRepository, IBaseRepository


class ISessionRepository(IBaseRepository[SessionModel]):
    """Session repository interface."""

    @abstractmethod
    def get_by_user_id(self, user_id: UserId) -> list[SessionModel]:
        pass

    @abstractmethod
    def get_with_messages(self, session_id: SessionId) -> SessionModel | None:
        """Get session with all its messages."""
        pass

    @abstractmethod
    def update_name(self, session_id: SessionId, name: str) -> SessionModel | None:
        pass

    @abstractmethod
    def get_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> SessionModel | None:
        """Get session if it belongs to the user."""
        pass


class IMessageRepository(IBaseRepository[ChatMessage]):
    """Message repository interface."""

    @abstractmethod
    def get_by_session_id(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[ChatMessage]:
        """Get all messages for a specific session."""
        pass

    @abstractmethod
    def create_message(
        self, session_id: SessionId, message: str, sender_type: str, sender_name: str
    ) -> ChatMessage:
        pass


class SessionRepository(BaseRepository[SessionModel], ISessionRepository):
    """Session repository implementation."""

    def __init__(self, db: Session):
        super().__init__(db, SessionModel)

    def get_by_user_id(self, user_id: UserId) -> list[SessionModel]:
        return self.db.query(SessionModel).filter(SessionModel.user_id == user_id).all()

    def get_with_messages(self, session_id: SessionId) -> SessionModel | None:
        """Get session with all its messages."""
        return self.db.query(SessionModel).filter(SessionModel.id == session_id).first()

    def update_name(self, session_id: SessionId, name: str) -> SessionModel | None:
        return self.update(session_id, {"name": name})

    def get_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> SessionModel | None:
        """Get session if it belongs to the user."""
        return (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
            .first()
        )


class MessageRepository(BaseRepository[ChatMessage], IMessageRepository):
    """Message repository implementation."""

    def __init__(self, db: Session):
        super().__init__(db, ChatMessage)

    def get_by_session_id(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[ChatMessage]:
        """Get all messages for a specific session."""
        query = self.db.query(ChatMessage).filter(ChatMessage.session_id == session_id)

        query = query.order_by(ChatMessage.created_at.asc())

        if pagination:
            query = query.offset((pagination.page - 1) * pagination.page_size).limit(
                pagination.page_size
            )

        return query.all()

    def create_message(
        self, session_id: SessionId, message: str, sender_type: str, sender_name: str
    ) -> ChatMessage:
        import uuid

        message_data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "message": message,
            "sender_type": sender_type,
            "sender_name": sender_name,
        }
        return self.create(message_data)
