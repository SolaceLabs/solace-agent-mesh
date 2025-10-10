"""
Repository interfaces defining contracts for data access.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime

from ..shared.types import PaginationInfo, SessionId, UserId
from .entities import Message, Session
from .entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter
from typing import TYPE_CHECKING, Optional

from ..shared.types import PaginationInfo, PaginationParams, SessionId, UserId
from .entities import Feedback, Session, Task, TaskEvent

if TYPE_CHECKING:
    from .entities import ChatTask


class ISessionRepository(ABC):
    """Interface for session data access operations."""
    
    @abstractmethod
    def find_by_user(
        self, user_id: UserId, pagination: PaginationParams | None = None
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

    @abstractmethod
    def delete_tasks_older_than(self, cutoff_time_ms: int, batch_size: int) -> int:
        """Delete tasks older than cutoff time using batch deletion."""
        pass


class IFeedbackRepository(ABC):
    """Interface for feedback data access operations."""

    @abstractmethod
    def save(self, feedback: Feedback) -> Feedback:
        """Save feedback."""
        pass

    @abstractmethod
    def delete_feedback_older_than(self, cutoff_time_ms: int, batch_size: int) -> int:
        """Delete feedback older than cutoff time using batch deletion."""
        pass


class IChatTaskRepository(ABC):
    """Interface for chat task data access operations."""

    @abstractmethod
    def save(self, task: "ChatTask") -> "ChatTask":
        """Save or update a chat task (upsert)."""
        pass

    @abstractmethod
    def find_by_session(self, session_id: SessionId, user_id: UserId) -> list["ChatTask"]:
        """Find all tasks for a session."""
        pass

    @abstractmethod
    def find_by_id(self, task_id: str, user_id: UserId) -> Optional["ChatTask"]:
        """Find a specific task."""
        pass

    @abstractmethod
    def delete_by_session(self, session_id: SessionId) -> bool:
        """Delete all messages in a session."""
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
    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        pass

    @abstractmethod
    def get_global_projects(self) -> List[Project]:
        """Get all global project templates."""
        pass

    @abstractmethod
    def get_projects_by_template(self, template_id: str) -> List[Project]:
        """Get all projects copied from a specific template."""
        pass

    @abstractmethod
    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
        pass

    @abstractmethod
    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
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
