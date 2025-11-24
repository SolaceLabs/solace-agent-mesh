"""
SQLAlchemy model for session tags.
"""

from sqlalchemy import Column, String, Integer, BigInteger, Index
from .base import Base


class SessionTagModel(Base):
    """SQLAlchemy model for session tags (bookmarks)."""
    
    __tablename__ = "session_tags"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    tag = Column(String, nullable=False)
    description = Column(String, nullable=True)
    count = Column(Integer, nullable=False, default=0)
    position = Column(Integer, nullable=False, default=0)
    created_time = Column(BigInteger, nullable=False)
    updated_time = Column(BigInteger, nullable=True)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_session_tags_user_id', 'user_id'),
        Index('ix_session_tags_tag', 'tag'),
        Index('ix_session_tags_user_id_tag', 'user_id', 'tag', unique=True),
        Index('ix_session_tags_user_id_position', 'user_id', 'position'),
    )