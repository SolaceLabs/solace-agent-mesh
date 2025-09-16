"""
Session-related response DTOs.
"""

from pydantic import BaseModel

from ....shared.enums import MessageType, SenderType
from ....shared.types import MessageId, PaginationInfo, SessionId, UserId
from .base_responses import BaseTimestampResponse


class MessageResponse(BaseTimestampResponse):
    """Response DTO for a chat message."""

    id: MessageId
    session_id: SessionId
    message: str
    sender_type: SenderType
    sender_name: str
    message_type: MessageType = MessageType.TEXT
    created_time: int
    updated_time: int | None = None


class SessionResponse(BaseTimestampResponse):
    """Response DTO for a session."""

    id: SessionId
    user_id: UserId
    name: str | None = None
    agent_id: str | None = None
    created_time: int
    updated_time: int | None = None


class SessionListResponse(BaseModel):
    """Response DTO for a list of sessions."""

    sessions: list[SessionResponse]
    pagination: PaginationInfo | None = None
    total_count: int
