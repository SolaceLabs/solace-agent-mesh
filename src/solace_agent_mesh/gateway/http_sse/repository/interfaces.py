"""
Repository interfaces defining contracts for data access.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session as DBSession

from ..shared.pagination import PaginationParams
from ..shared.types import SessionId, UserId
from .entities import Feedback, Session, Task, TaskEvent

if TYPE_CHECKING:
    from .entities import ChatTask


class ISessionRepository(ABC):
    """Interface for session data access operations."""

    @abstractmethod
    def find_by_user(
        self, session: DBSession, user_id: UserId, pagination: PaginationParams | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user."""
        pass

    @abstractmethod
    def count_by_user(self, session: DBSession, user_id: UserId) -> int:
        """Count total sessions for a specific user."""
        pass

    @abstractmethod
    def find_user_session(
        self, session: DBSession, session_id: SessionId, user_id: UserId
    ) -> Session | None:
        """Find a specific session belonging to a user."""
        pass

    @abstractmethod
    def save(self, session: DBSession, session_obj: Session) -> Session:
        """Save or update a session."""
        pass

    @abstractmethod
    def delete(self, session: DBSession, session_id: SessionId, user_id: UserId) -> bool:
        """Delete a session belonging to a user."""
        pass


class ITaskRepository(ABC):
    """Interface for task data access operations."""

    @abstractmethod
    def save_task(self, session: DBSession, task: Task) -> Task:
        """Create or update a task."""
        pass

    @abstractmethod
    def save_event(self, session: DBSession, event: TaskEvent) -> TaskEvent:
        """Save a task event."""
        pass

    @abstractmethod
    def find_by_id(self, session: DBSession, task_id: str) -> Task | None:
        """Find a task by its ID."""
        pass

    @abstractmethod
    def find_by_id_with_events(
        self, session: DBSession, task_id: str
    ) -> tuple[Task, list[TaskEvent]] | None:
        """Find a task with all its events."""
        pass

    @abstractmethod
    def search(
        self,
        session: DBSession,
        user_id: UserId,
        start_date: int | None = None,
        end_date: int | None = None,
        search_query: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> list[Task]:
        """Search for tasks with filters."""
        pass

    @abstractmethod
    def delete_tasks_older_than(self, session: DBSession, cutoff_time_ms: int, batch_size: int) -> int:
        """Delete tasks older than cutoff time using batch deletion."""
        pass


class IFeedbackRepository(ABC):
    """Interface for feedback data access operations."""

    @abstractmethod
    def save(self, session: DBSession, feedback: Feedback) -> Feedback:
        """Save feedback."""
        pass

    @abstractmethod
    def delete_feedback_older_than(self, session: DBSession, cutoff_time_ms: int, batch_size: int) -> int:
        """Delete feedback older than cutoff time using batch deletion."""
        pass


class IChatTaskRepository(ABC):
    """Interface for chat task data access operations."""

    @abstractmethod
    def save(self, session: DBSession, task: "ChatTask") -> "ChatTask":
        """Save or update a chat task (upsert)."""
        pass

    @abstractmethod
    def find_by_session(
        self, session: DBSession, session_id: SessionId, user_id: UserId
    ) -> list["ChatTask"]:
        """Find all tasks for a session."""
        pass

    @abstractmethod
    def find_by_id(self, session: DBSession, task_id: str, user_id: UserId) -> Optional["ChatTask"]:
        """Find a specific task."""
        pass

    @abstractmethod
    def delete_by_session(self, session: DBSession, session_id: SessionId) -> bool:
        """Delete all tasks for a session."""
        pass
