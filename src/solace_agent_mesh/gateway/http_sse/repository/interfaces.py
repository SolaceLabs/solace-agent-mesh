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


class IProjectRepository(ABC):
    """Interface for project repository operations."""

    @abstractmethod
    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      system_prompt: Optional[str] = None,
                      created_by_user_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        pass

    @abstractmethod
    def create_global_project(self, name: str, description: Optional[str] = None,
                             created_by_user_id: str = None) -> Project:
        """Create a new global project template."""
        pass

    @abstractmethod
    def copy_from_template(self, template_id: str, name: str, user_id: str,
                          description: Optional[str] = None) -> Optional[Project]:
        """Create a new project by copying from a template."""
        pass

    @abstractmethod
    def get_user_projects(self, user_id: str) -> list[Project]:
        """Get all projects owned by a specific user."""
        pass

    @abstractmethod
    def get_global_projects(self) -> list[Project]:
        """Get all global project templates."""
        pass

    @abstractmethod
    def get_projects_by_template(self, template_id: str) -> list[Project]:
        """Get all projects copied from a specific template."""
        pass

    @abstractmethod
    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
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
