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
    # Task requests
    "SendTaskRequest",
    "SubscribeTaskRequest",
    "CancelTaskRequest",
    "GetTaskStatusRequest",
    "TaskFilesInfo",
    "ProcessedTaskRequest",
]