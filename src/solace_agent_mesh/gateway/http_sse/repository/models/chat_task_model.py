"""
ChatTask SQLAlchemy model.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, String, Text

from .base import Base


class ChatTaskModel(Base):
    """SQLAlchemy model for chat tasks."""

    __tablename__ = "chat_tasks"

    id = Column(String, primary_key=True)
    session_id = Column(
        String,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(String, nullable=False, index=True)
    user_message = Column(Text, nullable=True)
    message_bubbles = Column(Text, nullable=False)
    task_metadata = Column(Text, nullable=True)
    created_time = Column(BigInteger, nullable=False, index=True)
    updated_time = Column(BigInteger, nullable=True)
