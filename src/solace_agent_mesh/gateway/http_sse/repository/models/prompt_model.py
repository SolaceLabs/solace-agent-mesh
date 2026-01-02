"""
Prompt SQLAlchemy models for prompt library feature.
"""

from enum import Enum
from sqlalchemy import BigInteger, Column, String, Text, Integer, Boolean, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from .base import Base


class PromptGroupRole(str, Enum):
    """Valid roles for prompt group users."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class PromptGroupModel(Base):
    """SQLAlchemy model for prompt groups"""
    
    __tablename__ = "prompt_groups"
    
    # Primary key - String type (not UUID)
    id = Column(String, primary_key=True)
    
    # Core fields
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    command = Column(String(50), nullable=True, unique=True, index=True)
    
    # Ownership
    user_id = Column(String, nullable=False, index=True)
    author_name = Column(String(255), nullable=True)
    
    # Production prompt reference
    production_prompt_id = Column(
        String, 
        ForeignKey("prompts.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Sharing (optional - for future enhancement)
    is_shared = Column(Boolean, default=False, nullable=False)
    
    # User preferences
    is_pinned = Column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamps - BigInteger (epoch milliseconds) to match SAM convention
    created_at = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_at = Column(
        BigInteger, 
        nullable=False, 
        default=now_epoch_ms, 
        onupdate=now_epoch_ms
    )
    
    # Relationships
    prompts = relationship(
        "PromptModel",
        back_populates="group",
        foreign_keys="PromptModel.group_id",
        cascade="all, delete-orphan"
    )
    production_prompt = relationship(
        "PromptModel",
        foreign_keys=[production_prompt_id],
        post_update=True
    )
    prompt_group_users = relationship(
        "PromptGroupUserModel",
        back_populates="prompt_group",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<PromptGroupModel(id={self.id}, name={self.name}, command={self.command})>"


class PromptModel(Base):
    """SQLAlchemy model for individual prompt versions"""
    
    __tablename__ = "prompts"
    
    # Primary key - String type (not UUID)
    id = Column(String, primary_key=True)
    
    # Content
    prompt_text = Column(Text, nullable=False)
    
    # Versioned metadata fields (copied from group at version creation time)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    command = Column(String(50), nullable=True)
    
    # Group relationship
    group_id = Column(
        String,
        ForeignKey("prompt_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Ownership
    user_id = Column(String, nullable=False, index=True)
    
    # Versioning
    version = Column(Integer, default=1, nullable=False)
    
    # Timestamps - BigInteger (epoch milliseconds)
    created_at = Column(BigInteger, nullable=False, default=now_epoch_ms)
    updated_at = Column(
        BigInteger,
        nullable=False,
        default=now_epoch_ms,
        onupdate=now_epoch_ms
    )
    
    # Relationships
    group = relationship(
        "PromptGroupModel",
        back_populates="prompts",
        foreign_keys=[group_id]
    )
    
    def __repr__(self):
        return f"<PromptModel(id={self.id}, group_id={self.group_id}, version={self.version})>"


class PromptGroupUserModel(Base):
    """
    SQLAlchemy model for prompt group user access.
    
    This junction table tracks which users have access to which prompt groups,
    enabling multi-user collaboration on prompts with role-based permissions.
    """
    
    __tablename__ = "prompt_group_users"
    
    id = Column(String, primary_key=True)
    prompt_group_id = Column(String, ForeignKey("prompt_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(SQLEnum(PromptGroupRole), nullable=False, default=PromptGroupRole.VIEWER)
    added_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds
    added_by_user_id = Column(String, nullable=False)  # User who granted access
    
    # Ensure a user can only be added once per prompt group
    __table_args__ = (
        UniqueConstraint('prompt_group_id', 'user_id', name='uq_prompt_group_user'),
    )
    
    # Relationships
    prompt_group = relationship("PromptGroupModel", back_populates="prompt_group_users")
    
    def __repr__(self):
        return f"<PromptGroupUserModel(id={self.id}, prompt_group_id={self.prompt_group_id}, user_id={self.user_id}, role={self.role})>"