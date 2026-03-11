"""
Share link SQLAlchemy model and Pydantic models for strongly-typed operations.
"""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
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

    # Relationships
    shared_users = relationship("SharedLinkUserModel", back_populates="shared_link", cascade="all, delete-orphan")


class SharedLinkUserModel(Base):
    """SQLAlchemy model for tracking users with access to shared links."""

    __tablename__ = "shared_link_users"

    id = Column(String, primary_key=True)
    share_id = Column(String(21), ForeignKey("shared_links.share_id", ondelete="CASCADE"), nullable=False)
    user_email = Column(String(255), nullable=False)
    access_level = Column(String(50), nullable=False, default="RESOURCE_VIEWER")
    added_at = Column(BigInteger, nullable=False)
    added_by_user_id = Column(String(255), nullable=False)

    # Ensure a user can only be added once per share
    __table_args__ = (
        UniqueConstraint('share_id', 'user_email', name='uq_shared_link_user'),
    )

    # Relationships
    shared_link = relationship("SharedLinkModel", back_populates="shared_users")


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
    require_authentication: bool = Field(default=True, description="Require login to view (always True, public access not supported)")
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


class SharedArtifactInfo(BaseModel):
    """Artifact info for shared sessions."""
    filename: str
    mime_type: str
    size: int  # in bytes
    last_modified: Optional[str] = None  # ISO 8601 timestamp
    version: Optional[int] = None
    version_count: Optional[int] = None
    description: Optional[str] = None
    source: Optional[str] = None


class SharedTaskEvents(BaseModel):
    """Task events for workflow visualization in shared sessions."""
    task_id: str
    events: List[dict]  # A2AEventSSEPayload format
    initial_request_text: Optional[str] = None


class SharedSessionView(BaseModel):
    """Public view of a shared session."""
    share_id: str
    title: str
    created_time: int
    access_type: str
    tasks: List[dict]  # Anonymized chat tasks
    artifacts: List[SharedArtifactInfo]  # Full artifact info for side panel
    task_events: Optional[dict] = None  # Task events for workflow visualization: {task_id: SharedTaskEvents}
    is_owner: bool = False  # Whether the current viewer is the owner of the shared chat
    session_id: Optional[str] = None  # Original session ID (only included for owner)


# User-specific sharing models

class SharedLinkUserInfo(BaseModel):
    """Info about a user with access to a shared link."""
    user_email: str
    access_level: str
    added_at: int


class ShareUsersResponse(BaseModel):
    """Response model for getting share users."""
    share_id: str
    owner_email: str
    users: List[SharedLinkUserInfo]


class AddShareUserRequest(BaseModel):
    """Request to add a user to a share."""
    user_email: str = Field(..., description="Email of user to share with")
    access_level: str = Field(default="RESOURCE_VIEWER", description="Access level for the user")


class BatchAddShareUsersRequest(BaseModel):
    """Request to add multiple users to a share."""
    shares: List[AddShareUserRequest]


class BatchAddShareUsersResponse(BaseModel):
    """Response for batch adding users to a share."""
    added_count: int
    users: List[SharedLinkUserInfo]


class BatchDeleteShareUsersRequest(BaseModel):
    """Request to remove multiple users from a share."""
    user_emails: List[str]


class BatchDeleteShareUsersResponse(BaseModel):
    """Response for batch removing users from a share."""
    deleted_count: int


class SharedWithMeItem(BaseModel):
    """Item representing a chat shared with the current user."""
    share_id: str
    title: str
    owner_email: str
    access_level: str
    shared_at: int  # epoch ms when the share was added
    share_url: str = ""


class ForkSharedChatResponse(BaseModel):
    """Response for forking a shared chat into the user's own sessions."""
    session_id: str
    session_name: str
    message: str = "Chat forked successfully"
