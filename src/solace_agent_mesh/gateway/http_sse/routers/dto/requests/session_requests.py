"""
Session-related request DTOs.
"""

from pydantic import BaseModel, Field

from ....shared.types import SessionId, UserId


class GetSessionRequest(BaseModel):
    """Request DTO for retrieving a specific session."""
    session_id: SessionId
    user_id: UserId


class UpdateSessionRequest(BaseModel):
    """Request DTO for updating session details."""
    session_id: SessionId
    user_id: UserId
    name: str = Field(..., min_length=1, max_length=255, description="New session name")
