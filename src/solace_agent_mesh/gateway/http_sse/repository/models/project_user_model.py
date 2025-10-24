"""
SQLAlchemy model for project user access (junction table).
"""

from sqlalchemy import Column, String, BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from .base import Base


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
    role = Column(String, nullable=False, default="viewer")  # e.g., "owner", "editor", "viewer"
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
    role: str = "viewer"
    added_at: int
    added_by_user_id: str


class UpdateProjectUserModel(BaseModel):
    """Pydantic model for updating a project user access record."""
    role: str | None = None