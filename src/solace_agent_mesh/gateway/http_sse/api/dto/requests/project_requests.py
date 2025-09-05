"""
Request DTOs for project-related API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")


class UpdateProjectRequest(BaseModel):
    """Request to update an existing project."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")


class CopyProjectRequest(BaseModel):
    """Request to copy a project from a template."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Name for the copied project")
    description: Optional[str] = Field(None, max_length=1000, description="Description for the copied project")