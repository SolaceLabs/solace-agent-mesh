"""
Message SQLAlchemy model and Pydantic models for strongly-typed operations.
"""

from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ...shared import now_epoch_ms
from .base import Base


class MessageModel(Base):
    """SQLAlchemy model for messages."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message = Column(Text, nullable=False)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    sender_type = Column(String(50))
    sender_name = Column(String(255))

    # Relationship to session
    session = relationship("SessionModel", back_populates="messages")


class CreateMessageModel(BaseModel):
    """Pydantic model for creating a message."""
    id: str
    session_id: str
    message: str
    sender_type: str
    sender_name: str
    created_time: int


class UpdateMessageModel(BaseModel):
    """Pydantic model for updating a message."""
    message: str
    sender_type: str
    sender_name: str
