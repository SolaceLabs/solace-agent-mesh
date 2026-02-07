"""
SSE Event Buffer SQLAlchemy model.

This model stores SSE events for background tasks that need to be replayed
when the user returns to the session. Events are stored in sequence order
and can be fetched and replayed through the frontend's existing SSE processing.
"""

from sqlalchemy import BigInteger, Boolean, Column, Integer, JSON, String
from sqlalchemy.orm import relationship

from .base import Base


class SSEEventBufferModel(Base):
    """SQLAlchemy model for SSE event buffer entries."""

    __tablename__ = "sse_event_buffer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False)
    event_sequence = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSON, nullable=False)
    created_at = Column(BigInteger, nullable=False)  # Epoch milliseconds
    consumed = Column(Boolean, nullable=False, default=False, index=True)
    consumed_at = Column(BigInteger, nullable=True)  # Epoch milliseconds

    def __repr__(self):
        return (
            f"<SSEEventBufferModel(id={self.id}, task_id={self.task_id}, "
            f"event_sequence={self.event_sequence}, event_type={self.event_type}, "
            f"consumed={self.consumed})>"
        )
