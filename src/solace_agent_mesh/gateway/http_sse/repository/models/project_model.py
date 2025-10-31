"""
SQLAlchemy model for project data.
"""

from sqlalchemy import Column, String, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from .base import Base


class ProjectModel(Base):
    """SQLAlchemy model for projects."""
    
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    default_agent_id = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)  
    deleted_at = Column(BigInteger, nullable=True)   
    deleted_by = Column(String, nullable=True)       
    
    # Relationships
    sessions = relationship("SessionModel", back_populates="project")
    project_users = relationship("ProjectUserModel", back_populates="project", cascade="all, delete-orphan")


class CreateProjectModel(BaseModel):
    """Pydantic model for creating a project."""
    id: str
    name: str
    user_id: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    default_agent_id: str | None = None
    created_at: int
    updated_at: int | None = None


class UpdateProjectModel(BaseModel):
    """Pydantic model for updating a project."""
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    default_agent_id: str | None = None
    updated_at: int