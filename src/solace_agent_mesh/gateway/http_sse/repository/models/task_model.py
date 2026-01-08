"""
Task SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Boolean, Column, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class TaskModel(Base):
    """SQLAlchemy model for tasks."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    parent_task_id = Column(String, nullable=True, index=True)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=True)
    status = Column(String, nullable=True)
    initial_request_text = Column(Text, nullable=True, index=True)
    
    # Token usage columns
    total_input_tokens = Column(Integer, nullable=True)
    total_output_tokens = Column(Integer, nullable=True)
    total_cached_input_tokens = Column(Integer, nullable=True)
    token_usage_details = Column(JSON, nullable=True)
    
    # Background task execution columns
    execution_mode = Column(String(20), nullable=True, default="foreground", index=True)
    last_activity_time = Column(BigInteger, nullable=True, index=True)
    background_execution_enabled = Column(Boolean, nullable=True, default=False)
    max_execution_time_ms = Column(BigInteger, nullable=True)

    # Relationship to events
    events = relationship(
        "TaskEventModel", back_populates="task", cascade="all, delete-orphan"
    )
