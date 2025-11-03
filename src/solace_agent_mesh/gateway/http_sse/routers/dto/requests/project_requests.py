"""
Request DTOs for project-related API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    system_prompt: Optional[str] = Field(None, max_length=4000, description="Instructions for the project")
    default_agent_id: Optional[str] = Field(None, description="Default agent ID for new chats")
    file_metadata: Optional[str] = Field(None, description="JSON string containing file metadata")
    user_id: str


class UpdateProjectRequest(BaseModel):
    """Request to update an existing project."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt", max_length=4000, description="Instructions for the project")
    default_agent_id: Optional[str] = Field(None, alias="defaultAgentId", description="Default agent ID for new chats")


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


class ProjectFilter(BaseModel):
    """Filter criteria for retrieving projects."""
    user_id: Optional[str] = None
