"""
Message SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class MessageModel(Base):
    """SQLAlchemy model for messages."""
    
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True)
    session_id = Column(
        String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    sender_type = Column(String(50))
    sender_name = Column(String(255))
    
    # Relationship to session
    session = relationship("SessionModel", back_populates="messages")