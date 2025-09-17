"""
Message SQLAlchemy model.
"""

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
