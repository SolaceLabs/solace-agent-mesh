"""
SQLAlchemy model for app storage (key-value pairs scoped to user+app).
"""

from sqlalchemy import Column, String, Text, BigInteger, Index
from .base import Base


class AppStorageModel(Base):
    """
    Persistent key-value storage for SAM apps.

    Each record stores a single key-value pair, scoped to a user and app.
    Values are stored as JSON strings.
    """
    __tablename__ = "app_storage"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    app_id = Column(String(255), nullable=False, index=True)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)  # JSON-encoded value
    created_time = Column(BigInteger, nullable=False)
    updated_time = Column(BigInteger, nullable=False)

    # Composite index for efficient lookups
    __table_args__ = (
        Index("ix_app_storage_user_app_key", "user_id", "app_id", "key", unique=True),
    )

    def __repr__(self):
        return f"<AppStorageModel(user={self.user_id}, app={self.app_id}, key={self.key})>"
