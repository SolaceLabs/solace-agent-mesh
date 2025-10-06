"""
Repository layer containing all data access logic organized by entity type.
"""

# Interfaces
from .interfaces import ISessionRepository

# Implementations
from .session_repository import SessionRepository

# Entities (re-exported for convenience)
from .entities.session import Session

# Models (re-exported for convenience)
from .models.base import Base
from .models.session_model import SessionModel

__all__ = [
    # Interfaces
    "ISessionRepository",
    # Implementations
    "SessionRepository",
    # Entities
    "Session",
    # Models
    "Base",
    "SessionModel",
]
