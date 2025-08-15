"""
Request DTOs for API endpoints.
"""

from .session_requests import (
    GetSessionsRequest,
    GetSessionRequest,
    GetSessionHistoryRequest,
    UpdateSessionRequest,
    DeleteSessionRequest,
    CreateSessionRequest,
)
from .user_requests import (
    GetCurrentUserRequest,
    AuthenticateUserRequest,
    UserProfileRequest,
)
from .task_requests import (
    SendTaskRequest,
    SubscribeTaskRequest,
    CancelTaskRequest,
    GetTaskStatusRequest,
    TaskFilesInfo,
    ProcessedTaskRequest,
)

__all__ = [
    # Session requests
    "GetSessionsRequest",
    "GetSessionRequest", 
    "GetSessionHistoryRequest",
    "UpdateSessionRequest",
    "DeleteSessionRequest",
    "CreateSessionRequest",
    # User requests
    "GetCurrentUserRequest",
    "AuthenticateUserRequest",
    "UserProfileRequest",
    # Task requests
    "SendTaskRequest",
    "SubscribeTaskRequest",
    "CancelTaskRequest",
    "GetTaskStatusRequest",
    "TaskFilesInfo",
    "ProcessedTaskRequest",
]