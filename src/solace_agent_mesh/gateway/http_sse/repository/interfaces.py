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