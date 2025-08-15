"""
Response DTOs for API endpoints.
"""

from .session_responses import (
    MessageResponse,
    SessionResponse,
    SessionListResponse,
    SessionHistoryResponse,
    SessionCreatedResponse,
    SessionUpdatedResponse,
    SessionDeletedResponse,
)
from .user_responses import (
    UserProfileResponse,
    CurrentUserResponse,
    UserSessionsResponse,
    UserPreferencesResponse,
    AuthenticationResponse,
)
from .task_responses import (
    TaskResponse,
    SendTaskResponse,
    SubscribeTaskResponse,
    CancelTaskResponse,
    TaskStatusResponse,
    TaskListResponse,
    TaskErrorResponse,
    JSONRPCTaskResponse,
)

__all__ = [
    # Session responses
    "MessageResponse",
    "SessionResponse",
    "SessionListResponse",
    "SessionHistoryResponse",
    "SessionCreatedResponse",
    "SessionUpdatedResponse",
    "SessionDeletedResponse",
    # User responses
    "UserProfileResponse",
    "CurrentUserResponse",
    "UserSessionsResponse",
    "UserPreferencesResponse",
    "AuthenticationResponse",
    # Task responses
    "TaskResponse",
    "SendTaskResponse",
    "SubscribeTaskResponse",
    "CancelTaskResponse",
    "TaskStatusResponse",
    "TaskListResponse",
    "TaskErrorResponse",
    "JSONRPCTaskResponse",
]