"""
Task SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class TaskModel(Base):
    """SQLAlchemy model for tasks."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=True)
    status = Column(String, nullable=True)
    initial_request_text = Column(Text, nullable=True, index=True)

    # Relationship to events
    events = relationship(
        "TaskEventModel", back_populates="task", cascade="all, delete-orphan"
    )
