"""
Prompt SQLAlchemy models for prompt library feature.
Adapted for SAM fork with epoch millisecond timestamps and String IDs.
"""

from sqlalchemy import BigInteger, Column, String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ...shared import now_epoch_ms
from .base import Base


class PromptGroupModel(Base):
    """SQLAlchemy model for prompt groups - adapted for SAM fork."""
    
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
    
    def __repr__(self):
        return f"<PromptGroupModel(id={self.id}, name={self.name}, command={self.command})>"


class PromptModel(Base):
    """SQLAlchemy model for individual prompt versions - adapted for SAM fork."""
    
    __tablename__ = "prompts"
    
    # Primary key - String type (not UUID)
    id = Column(String, primary_key=True)
    
    # Content
    prompt_text = Column(Text, nullable=False)
    
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