"""
SQLAlchemy model for project user access (junction table).
"""

from enum import Enum
from sqlalchemy import Column, String, BigInteger, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, field_validator
from typing import Literal

from .base import Base


class ProjectRole(str, Enum):
    """Valid roles for project users."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectUserModel(Base):
    """
    SQLAlchemy model for project user access.
    
    This junction table tracks which users have access to which projects,
    enabling multi-user collaboration on projects.
    """
    
    __tablename__ = "project_users"
    
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(SQLEnum(ProjectRole), nullable=False, default=ProjectRole.VIEWER)
    added_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds
    added_by_user_id = Column(String, nullable=False)  # User who granted access
    
    # Ensure a user can only be added once per project
    __table_args__ = (
        UniqueConstraint('project_id', 'user_id', name='uq_project_user'),
    )
    
    # Relationships
    project = relationship("ProjectModel", back_populates="project_users")


class CreateProjectUserModel(BaseModel):
    """Pydantic model for creating a project user access record."""
    id: str
    project_id: str
    user_id: str
    role: Literal["owner", "editor", "viewer"] = "viewer"
    added_at: int
    added_by_user_id: str
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is one of the allowed values."""
        if v not in [role.value for role in ProjectRole]:
            raise ValueError(f"Role must be one of: {', '.join([role.value for role in ProjectRole])}")
        return v


class UpdateProjectUserModel(BaseModel):
    """Pydantic model for updating a project user access record."""
    role: Literal["owner", "editor", "viewer"] | None = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        """Validate that role is one of the allowed values."""
        if v is not None and v not in [role.value for role in ProjectRole]:
            raise ValueError(f"Role must be one of: {', '.join([role.value for role in ProjectRole])}")
        return v