"""
Message domain entity.
"""

from pydantic import BaseModel, ConfigDict

from ...shared.enums import MessageType, SenderType
from ...shared.types import MessageId, SessionId


class Message(BaseModel):
    """Message domain entity with business logic."""

    model_config = ConfigDict(from_attributes=True)

    id: MessageId
    session_id: SessionId
    message: str
    sender_type: SenderType
    sender_name: str
    message_type: MessageType = MessageType.TEXT
    created_time: int

    def validate_message_content(self) -> None:
        """Validate message content."""
        if not self.message or len(self.message.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(self.message) > 10_000_000:
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
