"""
SQLAlchemy models for the skill learning system.

These models define the database schema for storing skills,
feedback, usage tracking, and the learning queue.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    JSON,
    Index,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class SkillModel(Base):
    """SQLAlchemy model for skills."""
    
    __tablename__ = "skills"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Classification
    type = Column(String(20), nullable=False, index=True)  # learned, authored
    scope = Column(String(20), nullable=False, index=True)  # agent, user, shared, global
    
    # Ownership
    owner_agent_name = Column(String(255), nullable=True, index=True)
    owner_user_id = Column(String(255), nullable=True, index=True)
    
    # Content
    markdown_content = Column(Text, nullable=True)
    agent_chain = Column(JSON, nullable=True)  # List[AgentChainNode]
    tool_steps = Column(JSON, nullable=True)  # List[AgentToolStep]
    
    # Source tracking
    source_task_id = Column(String(36), nullable=True, index=True)
    related_task_ids = Column(JSON, nullable=True)  # List[str]
    involved_agents = Column(JSON, nullable=True)  # List[str]
    summary = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(Integer, nullable=False, index=True)
    updated_at = Column(Integer, nullable=False)
    
    # Feedback metrics
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    user_corrections = Column(Integer, default=0)
    last_feedback_at = Column(Integer, nullable=True)
    
    # Refinement tracking
    parent_skill_id = Column(String(36), nullable=True, index=True)
    refinement_reason = Column(Text, nullable=True)
    
    # Quality metrics
    complexity_score = Column(Integer, default=0)
    
    # Embedding for vector search (stored as JSON array)
    embedding = Column(JSON, nullable=True)
    
    # Relationships
    shares = relationship("SkillShareModel", back_populates="skill", cascade="all, delete-orphan")
    feedback = relationship("SkillFeedbackModel", back_populates="skill", cascade="all, delete-orphan")
    usages = relationship("SkillUsageModel", back_populates="skill", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Composite indexes for common queries
        Index("ix_skills_scope_owner_agent", "scope", "owner_agent_name"),
        Index("ix_skills_scope_owner_user", "scope", "owner_user_id"),
        Index("ix_skills_type_scope", "type", "scope"),
    )


class SkillShareModel(Base):
    """SQLAlchemy model for skill sharing relationships."""
    
    __tablename__ = "skill_shares"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(String(255), nullable=False, index=True)
    shared_by_user_id = Column(String(255), nullable=False, index=True)
    shared_at = Column(Integer, nullable=False)
    
    # Relationship
    skill = relationship("SkillModel", back_populates="shares")
    
    __table_args__ = (
        Index("ix_skill_shares_skill_user", "skill_id", "shared_with_user_id"),
    )


class SkillFeedbackModel(Base):
    """SQLAlchemy model for skill feedback."""
    
    __tablename__ = "skill_feedback"
    
    id = Column(String(36), primary_key=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    feedback_type = Column(String(50), nullable=False, index=True)
    correction_text = Column(Text, nullable=True)
    created_at = Column(Integer, nullable=False, index=True)
    
    # Relationship
    skill = relationship("SkillModel", back_populates="feedback")


class SkillUsageModel(Base):
    """SQLAlchemy model for skill usage tracking."""
    
    __tablename__ = "skill_usages"
    
    id = Column(String(36), primary_key=True)
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    used_at = Column(Integer, nullable=False, index=True)
    
    # Relationship
    skill = relationship("SkillModel", back_populates="usages")
    
    __table_args__ = (
        Index("ix_skill_usages_skill_agent", "skill_id", "agent_name"),
    )


class LearningQueueModel(Base):
    """SQLAlchemy model for the learning queue."""
    
    __tablename__ = "learning_queue"
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    status = Column(String(20), nullable=False, index=True)  # pending, processing, completed, failed
    queued_at = Column(Integer, nullable=False, index=True)
    started_at = Column(Integer, nullable=True)
    completed_at = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index("ix_learning_queue_status_queued", "status", "queued_at"),
    )


class SkillEmbeddingModel(Base):
    """
    Separate table for skill embeddings to support vector search.
    
    This allows for more efficient vector operations and potential
    integration with vector databases like pgvector.
    """
    
    __tablename__ = "skill_embeddings"
    
    skill_id = Column(String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    embedding_model = Column(String(100), nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    embedding = Column(JSON, nullable=False)  # List[float]
    created_at = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index("ix_skill_embeddings_model", "embedding_model"),
    )