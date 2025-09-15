"""
Request DTOs for API endpoints.
"""

from .session_requests import (
    GetSessionsRequest,
    GetSessionRequest,
    GetSessionHistoryRequest,
    UpdateSessionRequest,
    DeleteSessionRequest,
)

__all__ = [
    # Session requests
    "GetSessionsRequest",
    "GetSessionRequest", 
    "GetSessionHistoryRequest",
    "UpdateSessionRequest",
    "DeleteSessionRequest",
]