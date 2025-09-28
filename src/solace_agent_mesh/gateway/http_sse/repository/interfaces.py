"""
Repository interfaces defining contracts for data access.
"""

from abc import ABC, abstractmethod

from ..shared.types import PaginationInfo, PaginationParams, SessionId, UserId
from .entities import Feedback, Message, Session, Task, TaskEvent


class ISessionRepository(ABC):
    """Interface for session data access operations."""
    
    @abstractmethod
    def find_by_user(
        self, user_id: UserId, pagination: PaginationInfo | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
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


class ITaskRepository(ABC):
    """Interface for task data access operations."""

    @abstractmethod
    def save_task(self, task: Task) -> Task:
        """Create or update a task."""
        pass

    @abstractmethod
    def save_event(self, event: TaskEvent) -> TaskEvent:
        """Save a task event."""
        pass

    @abstractmethod
    def find_by_id(self, task_id: str) -> Task | None:
        """Find a task by its ID."""
        pass

    @abstractmethod
    def find_by_id_with_events(self, task_id: str) -> tuple[Task, list[TaskEvent]] | None:
        """Find a task with all its events."""
        pass

    @abstractmethod
    def search(
        self,
        user_id: UserId,
        start_date: int | None = None,
        end_date: int | None = None,
        search_query: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> list[Task]:
        """Search for tasks with filters."""
        pass


class IFeedbackRepository(ABC):
    """Interface for feedback data access operations."""

    @abstractmethod
    def save(self, feedback: Feedback) -> Feedback:
        """Save feedback."""
        pass
