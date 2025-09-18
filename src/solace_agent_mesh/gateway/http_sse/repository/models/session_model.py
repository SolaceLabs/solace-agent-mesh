"""
Session SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, String
from sqlalchemy.orm import relationship

from ...shared import now_epoch_ms
from .base import Base


class SessionModel(Base):
    """SQLAlchemy model for sessions."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    user_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=True)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(
        BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms
    )

    # Relationship to messages
    messages = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan"
    )
