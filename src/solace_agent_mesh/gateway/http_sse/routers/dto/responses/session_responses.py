"""
Session-related response DTOs.
"""

from pydantic import BaseModel, ConfigDict, Field

from ....shared.enums import MessageType, SenderType
from ....shared.types import MessageId, PaginationInfo, SessionId, UserId
from .base_responses import BaseTimestampResponse


class MessageResponse(BaseTimestampResponse):
    """Response DTO for a chat message."""

    id: MessageId
    session_id: SessionId = Field(alias="sessionId")
    message: str
    sender_type: SenderType = Field(alias="senderType")
    sender_name: str = Field(alias="senderName")
    message_type: MessageType = Field(default=MessageType.TEXT, alias="messageType")
    created_time: int = Field(alias="createdTime")
    updated_time: int | None = Field(default=None, alias="updatedTime")


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
