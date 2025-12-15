"""
SQLAlchemy model for app user access (junction table).
"""

from enum import Enum
from sqlalchemy import Column, String, BigInteger, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, field_validator
from typing import Literal

from .base import Base


class AppRole(str, Enum):
    """Valid roles for app users."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class AppUserModel(Base):
    """
    SQLAlchemy model for app user access.

    This junction table tracks which users have access to which apps,
    enabling multi-user collaboration on apps.
    """

    __tablename__ = "app_users"

    id = Column(String, primary_key=True)
    app_id = Column(String, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(SQLEnum(AppRole), nullable=False, default=AppRole.VIEWER)
    added_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds
    added_by_user_id = Column(String, nullable=False)  # User who granted access

    # Ensure a user can only be added once per app
    __table_args__ = (
        UniqueConstraint('app_id', 'user_id', name='uq_app_user'),
    )

    # Relationships
    app = relationship("AppModel", back_populates="app_users")


class CreateAppUserModel(BaseModel):
    """Pydantic model for creating an app user access record."""
    id: str
    app_id: str
    user_id: str
    role: Literal["owner", "editor", "viewer"] = "viewer"
    added_at: int
    added_by_user_id: str

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is one of the allowed values."""
        if v not in [role.value for role in AppRole]:
            raise ValueError(f"Role must be one of: {', '.join([role.value for role in AppRole])}")
        return v


class UpdateAppUserModel(BaseModel):
    """Pydantic model for updating an app user access record."""
    role: Literal["owner", "editor", "viewer"] | None = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        """Validate that role is one of the allowed values."""
        if v is not None and v not in [role.value for role in AppRole]:
            raise ValueError(f"Role must be one of: {', '.join([role.value for role in AppRole])}")
        return v
