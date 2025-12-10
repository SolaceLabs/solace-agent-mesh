"""Request models for app-related endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class CreateAppRequest(BaseModel):
    """Request to create a new app."""

    name: str = Field(..., min_length=1, max_length=255, description="App name")
    description: Optional[str] = Field(None, description="App description")

    model_config = {"populate_by_name": True}


class UpdateAppRequest(BaseModel):
    """Request to update app metadata."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="App name")
    description: Optional[str] = Field(None, description="App description")

    model_config = {"populate_by_name": True}


class DeployAppRequest(BaseModel):
    """Request to deploy an app."""

    # No parameters needed - deployment uses current workspace state
    pass
