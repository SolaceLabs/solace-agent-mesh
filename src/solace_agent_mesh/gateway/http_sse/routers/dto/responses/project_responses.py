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
    created_by_user_id: str = Field(alias="createdByUserId")
    created_at: int = Field(alias="createdAt")
    updated_at: Optional[int] = Field(default=None, alias="updatedAt")


class ProjectListResponse(BaseModel):
    """Response DTO for a list of projects."""

    model_config = ConfigDict(populate_by_name=True)

    projects: list[ProjectResponse]
    total: int
