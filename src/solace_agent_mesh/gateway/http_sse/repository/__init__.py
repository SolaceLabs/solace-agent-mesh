"""
Repository layer containing all data access logic organized by entity type.
"""

# Interfaces
from .interfaces import IMessageRepository, IProjectRepository, ISessionRepository

# Implementations
from .message_repository import MessageRepository
from .project_repository import ProjectRepository
from .session_repository import SessionRepository

# Entities (re-exported for convenience)
from .entities.session import Session
from .entities.message import Message
from .entities.session_history import SessionHistory

# Models (re-exported for convenience)
from .models.base import Base
from .models.message_model import MessageModel
from .models.project_model import ProjectModel
from .models.session_model import SessionModel

__all__ = [
    # Interfaces
    "IMessageRepository",
    "IProjectRepository",
    "ISessionRepository",
    # Implementations
    "MessageRepository",
    "ProjectRepository",
    "SessionRepository",
    # Entities
    "Message",
    "Session",
    "SessionHistory",
    # Models
    "Base",
    "MessageModel",
    "ProjectModel",
    "SessionModel",
]