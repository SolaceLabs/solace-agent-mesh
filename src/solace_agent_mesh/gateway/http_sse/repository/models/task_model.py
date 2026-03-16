"""
Task SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import relationship

from .base import Base


class TaskModel(Base):
    """SQLAlchemy model for tasks."""

    __tablename__ = "tasks"

    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    parent_task_id = Column(String(255), nullable=True, index=True)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=True)
    status = Column(String(255), nullable=True)
    # ix_tasks_initial_request_text was dropped by migration 20251015_session_idx
    initial_request_text = Column(Text, nullable=True)

    # Token usage columns
    total_input_tokens = Column(Integer, nullable=True)
    total_output_tokens = Column(Integer, nullable=True)
    total_cached_input_tokens = Column(Integer, nullable=True)
    token_usage_details = Column(JSON, nullable=True)

    # Background task execution columns — indexes use idx_ prefix from migration 20251126
    execution_mode = Column(String(20), nullable=True, default="foreground")
    last_activity_time = Column(BigInteger, nullable=True)
    background_execution_enabled = Column(Boolean, nullable=True, default=False)
    max_execution_time_ms = Column(BigInteger, nullable=True)

    # SSE event buffer state columns — indexes use idx_ prefix from migration 20260207_sse_event_buffer
    session_id = Column(String(255), nullable=True)
    events_buffered = Column(Boolean, nullable=True, default=False)
    events_consumed = Column(Boolean, nullable=True, default=False)

    __table_args__ = (
        # Added by migration 20251006
        Index("ix_tasks_start_time", "start_time"),
        # Added by migration 20251015_session_idx
        Index("ix_tasks_user_start_time", "user_id", text("start_time DESC")),
        # Added by migration 20251126_background_tasks (idx_ prefix, not ix_)
        Index("idx_tasks_execution_mode", "execution_mode"),
        Index("idx_tasks_last_activity", "last_activity_time"),
        # Added by migration 20260207_sse_event_buffer (idx_ prefix, not ix_)
        Index("idx_tasks_session_id", "session_id"),
        Index("idx_tasks_events_buffered", "events_buffered"),
    )

    # Relationship to events
    events = relationship(
        "TaskEventModel", back_populates="task", cascade="all, delete-orphan"
    )
