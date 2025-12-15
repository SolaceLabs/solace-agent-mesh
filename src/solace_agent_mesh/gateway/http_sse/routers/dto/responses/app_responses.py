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
    is_public: bool = Field(False, alias="isPublic", description="Whether the app is publicly visible")
    is_owner: bool = Field(False, alias="isOwner", description="Whether the current user is the owner")
    created_by_user_id: str = Field(..., alias="createdByUserId", description="User ID who created the app")
    status: str = Field(..., description="App status: draft, deployed, archived")
    current_version: int = Field(..., alias="currentVersion", description="Current deployed version number")
    dev_version: Optional[str] = Field(None, alias="devVersion", description="Version deployed to dev environment")
    staging_version: Optional[str] = Field(None, alias="stagingVersion", description="Version deployed to staging environment")
    prod_version: Optional[str] = Field(None, alias="prodVersion", description="Version deployed to prod environment")
    icon_emoji: Optional[str] = Field(None, alias="iconEmoji", description="Emoji for the app icon")
    icon_background: Optional[str] = Field(None, alias="iconBackground", description="Background color/gradient for the icon")
    created_time: int = Field(..., alias="createdTime", description="Creation timestamp (milliseconds since epoch)")
    updated_time: int = Field(..., alias="updatedTime", description="Last update timestamp (milliseconds since epoch)")
    archived_time: Optional[int] = Field(None, alias="archivedTime", description="Archive timestamp if archived")
    tags: list[str] = Field(default_factory=list, description="Tags associated with the app")

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
    icon_emoji: Optional[str] = Field(None, alias="iconEmoji", description="Emoji for the app icon")
    icon_background: Optional[str] = Field(None, alias="iconBackground", description="Background color/gradient for the icon")

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


class PreviewVersionInfo(BaseModel):
    """Preview version info for versions response."""

    version: Optional[str] = Field(None, description="Preview version from VERSION file")
    available: bool = Field(..., description="Whether preview build exists")

    model_config = {"populate_by_name": True}


class EnvironmentVersions(BaseModel):
    """Environment version assignments."""

    dev: Optional[str] = Field(None, description="Version deployed to dev")
    staging: Optional[str] = Field(None, description="Version deployed to staging")
    prod: Optional[str] = Field(None, description="Version deployed to prod")

    model_config = {"populate_by_name": True}


class AppVersionsResponse(BaseModel):
    """Response for list_app_versions endpoint."""

    versions: list[str] = Field(..., description="List of deployed version strings, newest first")
    preview: PreviewVersionInfo = Field(..., description="Preview version info")
    environments: EnvironmentVersions = Field(..., description="Current environment version assignments")

    model_config = {"populate_by_name": True}


class PromoteVersionResponse(BaseModel):
    """Response after promoting a version."""

    success: bool = Field(..., description="Whether promotion succeeded")
    version: str = Field(..., description="Version that was promoted")
    environment: str = Field(..., description="Environment it was promoted to")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = {"populate_by_name": True}


class RegenerateIconResponse(BaseModel):
    """Response after regenerating an app icon (preview only, not saved)."""

    success: bool = Field(..., description="Whether icon generation succeeded")
    icon_emoji: Optional[str] = Field(None, alias="iconEmoji", description="Generated emoji for the app icon")
    icon_background: Optional[str] = Field(None, alias="iconBackground", description="Generated background color/gradient")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = {"populate_by_name": True}
