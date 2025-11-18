"""
Project-related response DTOs.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

from .base_responses import BaseTimestampResponse


class ProjectResponse(BaseTimestampResponse):
    """Response DTO for a project."""

    id: str
    name: str
    user_id: str = Field(alias="userId")
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    default_agent_id: Optional[str] = Field(default=None, alias="defaultAgentId")
    artifact_count: Optional[int] = Field(default=None, alias="artifactCount")
    created_at: int = Field(alias="createdAt")
    updated_at: Optional[int] = Field(default=None, alias="updatedAt")


class ProjectListResponse(BaseModel):
    """Response DTO for a list of projects."""

    model_config = ConfigDict(populate_by_name=True)

    projects: list[ProjectResponse]
    total: int
