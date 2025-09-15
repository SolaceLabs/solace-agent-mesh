"""
Session SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class SessionModel(Base):
    """SQLAlchemy model for sessions."""
    
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    user_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationship to messages
    messages = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan"
    )