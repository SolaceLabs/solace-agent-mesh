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
from .document_conversion_cache_repository import DocumentConversionCacheRepository
from .feedback_repository import FeedbackRepository
from .project_repository import ProjectRepository
from .session_repository import SessionRepository
from .sse_event_buffer_repository import SSEEventBufferRepository
from .task_repository import TaskRepository

# Entities (re-exported for convenience)
from .entities.session import Session

# Models (re-exported for convenience)
from .models.base import Base
from .models.document_conversion_cache_model import DocumentConversionCacheModel
from .models.session_model import SessionModel
from .models.sse_event_buffer_model import SSEEventBufferModel

__all__ = [
    # Interfaces
    "IChatTaskRepository",
    "IFeedbackRepository",
    "IProjectRepository",
    "ISessionRepository",
    "ITaskRepository",
    # Implementations
    "ChatTaskRepository",
    "DocumentConversionCacheRepository",
    "FeedbackRepository",
    "ProjectRepository",
    "SessionRepository",
    "SSEEventBufferRepository",
    "TaskRepository",
    # Entities
    "Session",
    # Models
    "Base",
    "DocumentConversionCacheModel",
    "SessionModel",
    "SSEEventBufferModel",
]
