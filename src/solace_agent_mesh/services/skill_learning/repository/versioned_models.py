"""
SQLAlchemy models for the skill versioning system.

These models implement the versioning pattern similar to prompts:
- SkillGroupModel: Container for skill versions
- SkillVersionModel: Individual versions of a skill
- SkillGroupUserModel: Sharing/access control for skill groups
"""

from enum import Enum
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    JSON,
    Index,
    ForeignKey,
    Boolean,
    BigInteger,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from .models import Base


class SkillGroupRole(str, Enum):
    """Valid roles for skill group users."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class SkillGroupModel(Base):
    """
    SQLAlchemy model for skill groups (containers for versions).
    
    A skill group represents a logical skill that can have multiple versions.
    Only one version is "production" (active) at a time.
    """
    
    __tablename__ = "skill_groups"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Core fields
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    
    # Classification
    type = Column(String(20), nullable=False, index=True)  # learned, authored
    scope = Column(String(20), nullable=False, index=True)  # agent, user, shared, global
    
    # Ownership
    owner_agent_name = Column(String(255), nullable=True, index=True)
    owner_user_id = Column(String(255), nullable=True, index=True)
    
    # Production version reference
    production_version_id = Column(
        String(36),
        ForeignKey("skill_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True
    )
    
    # Status
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    
    # Timestamps (epoch ms)
    created_at = Column(BigInteger, nullable=False, index=True)
    updated_at = Column(BigInteger, nullable=False)
    
    # Relationships
    versions = relationship(
        "SkillVersionModel",
        back_populates="group",
        foreign_keys="SkillVersionModel.group_id",
        cascade="all, delete-orphan",
        order_by="SkillVersionModel.version.desc()"
    )
    production_version = relationship(
        "SkillVersionModel",
        foreign_keys=[production_version_id],
        post_update=True
    )
    users = relationship(
        "SkillGroupUserModel",
        back_populates="skill_group",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        # Unique constraint: name must be unique per agent
        UniqueConstraint('owner_agent_name', 'name', name='uq_skill_group_agent_name'),
        Index("ix_skill_groups_scope_owner_agent", "scope", "owner_agent_name"),
        Index("ix_skill_groups_scope_owner_user", "scope", "owner_user_id"),
        Index("ix_skill_groups_type_scope", "type", "scope"),
    )
    
    def __repr__(self):
        return f"<SkillGroupModel(id={self.id}, name={self.name}, scope={self.scope})>"


class SkillVersionModel(Base):
    """
    SQLAlchemy model for individual skill versions.
    
    Each version contains the full skill content and metadata.
    Versions are immutable once created.
    """
    
    __tablename__ = "skill_versions"
    
    # Primary key
    id = Column(String(36), primary_key=True)
    
    # Group relationship
    group_id = Column(
        String(36),
        ForeignKey("skill_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Version number (1, 2, 3, ...)
    version = Column(Integer, nullable=False)
    
    # Content
    description = Column(Text, nullable=False)
    markdown_content = Column(Text, nullable=True)
    agent_chain = Column(JSON, nullable=True)  # List[AgentChainNode]
    tool_steps = Column(JSON, nullable=True)  # List[AgentToolStep]
    summary = Column(Text, nullable=True)
    
    # Source tracking
    source_task_id = Column(String(36), nullable=True, index=True)
    related_task_ids = Column(JSON, nullable=True)  # List[str]
    involved_agents = Column(JSON, nullable=True)  # List[str]
    
    # Embedding for vector search
    embedding = Column(JSON, nullable=True)
    
    # Quality metrics
    complexity_score = Column(Integer, default=0)
    
    # Bundled resources (scripts, data files)
    # URI reference to storage location (s3:// or file://)
    bundled_resources_uri = Column(String(500), nullable=True)
    # Manifest of included files: {"scripts": [...], "resources": [...]}
    bundled_resources_manifest = Column(JSON, nullable=True)
    
    # Version metadata
    created_by_user_id = Column(String(255), nullable=True, index=True)
    creation_reason = Column(Text, nullable=True)
    
    # Timestamps (epoch ms)
    created_at = Column(BigInteger, nullable=False, index=True)
    
    # Relationships
    group = relationship(
        "SkillGroupModel",
        back_populates="versions",
        foreign_keys=[group_id]
    )
    
    __table_args__ = (
        # Unique constraint: version number must be unique per group
        UniqueConstraint('group_id', 'version', name='uq_skill_version_group_version'),
        Index("ix_skill_versions_group_version", "group_id", "version"),
    )
    
    def __repr__(self):
        return f"<SkillVersionModel(id={self.id}, group_id={self.group_id}, version={self.version})>"


class SkillGroupUserModel(Base):
    """
    SQLAlchemy model for skill group user access.
    
    This junction table tracks which users have access to which skill groups,
    enabling multi-user collaboration on skills with role-based permissions.
    """
    
    __tablename__ = "skill_group_users"
    
    id = Column(String(36), primary_key=True)
    skill_group_id = Column(
        String(36),
        ForeignKey("skill_groups.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(String(255), nullable=False, index=True)
    role = Column(SQLEnum(SkillGroupRole), nullable=False, default=SkillGroupRole.VIEWER)
    added_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds
    added_by_user_id = Column(String(255), nullable=False)  # User who granted access
    
    # Ensure a user can only be added once per skill group
    __table_args__ = (
        UniqueConstraint('skill_group_id', 'user_id', name='uq_skill_group_user'),
        Index("ix_skill_group_users_user_group", "user_id", "skill_group_id"),
        Index("ix_skill_group_users_user_role", "user_id", "role"),
    )
    
    # Relationships
    skill_group = relationship("SkillGroupModel", back_populates="users")
    
    def __repr__(self):
        return f"<SkillGroupUserModel(id={self.id}, skill_group_id={self.skill_group_id}, user_id={self.user_id}, role={self.role})>"