"""
Session repository interface and implementation.
"""

from abc import abstractmethod
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from .base_repository import IBaseRepository, BaseRepository
from ..models.session_models import Session as SessionModel, ChatMessage
from ...shared.types import SessionId, UserId, MessageId, PaginationInfo


class ISessionRepository(IBaseRepository[SessionModel]):
    """Session repository interface."""
    
    @abstractmethod
    def get_by_user_id(self, user_id: UserId) -> List[SessionModel]:
        pass
    
    @abstractmethod
    def get_with_messages(self, session_id: SessionId) -> Optional[SessionModel]:
        """Get session with all its messages."""
        pass
    
    @abstractmethod
    def update_name(self, session_id: SessionId, name: str) -> Optional[SessionModel]:
        pass
    
    @abstractmethod
    def get_user_session(self, session_id: SessionId, user_id: UserId) -> Optional[SessionModel]:
        """Get session if it belongs to the user."""
        pass


class IMessageRepository(IBaseRepository[ChatMessage]):
    """Message repository interface."""
    
    @abstractmethod
    def get_by_session_id(
        self, 
        session_id: SessionId,
        pagination: Optional[PaginationInfo] = None
    ) -> List[ChatMessage]:
        """Get all messages for a specific session."""
        pass
    
    @abstractmethod
    def create_message(
        self,
        session_id: SessionId,
        message: str,
        sender_type: str,
        sender_name: str
    ) -> ChatMessage:
        pass


class SessionRepository(BaseRepository[SessionModel], ISessionRepository):
    """Session repository implementation."""
    
    def __init__(self, db: Session):
        super().__init__(db, SessionModel)
    
    def get_by_user_id(self, user_id: UserId) -> List[SessionModel]:
        return self.db.query(SessionModel).filter(SessionModel.user_id == user_id).all()
    
    def get_with_messages(self, session_id: SessionId) -> Optional[SessionModel]:
        """Get session with all its messages."""
        return (
            self.db.query(SessionModel)
            .filter(SessionModel.id == session_id)
            .first()
        )
    
    def update_name(self, session_id: SessionId, name: str) -> Optional[SessionModel]:
        return self.update(session_id, {"name": name})
    
    def get_user_session(self, session_id: SessionId, user_id: UserId) -> Optional[SessionModel]:
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
        self, 
        session_id: SessionId,
        pagination: Optional[PaginationInfo] = None
    ) -> List[ChatMessage]:
        """Get all messages for a specific session."""
        query = self.db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
        
        # Order by creation time
        query = query.order_by(ChatMessage.created_at.asc())
        
        # Apply pagination if provided
        if pagination:
            query = query.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size)
        
        return query.all()
    
    def create_message(
        self,
        session_id: SessionId,
        message: str,
        sender_type: str,
        sender_name: str
    ) -> ChatMessage:
        import uuid
        message_data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "message": message,
            "sender_type": sender_type,
            "sender_name": sender_name
        }
        return self.create(message_data)