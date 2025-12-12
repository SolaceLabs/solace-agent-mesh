"""
User profile SQLAlchemy model for storing user profile information.
"""

from sqlalchemy import Column, String, BigInteger, Index
from pydantic import BaseModel as PydanticBaseModel

from .base import Base


class UserProfileModel(Base):
    """
    User profile model for storing user-specific profile data.
    
    Stores user display information, avatar, and other profile settings.
    """

    __tablename__ = "user_profiles"

    # Primary key
    user_id = Column(String, primary_key=True, index=True)
    
    # Profile information
    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    avatar_url = Column(String, nullable=True)  # URL or path to user's avatar image
    avatar_storage_type = Column(String, nullable=True)  # 'local' or 's3'
    
    # Metadata
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    
    __table_args__ = (
        Index('ix_user_profiles_user_id', 'user_id', unique=True),
        Index('ix_user_profiles_email', 'email'),
    )


class CreateUserProfileModel(PydanticBaseModel):
    """Pydantic model for creating a user profile."""
    user_id: str
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    avatar_storage_type: str | None = None


class UpdateUserProfileModel(PydanticBaseModel):
    """Pydantic model for updating a user profile."""
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    avatar_storage_type: str | None = None