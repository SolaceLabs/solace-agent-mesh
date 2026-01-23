"""
Share link SQLAlchemy model and Pydantic models for strongly-typed operations.
"""

from sqlalchemy import BigInteger, Boolean, Column, String, Text
from pydantic import BaseModel, Field
from typing import Optional, List

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from .base import Base


class SharedLinkModel(Base):
    """SQLAlchemy model for shared links."""

    __tablename__ = "shared_links"

    share_id = Column(String(21), primary_key=True)  # nanoid
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    require_authentication = Column(Boolean, default=False, nullable=False, index=True)
    allowed_domains = Column(Text, nullable=True)  # Comma-separated list
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_time = Column(BigInteger, nullable=False, default=now_epoch_ms, onupdate=now_epoch_ms)
    deleted_at = Column(BigInteger, nullable=True)


class SharedArtifactModel(Base):
    """SQLAlchemy model for tracking artifacts in shared links."""

    __tablename__ = "shared_artifacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    share_id = Column(String(21), nullable=False, index=True)
    artifact_uri = Column(String(1000), nullable=False)
    artifact_version = Column(BigInteger, nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    created_time = Column(BigInteger, nullable=False, default=now_epoch_ms)


class CreateShareLinkRequest(BaseModel):
    """Pydantic model for creating a share link."""
    require_authentication: bool = Field(default=False, description="Require login to view")
    allowed_domains: Optional[List[str]] = Field(default=None, description="Allowed email domains")


class UpdateShareLinkRequest(BaseModel):
    """Pydantic model for updating a share link."""
    require_authentication: Optional[bool] = None
    allowed_domains: Optional[List[str]] = None


class ShareLinkResponse(BaseModel):
    """Response model for share link operations."""
    share_id: str
    session_id: str
    title: str
    is_public: bool
    require_authentication: bool
    allowed_domains: Optional[List[str]]
    access_type: str  # "public", "authenticated", or "domain-restricted"
    created_time: int
    share_url: str


class ShareLinkItem(BaseModel):
    """List item model for share links."""
    share_id: str
    session_id: str
    title: str
    is_public: bool
    require_authentication: bool
    allowed_domains: Optional[List[str]]
    access_type: str
    created_time: int
    message_count: int


class SharedSessionView(BaseModel):
    """Public view of a shared session."""
    share_id: str
    title: str
    created_time: int
    access_type: str
    tasks: List[dict]  # Anonymized chat tasks
    artifacts: List[dict]  # Public artifact info
