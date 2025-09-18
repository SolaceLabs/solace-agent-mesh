"""
SQLAlchemy model for project data.
"""

from sqlalchemy import Column, String, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship

from .base import Base


class ProjectModel(Base):
    """SQLAlchemy model for projects."""
    
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    user_id = Column(String, nullable=True)  # Null for global projects
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    is_global = Column(Boolean, default=False, nullable=False)
    template_id = Column(String, nullable=True)  # Reference to template project
    created_by_user_id = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)  # Epoch timestamp in milliseconds
    updated_at = Column(BigInteger, nullable=True)   # Epoch timestamp in milliseconds
    
    # Relationships
    sessions = relationship("SessionModel", back_populates="project")