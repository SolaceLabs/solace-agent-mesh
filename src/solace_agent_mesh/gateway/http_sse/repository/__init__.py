"""
Repository layer containing all data access logic organized by entity type.
"""

# Interfaces
from .interfaces import (
    IChatTaskRepository,
    IFeedbackRepository,
    IProjectRepository,
    ISessionRepository,
    ITaskRepository,
)

# Implementations
from .chat_task_repository import ChatTaskRepository
from .feedback_repository import FeedbackRepository
from .project_repository import ProjectRepository
from .session_repository import SessionRepository
from .task_repository import TaskRepository

# Entities (re-exported for convenience)
from .entities.session import Session

# Models (re-exported for convenience)
from .models.base import Base
from .models.session_model import SessionModel

__all__ = [
    # Interfaces
    "IChatTaskRepository",
    "IFeedbackRepository",
    "IProjectRepository",
    "ISessionRepository",
    "ITaskRepository",
    # Implementations
    "ChatTaskRepository",
    "FeedbackRepository",
    "ProjectRepository",
    "SessionRepository",
    "TaskRepository",
    # Entities
    "Session",
    # Models
    "Base",
    "SessionModel",
]
