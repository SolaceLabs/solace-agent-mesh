"""
Session-related response DTOs.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ....shared.types import SessionId, UserId, MessageId, PaginationInfo, Timestamp
from ....shared.enums import SessionStatus, SenderType, MessageType


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
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class SessionListResponse(BaseModel):
    """Response DTO for a list of sessions."""
    sessions: List[SessionResponse]
    pagination: Optional[PaginationInfo] = None
    total_count: int


class SessionHistoryResponse(BaseModel):
    """Response DTO for session message history."""
    session_id: SessionId
    messages: List[MessageResponse]
    pagination: Optional[PaginationInfo] = None
    total_count: int


class SessionCreatedResponse(BaseModel):
    """Response DTO for session creation."""
    session: SessionResponse
    message: str = "Session created successfully"


class SessionUpdatedResponse(BaseModel):
    """Response DTO for session update."""
    session: SessionResponse
    message: str = "Session updated successfully"


class SessionDeletedResponse(BaseModel):
    """Response DTO for session deletion."""
    session_id: SessionId
    message: str = "Session deleted successfully"