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
from .share_repository import ShareRepository
from .task_repository import TaskRepository

# Entities (re-exported for convenience)
from .entities.session import Session
from .entities.share import ShareLink, SharedArtifact

# Models (re-exported for convenience)
from .models.base import Base
from .models.session_model import SessionModel
from .models.share_model import SharedLinkModel, SharedArtifactModel

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
    "ShareRepository",
    "TaskRepository",
    # Entities
    "Session",
    "ShareLink",
    "SharedArtifact",
    # Models
    "Base",
    "SessionModel",
    "SharedLinkModel",
    "SharedArtifactModel",
]
