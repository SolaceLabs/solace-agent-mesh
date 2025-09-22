"""
Request DTOs for project-related API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    system_prompt: Optional[str] = Field(None, max_length=4000, description="System prompt for the project")
    file_metadata: Optional[str] = Field(None, description="JSON string containing file metadata")
    user_id: str


class UpdateProjectRequest(BaseModel):
    """Request to update an existing project."""
    
    project_id: str  # Set by router
    user_id: str  # Set by router
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    system_prompt: Optional[str] = Field(None, max_length=4000, description="System prompt for the project")


class CopyProjectRequest(BaseModel):
    """Request to copy a project from a template."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Name for the copied project")
    description: Optional[str] = Field(None, max_length=1000, description="Description for the copied project")


class GetProjectsRequest(BaseModel):
    """Request DTO for retrieving projects."""
    user_id: str


class GetProjectRequest(BaseModel):
    """Request DTO for retrieving a specific project."""
    project_id: str
    user_id: str


class DeleteProjectRequest(BaseModel):
    """Request DTO for deleting a project."""
    project_id: str
    user_id: str


class ProjectCopyRequest(BaseModel):
    """Domain model for copying a project from a template."""
    
    template_id: str
    new_name: str = Field(..., min_length=1, max_length=255)
    new_description: Optional[str] = Field(None, max_length=1000)
    user_id: str


class ProjectFilter(BaseModel):
    """Domain model for filtering projects."""
    
    user_id: Optional[str] = None
    is_global: Optional[bool] = None
    template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
