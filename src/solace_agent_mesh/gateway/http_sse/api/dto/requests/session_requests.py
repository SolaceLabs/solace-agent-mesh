"""
Session-related request DTOs.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from ....shared.types import SessionId, UserId, SortInfo, FilterInfo, PaginationInfo


class GetSessionsRequest(BaseModel):
    """Request DTO for retrieving sessions."""
    user_id: UserId
    pagination: Optional[PaginationInfo] = None
    sort: Optional[SortInfo] = None
    filters: Optional[List[FilterInfo]] = None


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


class DeleteSessionRequest(BaseModel):
    """Request DTO for deleting a session."""
    session_id: SessionId
    user_id: UserId


class CreateSessionRequest(BaseModel):
    """Request DTO for creating a new session."""
    user_id: UserId
    name: Optional[str] = Field(None, max_length=255, description="Session name")
    agent_id: Optional[str] = Field(None, description="Associated agent ID")