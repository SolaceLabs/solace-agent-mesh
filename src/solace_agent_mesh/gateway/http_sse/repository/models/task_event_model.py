"""
Task Event SQLAlchemy model.
"""

from sqlalchemy import JSON, BigInteger, Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class TaskEventModel(Base):
    """SQLAlchemy model for A2A task events."""

    __tablename__ = "task_events"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id = Column(String, nullable=True, index=True)
    created_time = Column(BigInteger, nullable=False)
    topic = Column(Text, nullable=False)
    direction = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)

    # Relationship to task
    task = relationship("TaskModel", back_populates="events")
