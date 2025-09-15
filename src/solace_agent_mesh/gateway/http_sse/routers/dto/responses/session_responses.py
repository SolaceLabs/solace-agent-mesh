"""
Session-related response DTOs.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from ....shared.types import SessionId, UserId, MessageId, PaginationInfo
from ....shared.enums import SenderType, MessageType


class MessageResponse(BaseModel):
    """Response DTO for a chat message."""
    id: MessageId
    session_id: SessionId
    message: str
    sender_type: SenderType
    sender_name: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None


class SessionResponse(BaseModel):
    """Response DTO for a session."""
    id: SessionId
    user_id: UserId
    name: Optional[str] = None
    agent_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class SessionListResponse(BaseModel):
    """Response DTO for a list of sessions."""
    sessions: List[SessionResponse]
    pagination: Optional[PaginationInfo] = None
    total_count: int
