"""
App and AppVersion SQLAlchemy models for SAM Apps feature.
"""

from sqlalchemy import BigInteger, Boolean, Column, Integer, String, Text
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from ...shared import now_epoch_ms
from .base import Base


class AppModel(Base):
    """SQLAlchemy model for apps."""

    __tablename__ = "apps"

    id = Column(String, primary_key=True)
    app_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    workspace_id = Column(String(255), nullable=False)
    is_public = Column(Boolean, nullable=False, default=False)
    status = Column(String(50), nullable=False, default="draft", index=True)
    current_version = Column(Integer, nullable=False, default=0)

    # Environment-specific deployed versions (semver strings like "1.2.3")
    # Each environment can have a different version deployed
    dev_version = Column(String(50), nullable=True)  # Version deployed to dev
    staging_version = Column(String(50), nullable=True)  # Version deployed to staging
    prod_version = Column(String(50), nullable=True)  # Version deployed to prod

    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(
        BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms
    )
    archived_time = Column(BigInteger, nullable=True)

    # Relationships
    app_users = relationship("AppUserModel", back_populates="app", cascade="all, delete-orphan")
    tags = relationship("AppTagModel", back_populates="app", cascade="all, delete-orphan")


class AppVersionModel(Base):
    """SQLAlchemy model for app versions."""

    __tablename__ = "app_versions"

    id = Column(String, primary_key=True)
    app_id = Column(String(255), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    deployed_time = Column(BigInteger, nullable=False, index=True)
    build_path = Column(String(500), nullable=False)
    git_commit = Column(String(100), nullable=True)


class CreateAppModel(BaseModel):
    """Pydantic model for creating an app."""
    id: str
    app_id: str
    user_id: str
    name: str
    description: str | None
    workspace_id: str
    is_public: bool = False
    status: str
    current_version: int
    dev_version: str | None = None
    staging_version: str | None = None
    prod_version: str | None = None
    created_time: int
    updated_time: int


class UpdateAppModel(BaseModel):
    """Pydantic model for updating an app."""
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None
    status: str | None = None
    current_version: int | None = None
    dev_version: str | None = None
    staging_version: str | None = None
    prod_version: str | None = None
