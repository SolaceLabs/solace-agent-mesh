"""
Feedback SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, String, Text

from .base import Base


class FeedbackModel(Base):
    """SQLAlchemy model for user feedback."""

    __tablename__ = "feedback"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    task_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    rating = Column(String, nullable=False)  # e.g., 'up', 'down'
    comment = Column(Text, nullable=True)
    created_time = Column(BigInteger, nullable=False)
