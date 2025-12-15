"""
SQLAlchemy model for app tags.
"""

from sqlalchemy import Column, String, BigInteger, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from .base import Base


class AppTagModel(Base):
    """
    SQLAlchemy model for app tags.

    This table stores tags associated with apps, enabling categorization
    and searchable tagging functionality.
    """

    __tablename__ = "app_tags"

    id = Column(String, primary_key=True)
    app_id = Column(String, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(100), nullable=False)  # The tag text (lowercase, normalized)
    created_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds

    # Ensure a tag can only be added once per app
    __table_args__ = (
        UniqueConstraint('app_id', 'tag', name='uq_app_tag'),
        Index('ix_app_tags_tag', 'tag'),  # For searching by tag
    )

    # Relationships
    app = relationship("AppModel", back_populates="tags")


class CreateAppTagModel(BaseModel):
    """Pydantic model for creating an app tag."""
    id: str
    app_id: str
    tag: str
    created_at: int
