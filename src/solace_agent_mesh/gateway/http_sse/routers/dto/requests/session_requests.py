"""
Session-related request DTOs.
"""

from typing import Optional
from pydantic import BaseModel, Field

from ....shared.types import SessionId, UserId, PaginationInfo


class GetSessionRequest(BaseModel):
    """Request DTO for retrieving a specific session."""
    session_id: SessionId
    user_id: UserId


class GetSessionHistoryRequest(BaseModel):
    """Request DTO for retrieving session message history."""
    session_id: SessionId
    user_id: UserId
    pagination: Optional[PaginationInfo] = None


class UpdateSessionRequest(BaseModel):
    """Request DTO for updating session details."""
    session_id: SessionId
    user_id: UserId
    name: str = Field(..., min_length=1, max_length=255, description="New session name")