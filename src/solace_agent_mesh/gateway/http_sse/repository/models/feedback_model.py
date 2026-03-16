"""
Feedback SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, Index, String, Text

from .base import Base


class FeedbackModel(Base):
    """SQLAlchemy model for user feedback."""

    __tablename__ = "feedback"

    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), nullable=False)
    task_id = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    rating = Column(String(255), nullable=False)  # e.g., 'up', 'down'
    comment = Column(Text, nullable=True)
    created_time = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_feedback_task_id", "task_id"),
        Index("ix_feedback_user_id", "user_id"),
        Index("ix_feedback_created_time", "created_time"),
    )
