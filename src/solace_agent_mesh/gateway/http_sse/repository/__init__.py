"""
Repository layer containing all data access logic organized by entity type.
"""

# Interfaces
# Entities (re-exported for convenience)
from .entities.session import Session
from .interfaces import ISessionRepository

# Models (re-exported for convenience)
from .models.base import Base
from .models.session_model import SessionModel

# Implementations
from .session_repository import SessionRepository

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
