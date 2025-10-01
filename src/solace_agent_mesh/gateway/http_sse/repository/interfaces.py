"""
Repository interfaces defining contracts for data access.
"""

from abc import ABC, abstractmethod

from ..shared.types import PaginationInfo, SessionId, UserId
from .entities import Message, Session


class ISessionRepository(ABC):
    """Interface for session data access operations."""
    
    @abstractmethod
    def find_by_user(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        pass

    @abstractmethod
    def count_by_user(self, user_id: UserId) -> int:
        """Count total sessions for a specific user."""
        pass

    @abstractmethod
    def find_user_session(
        self, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        """Find a specific session belonging to a user."""
        pass

    @abstractmethod
    def save(self, session: Session) -> Session:
        """Save or update a session."""
        pass

    @abstractmethod
    def delete(self, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        pass

    @abstractmethod
    def find_user_session_with_messages(
        self, session_id: SessionId, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> tuple[Session, list[Message]] | None:
        """Find a session with its messages."""
        pass


class IMessageRepository(ABC):
    """Interface for message data access operations."""
    
    @abstractmethod
    def find_by_session(
        self, session_id: SessionId, pagination: PaginationInfo | None = None
    ) -> list[Message]:
        """Find all messages in a session."""
        pass

    @abstractmethod
    def save(self, message: Message) -> Message:
        """Save or update a message."""
        pass

    @abstractmethod
    def delete_by_session(self, session_id: SessionId) -> bool:
        """Delete all messages in a session."""
        pass