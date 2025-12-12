"""
Session SQLAlchemy model and Pydantic models for strongly-typed operations.
"""

from sqlalchemy import BigInteger, Column, String, ForeignKey
from pydantic import BaseModel
from sqlalchemy.orm import relationship

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
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
    deleted_at = Column(BigInteger, nullable=True)
    deleted_by = Column(String, nullable=True)

    # Relationship to chat tasks
    chat_tasks = relationship(
        "ChatTaskModel", back_populates="session", cascade="all, delete-orphan"
    )
    project = relationship("ProjectModel", back_populates="sessions")


class CreateSessionModel(BaseModel):
    """Pydantic model for creating a session."""
    id: str
    name: str | None
    user_id: str
    agent_id: str | None
    project_id: str | None = None
    created_time: int
    updated_time: int


class UpdateSessionModel(BaseModel):
    """Pydantic model for updating a session."""
    name: str | None = None
    agent_id: str | None = None
    project_id: str | None = None
    updated_time: int
