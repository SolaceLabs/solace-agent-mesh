"""Response models for app-related endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class AppResponse(BaseModel):
    """Response model for app metadata."""

    id: str = Field(..., description="App unique identifier")
    app_id: str = Field(..., alias="appId", description="App ID (URL-friendly)")
    user_id: str = Field(..., alias="userId", description="User ID who owns the app")
    name: str = Field(..., description="App display name")
    description: Optional[str] = Field(None, description="App description")
    workspace_id: str = Field(..., alias="workspaceId", description="Associated workspace ID")
    status: str = Field(..., description="App status: draft, deployed, archived")
    current_version: int = Field(..., alias="currentVersion", description="Current deployed version number")
    created_time: int = Field(..., alias="createdTime", description="Creation timestamp (milliseconds since epoch)")
    updated_time: int = Field(..., alias="updatedTime", description="Last update timestamp (milliseconds since epoch)")
    archived_time: Optional[int] = Field(None, alias="archivedTime", description="Archive timestamp if archived")

    model_config = {"populate_by_name": True}


class AppVersionResponse(BaseModel):
    """Response model for app version metadata."""

    id: str = Field(..., description="Version unique identifier")
    app_id: str = Field(..., alias="appId", description="App ID")
    version_number: int = Field(..., alias="versionNumber", description="Version number")
    deployed_time: int = Field(..., alias="deployedTime", description="Deployment timestamp (milliseconds since epoch)")
    build_path: str = Field(..., alias="buildPath", description="Path to build artifacts")
    git_commit: Optional[str] = Field(None, alias="gitCommit", description="Git commit SHA")

    model_config = {"populate_by_name": True}


class CreateAppResponse(BaseModel):
    """Response after creating a new app."""

    app_id: str = Field(..., alias="appId", description="Created app ID")
    workspace_path: str = Field(..., alias="workspacePath", description="Workspace directory path")
    workspace_id: str = Field(..., alias="workspaceId", description="Workspace identifier")
    status: str = Field(..., description="Initial status (draft)")

    model_config = {"populate_by_name": True}


class DeployAppResponse(BaseModel):
    """Response after deploying an app."""

    success: bool = Field(..., description="Whether deployment succeeded")
    version: Optional[int] = Field(None, description="Deployed version number if successful")
    errors: Optional[list[str]] = Field(None, description="Build errors if deployment failed")

    model_config = {"populate_by_name": True}


class DevServerResponse(BaseModel):
    """Response with dev server information."""

    dev_server_url: str = Field(..., alias="devServerUrl", description="URL to access dev server via proxy")
    status: str = Field(..., description="Dev server status: starting, running, stopped")

    model_config = {"populate_by_name": True}
