"""
Repository interfaces defining contracts for data access.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session as DBSession

from ..shared.pagination import PaginationParams
from ..shared.types import SessionId, UserId
from .entities import Feedback, Session, Task, TaskEvent
from .entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter

if TYPE_CHECKING:
    from .entities import ChatTask


class ISessionRepository(ABC):
    """Interface for session data access operations."""

    @abstractmethod
    def find_by_user(
        self, session: DBSession, user_id: UserId, pagination: PaginationParams | None = None, project_id: str | None = None
    ) -> list[Session]:
        """Find all sessions for a specific user, optionally filtered by project."""
        pass

    @abstractmethod
    def count_by_user(self, session: DBSession, user_id: UserId, project_id: str | None = None) -> int:
        """Count total sessions for a specific user, optionally filtered by project."""
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

    @abstractmethod
    def soft_delete(self, session: DBSession, session_id: SessionId, user_id: UserId) -> bool:
        """Soft delete a session belonging to a user."""
        pass

    @abstractmethod
    def move_to_project(
        self, session: DBSession, session_id: SessionId, user_id: UserId, new_project_id: str | None
    ) -> Session | None:
        """Move a session to a different project."""
        pass

    @abstractmethod
    def search(
        self,
        session: DBSession,
        user_id: UserId,
        query: str,
        pagination: PaginationParams | None = None,
        project_id: str | None = None
    ) -> list[Session]:
        """Search sessions by name or content."""
        pass

    @abstractmethod
    def count_search_results(
        self,
        session: DBSession,
        user_id: UserId,
        query: str,
        project_id: str | None = None
    ) -> int:
        """Count search results for pagination."""
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
    def search(
        self,
        session: DBSession,
        user_id: UserId,
        start_date: int | None = None,
        end_date: int | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        rating: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> list[Feedback]:
        """
        Search feedback with flexible filtering.
        All filters are optional and can be combined.

        Args:
            session: Database session
            user_id: User ID to filter by, or "*" for all users (admin)
            start_date: Start of date range in epoch milliseconds
            end_date: End of date range in epoch milliseconds
            task_id: Filter by specific task ID
            session_id: Filter by specific session ID
            rating: Filter by rating type ("up" or "down")
            pagination: Pagination parameters

        Returns:
            List of feedback entries matching the filters
        """
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


class IProjectRepository(ABC):
    """Interface for project repository operations."""

    @abstractmethod
    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      system_prompt: Optional[str] = None) -> Project:
        """Create a new user project."""
        pass

    @abstractmethod
    def get_user_projects(self, user_id: str) -> list[Project]:
        """Get all projects owned by a specific user."""
        pass

    @abstractmethod
    def get_filtered_projects(self, project_filter: ProjectFilter) -> list[Project]:
        """Get projects based on filter criteria."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: str, user_id: str) -> Optional[Project]:
        """Get a project by its ID, ensuring user access."""
        pass

    @abstractmethod
    def update(self, project_id: str, user_id: str, update_data: dict) -> Optional[Project]:
        """Update a project with the given data, ensuring user access."""
        pass

    @abstractmethod
    def delete(self, project_id: str, user_id: str) -> bool:
        """Delete a project by its ID, ensuring user access."""
        pass

    @abstractmethod
    def soft_delete(self, project_id: str, user_id: str) -> bool:
        """Soft delete a project by its ID, ensuring user access."""
        pass
