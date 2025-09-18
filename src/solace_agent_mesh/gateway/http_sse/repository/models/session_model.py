"""
Session SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, String, ForeignKey
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
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(
        BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms
    )

    # Relationships
    messages = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan"
    )
    project = relationship("ProjectModel", back_populates="sessions")
