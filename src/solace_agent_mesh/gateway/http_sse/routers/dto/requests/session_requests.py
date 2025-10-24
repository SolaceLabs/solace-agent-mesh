"""
Session-related request DTOs.
"""

from typing import Optional
from pydantic import BaseModel, Field

from ....shared.types import SessionId, UserId


class GetSessionRequest(BaseModel):
    """Request DTO for retrieving a specific session."""
    session_id: SessionId
    project_id: Optional[str] = None
    user_id: UserId


class UpdateSessionRequest(BaseModel):
    """Request DTO for updating session details."""
    session_id: SessionId
    user_id: UserId
    name: str = Field(..., min_length=1, max_length=255, description="New session name")


class MoveSessionRequest(BaseModel):
    """Request DTO for moving a session to a different project."""
    project_id: Optional[str] = Field(None, alias="projectId", description="New project ID (null to remove from project)")


class SearchSessionsRequest(BaseModel):
    """Request DTO for searching sessions."""
    query: str = Field(..., min_length=1, description="Search query string")
    project_id: Optional[str] = Field(None, alias="projectId", description="Optional project ID to filter results")
