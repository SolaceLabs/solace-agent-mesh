"""
Session-related response DTOs.
"""

from pydantic import BaseModel, ConfigDict, Field

from ....shared.types import PaginationInfo, SessionId, UserId
from .base_responses import BaseTimestampResponse


class SessionResponse(BaseTimestampResponse):
    """Response DTO for a session."""

    id: SessionId
    user_id: UserId = Field(alias="userId")
    name: str | None = None
    agent_id: str | None = Field(default=None, alias="agentId")
    created_time: int = Field(alias="createdTime")
    updated_time: int | None = Field(default=None, alias="updatedTime")


class SessionListResponse(BaseModel):
    """Response DTO for a list of sessions."""

    model_config = ConfigDict(populate_by_name=True)

    sessions: list[SessionResponse]
    pagination: PaginationInfo | None = None
    total_count: int = Field(alias="totalCount")
