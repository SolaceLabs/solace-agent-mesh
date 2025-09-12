"""
Repository layer containing all data access logic organized by entity type.
"""

# Interfaces
from .interfaces import IMessageRepository, ISessionRepository

# Implementations
from .message_repository import MessageRepository
from .session_repository import SessionRepository

# Entities (re-exported for convenience)
from .entities.session import Session
from .entities.message import Message
from .entities.session_history import SessionHistory

# Models (re-exported for convenience)
from .models.base import Base
from .models.session_model import SessionModel
from .models.message_model import MessageModel

__all__ = [
    # Interfaces
    "IMessageRepository",
    "ISessionRepository",
    # Implementations
    "MessageRepository", 
    "SessionRepository",
    # Entities
    "Message",
    "Session", 
    "SessionHistory",
    # Models
    "Base",
    "MessageModel",
    "SessionModel",
]