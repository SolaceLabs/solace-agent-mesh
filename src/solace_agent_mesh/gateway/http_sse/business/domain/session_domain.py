"""
Session domain entities and business rules.
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from ...shared.enums import MessageType, SenderType, SessionStatus
from ...shared.types import AgentId, MessageId, SessionId, UserId


class SessionDomain(BaseModel):
    """Session domain entity with business rules."""

    id: SessionId
    user_id: UserId
    name: str | None = None
    agent_id: AgentId | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime
    updated_at: datetime | None = None
    last_activity: datetime | None = None

    def update_name(self, new_name: str) -> None:
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("Session name cannot be empty")
        if len(new_name) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        self.name = new_name.strip()
        self.updated_at = datetime.now(timezone.utc)

    def mark_activity(self) -> None:
        """Mark session as having recent activity."""
        self.last_activity = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        self.status = SessionStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        self.status = SessionStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def can_be_deleted_by_user(self, user_id: UserId) -> bool:
        """Check if session can be deleted by the given user."""
        return self.user_id == user_id

    def can_be_accessed_by_user(self, user_id: UserId) -> bool:
        """Check if session can be accessed by the given user."""
        return self.user_id == user_id


class MessageDomain(BaseModel):
    """Message domain entity with business rules."""

    id: MessageId
    session_id: SessionId
    message: str
    sender_type: SenderType
    sender_name: str
    message_type: MessageType = MessageType.TEXT
    created_at: datetime

    def validate_message_content(self) -> None:
        """Validate message content."""
        if not self.message or len(self.message.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(self.message) > 10_000_000:  # 10MB soft limit for extreme cases
            raise ValueError("Message content exceeds maximum length (10MB)")

    def is_from_user(self) -> bool:
        """Check if message is from a user."""
        return self.sender_type == SenderType.USER

    def is_from_agent(self) -> bool:
        """Check if message is from an agent."""
        return self.sender_type == SenderType.AGENT

    def is_system_message(self) -> bool:
        """Check if message is a system message."""
        return self.sender_type == SenderType.SYSTEM


class SessionHistoryDomain(BaseModel):
    """Session history domain entity."""

    session: SessionDomain
    messages: list[MessageDomain] = []
    total_message_count: int = 0

    def add_message(self, message: MessageDomain) -> None:
        if message.session_id != self.session.id:
            raise ValueError("Message does not belong to this session")

        message.validate_message_content()
        self.messages.append(message)
        self.total_message_count += 1
        self.session.mark_activity()

    def get_messages_by_sender_type(
        self, sender_type: SenderType
    ) -> list[MessageDomain]:
        """Get messages filtered by sender type."""
        return [msg for msg in self.messages if msg.sender_type == sender_type]

    def get_latest_messages(self, count: int = 10) -> list[MessageDomain]:
        """Get the latest N messages."""
        return sorted(self.messages, key=lambda x: x.created_at, reverse=True)[:count]
