"""
Project-related response DTOs.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from .base_responses import BaseTimestampResponse


class ProjectResponse(BaseTimestampResponse):
    """Response DTO for a project."""

    id: str
    name: str
    user_id: str = Field(alias="userId")
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    is_global: bool = Field(alias="isGlobal")
    template_id: Optional[str] = Field(default=None, alias="templateId")
    created_by_user_id: Optional[str] = Field(default=None, alias="createdByUserId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")


class ProjectListResponse(BaseModel):
    """Response DTO for a list of projects."""

    model_config = ConfigDict(populate_by_name=True)

    projects: list[ProjectResponse]
    total: int


class GlobalProjectResponse(BaseTimestampResponse):
    """Response DTO for a global project template."""

    id: str
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    created_by_user_id: Optional[str] = Field(default=None, alias="createdByUserId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")
    usage_count: int = Field(alias="usageCount")


class GlobalProjectListResponse(BaseModel):
    """Response DTO for a list of global project templates."""

    model_config = ConfigDict(populate_by_name=True)

    projects: list[GlobalProjectResponse]
    total: int