"""
FastAPI router for managing SAM apps - React applications built via App Agent.

This router handles:
- App CRUD operations (create, list, get, update, archive)
- Build validation and deployment
- Static file serving via AppStorageService

Note: Workspace initialization is now handled by the claude-code-sam-app container
itself when the agent first connects to the workspace. The gateway only creates
the empty workspace directory.

All file serving (preview and deployed) goes through AppStorageService, which
abstracts the storage backend (FilesystemAppStorageService for local dev,
S3AppStorageService for K8S production). This ensures identical code paths
in all environments.
"""

import json
import logging
import mimetypes
import re
import secrets
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..dependencies import get_db_optional, get_workspace_base, get_app_storage_service, get_sac_component
from ..shared.auth_utils import get_current_user
from ..services.app_icon_generator import AppIconGenerator, get_default_icon
from ..shared.pagination import PaginatedResponse, PaginationParams
from .dto.requests.app_requests import (
    CreateAppRequest,
    DeployAppRequest,
    UpdateAppRequest,
)
from .dto.responses.app_responses import (
    AppResponse,
    AppVersionResponse,
    AppVersionsResponse,
    CreateAppResponse,
    DeployAppResponse,
    EnvironmentVersions,
    PreviewVersionInfo,
    PromoteVersionResponse,
    RegenerateIconResponse,
)
from ..repository.app_repository import AppRepository
from ..repository.app_user_repository import AppUserRepository
from ..repository.app_tag_repository import AppTagRepository
from ....services.app_storage import AppStorageService

log = logging.getLogger(__name__)

router = APIRouter()
app_repository = AppRepository()



@router.post("/apps", response_model=CreateAppResponse)
async def create_app(
    request: CreateAppRequest,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Create new app with empty workspace directory.

    This endpoint:
    1. Generates unique app_id (name-based slug + random suffix)
    2. Creates database record (status='draft')
    3. Creates empty workspace directory
    4. Generates AI-powered icon (emoji + gradient) or uses default
    5. Returns app_id and workspace_path

    Note: Workspace initialization (template copying, git init) is handled by
    the claude-code-sam-app container when the agent first connects. The container
    detects the empty workspace and runs /usr/local/bin/init-workspace.sh.

    App names can be duplicated - app_id provides uniqueness.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} creating app: {request.name}")

    # Generate AI-powered icon (emoji + background gradient)
    # Falls back to default if LLM is not configured or fails
    try:
        model_config = component.get_config("model", {})
        icon_generator = AppIconGenerator(model_config)
        icon = await icon_generator.generate(
            app_name=request.name,
            description=request.description,
        )
        log.info(f"Generated icon for app {request.name}: {icon.emoji}")
    except Exception as e:
        log.warning(f"Icon generation failed, using default: {e}")
        icon = get_default_icon()

    # Generate unique app_id: slugified name + 4-char random suffix
    # This allows duplicate names while maintaining unique IDs
    base_slug = request.name.lower().replace(" ", "-").replace("_", "-")
    # Remove any non-alphanumeric characters except hyphens
    base_slug = "".join(c for c in base_slug if c.isalnum() or c == "-")
    # Generate 4-character random suffix
    random_suffix = secrets.token_hex(2)  # 2 bytes = 4 hex chars
    app_id = f"{base_slug}-{random_suffix}"

    # Create workspace path
    workspace_base = Path(workspace_base)
    workspace_path = workspace_base / user_id / "apps" / app_id

    # Extremely unlikely, but check if this exact app_id already exists
    # (only possible with random collision)
    if workspace_path.exists():
        log.warning(f"Random app_id collision detected: {app_id}, retrying...")
        # Regenerate with new suffix
        random_suffix = secrets.token_hex(2)
        app_id = f"{base_slug}-{random_suffix}"
        workspace_path = workspace_base / user_id / "apps" / app_id

    # Create empty workspace directory
    try:
        workspace_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Created workspace directory at {workspace_path}")
    except Exception as e:
        log.error(f"Failed to create workspace directory for {app_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace directory",
        ) from e

    # Insert into database
    if db:
        app = app_repository.create(
            db,
            app_id=app_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            workspace_id=app_id,
            status="draft",
            icon_emoji=icon.emoji,
            icon_background=icon.background,
        )
        log.info(f"App {app_id} saved to database")

        # Add creator as owner in app_users table
        app_user_repository = AppUserRepository(db)
        app_user_repository.add_user_to_app(
            app_id=app.id,  # Use the internal ID for FK relationship
            user_id=user_id,
            role="owner",
            added_by_user_id=user_id,
        )
        log.info(f"Added user {user_id} as owner of app {app_id}")

    log.info(f"App {app_id} created successfully at {workspace_path}")

    return CreateAppResponse(
        app_id=app_id,
        workspace_path=str(workspace_path),
        workspace_id=app_id,
        status="draft",
        icon_emoji=icon.emoji,
        icon_background=icon.background,
    )


@router.get("/apps", response_model=PaginatedResponse[AppResponse])
async def list_apps(
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """List all apps for current user with pagination."""
    user_id = user.get("id")
    log.info(f"User {user_id} listing apps (page={page_number}, size={page_size})")

    from ..shared.pagination import Meta, PaginationMeta

    if not db:
        # No database available, return empty list
        pagination_meta = PaginationMeta(
            pageNumber=page_number,
            count=0,
            pageSize=page_size,
            nextPage=None,
            totalPages=0,
        )
        return PaginatedResponse(
            data=[],
            meta=Meta(pagination=pagination_meta),
        )

    # Query database for apps
    pagination_params = PaginationParams(page_number=page_number, page_size=page_size)
    apps = app_repository.list_by_user(db, user_id, pagination_params)
    total_count = app_repository.count_by_user(db, user_id)

    # Get tags for all apps
    tag_repository = AppTagRepository(db)

    # Convert to response models
    app_responses = [
        AppResponse(
            id=app.id,
            app_id=app.app_id,
            user_id=app.user_id,
            name=app.name,
            description=app.description,
            workspace_id=app.workspace_id,
            is_public=app.is_public,
            is_owner=app.user_id == user_id,  # Compare app owner with current user
            created_by_user_id=app.user_id,  # Creator is stored in user_id
            status=app.status,
            current_version=app.current_version,
            dev_version=app.dev_version,
            staging_version=app.staging_version,
            prod_version=app.prod_version,
            icon_emoji=app.icon_emoji,
            icon_background=app.icon_background,
            created_time=app.created_time,
            updated_time=app.updated_time,
            archived_time=app.archived_time,
            tags=tag_repository.get_tags_for_app(app.id),
        )
        for app in apps
    ]

    # Calculate pagination metadata
    total_pages = (total_count + page_size - 1) // page_size
    next_page = page_number + 1 if page_number < total_pages else None

    pagination_meta = PaginationMeta(
        pageNumber=page_number,
        count=total_count,
        pageSize=page_size,
        nextPage=next_page,
        totalPages=total_pages,
    )

    return PaginatedResponse(
        data=app_responses,
        meta=Meta(pagination=pagination_meta),
    )


@router.get("/apps/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
):
    """Get app metadata and current version."""
    user_id = user.get("id")
    log.info(f"User {user_id} getting app {app_id}")

    # Try to get from database first
    if db:
        app = app_repository.get_by_id(db, app_id, user_id)
        if app:
            tag_repository = AppTagRepository(db)
            return AppResponse(
                id=app.id,
                app_id=app.app_id,
                user_id=app.user_id,
                name=app.name,
                description=app.description,
                workspace_id=app.workspace_id,
                is_public=app.is_public,
                is_owner=app.user_id == user_id,  # Compare app owner with current user
                created_by_user_id=app.user_id,  # Creator is stored in user_id
                status=app.status,
                current_version=app.current_version,
                dev_version=app.dev_version,
                staging_version=app.staging_version,
                prod_version=app.prod_version,
                icon_emoji=app.icon_emoji,
                icon_background=app.icon_background,
                created_time=app.created_time,
                updated_time=app.updated_time,
                archived_time=app.archived_time,
                tags=tag_repository.get_tags_for_app(app.id),
            )

    # Fallback to filesystem (for backwards compatibility)
    workspace_base = Path(workspace_base)
    workspace_path = workspace_base / user_id / "apps" / app_id

    if not workspace_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    # Read package.json for app metadata
    package_json_path = workspace_path / "package.json"
    try:
        with open(package_json_path) as f:
            package_json = json.load(f)
    except Exception as e:
        log.error(f"Failed to read package.json for {app_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read app metadata",
        )

    # Get workspace creation time
    created_time = int(workspace_path.stat().st_ctime * 1000)
    updated_time = int(workspace_path.stat().st_mtime * 1000)

    # Return app metadata (filesystem-based, no database)
    return AppResponse(
        id=app_id,
        app_id=app_id,
        user_id=user_id,
        name=package_json.get("description", app_id).replace("SAM App: ", ""),
        description=package_json.get("description"),
        workspace_id=app_id,
        is_public=False,  # Default to private for filesystem-based apps
        is_owner=True,  # Filesystem apps are always owned by current user
        created_by_user_id=user_id,  # Current user is creator for filesystem apps
        status="draft",  # Always draft until database tracks deployment
        current_version=0,
        dev_version=None,
        staging_version=None,
        prod_version=None,
        created_time=created_time,
        updated_time=updated_time,
        archived_time=None,
    )


@router.post("/apps/{app_id}/generate-icon", response_model=RegenerateIconResponse)
async def generate_app_icon(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Generate a new icon (emoji + background) for an app using AI.

    This endpoint returns a preview of the generated icon WITHOUT saving it.
    The icon should be saved via the PATCH /apps/{app_id} endpoint.

    This allows users to preview the generated icon before committing to it.

    Falls back to default icon if AI generation fails or is not configured.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} generating icon preview for app {app_id}")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Get app from database to get name/description for generation
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    # Generate new icon using AI (does NOT save to database)
    try:
        model_config = component.get_config("model", {})
        icon_generator = AppIconGenerator(model_config)
        icon = await icon_generator.generate(
            app_name=app.name,
            description=app.description,
            current_emoji=app.icon_emoji,
            current_background=app.icon_background,
        )
        log.info(f"Generated icon preview for app {app_id}: {icon.emoji}")
    except Exception as e:
        log.warning(f"Icon generation failed for {app_id}, using default: {e}")
        icon = get_default_icon()

    return RegenerateIconResponse(
        success=True,
        icon_emoji=icon.emoji,
        icon_background=icon.background,
    )


@router.get("/apps/{app_id}/versions", response_model=AppVersionsResponse)
async def list_app_versions(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """
    List all available versions for an app.

    Returns:
    - versions: List of deployed version strings from storage (newest first)
    - preview: Preview version info (from app storage VERSION file, workspace fallback)
    - environments: Current deployment state per environment from database
    """
    user_id = user.get("id")
    log.info(f"User {user_id} listing versions for app {app_id}")

    # Get deployed versions from storage
    versions = await app_storage.list_versions(user_id, app_id)

    # Get preview version - try app storage first (works without workspace),
    # then fall back to workspace VERSION file
    preview_version = None
    preview_available = False

    # Try to get VERSION from app storage first
    version_data = await app_storage.get_preview_version(user_id, app_id)
    if version_data:
        preview_version = version_data.get("version")
        # Check if preview dist/ exists in app storage
        preview_available = await app_storage.app_exists(user_id, app_id)
    else:
        # Fall back to workspace VERSION file
        workspace_base_path = Path(workspace_base)
        workspace_path = workspace_base_path / user_id / "apps" / app_id
        version_file = workspace_path / "VERSION"

        if version_file.exists():
            try:
                with open(version_file) as f:
                    version_data = json.load(f)
                    preview_version = version_data.get("version")
                    # Check if dist/ exists in workspace for preview
                    dist_path = workspace_path / "dist"
                    preview_available = dist_path.exists() and dist_path.is_dir()
            except Exception as e:
                log.warning(f"Failed to read VERSION file for {app_id}: {e}")

    # Get environment assignments from database
    dev_version = None
    staging_version = None
    prod_version = None

    if db:
        app = app_repository.get_by_id(db, app_id, user_id)
        if app:
            dev_version = app.dev_version
            staging_version = app.staging_version
            prod_version = app.prod_version

    return AppVersionsResponse(
        versions=versions,
        preview=PreviewVersionInfo(
            version=preview_version,
            available=preview_available,
        ),
        environments=EnvironmentVersions(
            dev=dev_version,
            staging=staging_version,
            prod=prod_version,
        ),
    )


@router.post("/apps/{app_id}/promote", response_model=PromoteVersionResponse)
async def promote_version(
    app_id: str,
    version: str = Query(..., description="Version to promote"),
    environment: str = Query(..., regex="^(dev|staging|prod)$", description="Target environment"),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """
    Promote an already-deployed version to an environment.

    Unlike deploy (which builds from workspace), this just updates
    the environment pointer to an existing version in storage.

    Use this to:
    - Promote staging version to prod
    - Rollback prod to a previous version
    - Test a specific version in dev environment
    """
    user_id = user.get("id")
    log.info(f"User {user_id} promoting version {version} to {environment} for app {app_id}")

    # Verify the version exists in storage
    if not await app_storage.version_exists(user_id, app_id, version):
        log.error(f"Version {version} not found in storage for app {app_id}")
        return PromoteVersionResponse(
            success=False,
            version=version,
            environment=environment,
            error=f"Version {version} not found in storage",
        )

    # Update database with the new environment assignment
    if not db:
        return PromoteVersionResponse(
            success=False,
            version=version,
            environment=environment,
            error="Database not available for version tracking",
        )

    try:
        # Build update kwargs based on environment
        update_kwargs = {
            f"{environment}_version": version,
        }

        # Only set status to "deployed" when promoting to prod
        # This ensures the app card click goes to a valid production version
        app = app_repository.get_by_id(db, app_id, user_id)
        if app and app.status == "draft" and environment == "prod":
            update_kwargs["status"] = "deployed"

        app_repository.update(
            db,
            app_id,
            user_id,
            **update_kwargs,
        )
        log.info(f"Promoted version {version} to {environment} for app {app_id}")

        return PromoteVersionResponse(
            success=True,
            version=version,
            environment=environment,
            error=None,
        )
    except Exception as e:
        log.error(f"Failed to promote version for app {app_id}: {e}")
        return PromoteVersionResponse(
            success=False,
            version=version,
            environment=environment,
            error=str(e),
        )


@router.patch("/apps/{app_id}", response_model=AppResponse)
async def update_app(
    app_id: str,
    request: UpdateAppRequest,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Update app metadata (name, description, visibility)."""
    user_id = user.get("id")
    log.info(f"User {user_id} updating app {app_id}")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Build update dict from provided fields
    update_fields = {}
    if request.name is not None:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.is_public is not None:
        update_fields["is_public"] = request.is_public
    if request.icon_emoji is not None:
        update_fields["icon_emoji"] = request.icon_emoji
    if request.icon_background is not None:
        update_fields["icon_background"] = request.icon_background

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    app = app_repository.update(db, app_id, user_id, **update_fields)

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    tag_repository = AppTagRepository(db)
    return AppResponse(
        id=app.id,
        app_id=app.app_id,
        user_id=app.user_id,
        name=app.name,
        description=app.description,
        workspace_id=app.workspace_id,
        is_public=app.is_public,
        is_owner=app.user_id == user_id,  # Compare app owner with current user
        created_by_user_id=app.user_id,
        status=app.status,
        current_version=app.current_version,
        dev_version=app.dev_version,
        staging_version=app.staging_version,
        prod_version=app.prod_version,
        created_time=app.created_time,
        updated_time=app.updated_time,
        archived_time=app.archived_time,
        tags=tag_repository.get_tags_for_app(app.id),
    )


@router.get("/apps/{app_id}/tags", response_model=list[str])
async def get_app_tags(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Get all tags for an app."""
    user_id = user.get("id")
    log.info(f"User {user_id} getting tags for app {app_id}")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Verify app exists and user has access
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    tag_repository = AppTagRepository(db)
    return tag_repository.get_tags_for_app(app.id)


@router.put("/apps/{app_id}/tags", response_model=list[str])
async def set_app_tags(
    app_id: str,
    tags: list[str],
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Set all tags for an app (replaces existing tags)."""
    user_id = user.get("id")
    log.info(f"User {user_id} setting tags for app {app_id}: {tags}")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Verify app exists and user has access
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    tag_repository = AppTagRepository(db)
    return tag_repository.set_tags(app.id, tags)


@router.get("/apps/tags/all", response_model=list[str])
async def get_all_tags(
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Get all unique tags across all apps (for autocomplete)."""
    user_id = user.get("id")
    log.info(f"User {user_id} getting all tags")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    tag_repository = AppTagRepository(db)
    return tag_repository.get_all_tags()


@router.post("/apps/{app_id}/deploy", response_model=DeployAppResponse)
async def deploy_app(
    app_id: str,
    environment: str = Query(default="prod", regex="^(dev|staging|prod)$"),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """
    Deploy new version of app to an environment.

    This endpoint:
    1. Reads VERSION file from workspace (created by build_and_version.sh)
    2. Validates that dist/ folder exists
    3. Deploys to AppStorageService (versioned storage)
    4. Updates database with deployed version for the environment
    5. Returns success with version number

    Args:
        environment: Target environment - "dev", "staging", or "prod" (default: "prod")

    Note: The actual build and versioning is done by Claude Code via build_and_version.sh
    during development. This endpoint just copies the already-built files to deployment.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deploying app {app_id} to {environment}")

    # Get workspace path (still needed to read VERSION and dist/)
    workspace_base_path = Path(workspace_base)
    workspace_path = workspace_base_path / user_id / "apps" / app_id

    if not workspace_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App workspace not found",
        )

    # Check if VERSION file exists
    version_file = workspace_path / "VERSION"
    if not version_file.exists():
        log.error(f"VERSION file not found for app {app_id}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=["No VERSION file found. App must be built with build_and_version.sh first."],
        )

    # Read version from VERSION file
    try:
        with open(version_file) as f:
            version_data = json.load(f)
            version_str = version_data.get("version")
            if not version_str:
                raise ValueError("VERSION file missing 'version' field")
    except Exception as e:
        log.error(f"Failed to read VERSION file for {app_id}: {e}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=[f"Failed to read VERSION file: {str(e)}"],
        )

    log.info(f"Deploying app {app_id} version {version_str} to {environment}")

    # Check if dist/ folder exists
    dist_path = workspace_path / "dist"
    if not dist_path.exists() or not dist_path.is_dir():
        log.error(f"dist/ folder not found for app {app_id}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=["dist/ folder not found. App must be built first."],
        )

    # Deploy to AppStorageService (same code path for local and K8S)
    try:
        await app_storage.deploy_version(user_id, app_id, version_str, dist_path)
        log.info(f"Deployed version {version_str} to AppStorageService")
    except Exception as e:
        log.error(f"Failed to deploy to AppStorageService for app {app_id}: {e}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=[f"Failed to deploy to storage: {str(e)}"],
        )

    # Update database with deployed version for the environment
    if db:
        try:
            # Parse version string to integer for current_version field
            version_int = int(version_str.replace(".", ""))

            # Build update kwargs based on environment
            # Only set status to "deployed" when deploying to prod
            # This ensures the app card click goes to a valid production version
            update_kwargs = {
                "current_version": version_int,
                f"{environment}_version": version_str,  # Store semver string
            }
            if environment == "prod":
                update_kwargs["status"] = "deployed"

            app_repository.update(
                db,
                app_id,
                user_id,
                **update_kwargs,
            )
            log.info(f"Updated app {app_id} {environment}_version to '{version_str}'")
        except Exception as e:
            log.error(f"Failed to update database for app {app_id}: {e}")
            # Don't fail deployment if DB update fails - files are already deployed

    log.info(f"Successfully deployed app {app_id} version {version_str} to {environment}")

    return DeployAppResponse(
        success=True,
        version=int(version_str.replace(".", "")),
        errors=None,
    )


@router.delete("/apps/{app_id}")
async def delete_app(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """
    Permanently delete an app and all associated data.

    This endpoint:
    1. Deletes the app record from database (including tags and user associations)
    2. Deletes the workspace directory from filesystem
    3. Deletes all deployed versions from app storage

    This action cannot be undone.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deleting app {app_id}")

    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Verify app exists and user owns it
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found",
        )

    # Verify the user is the owner
    if app.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the app owner can delete an app",
        )

    errors = []

    # 1. Delete workspace directory
    workspace_path = Path(workspace_base) / user_id / "apps" / app_id
    if workspace_path.exists():
        try:
            import shutil
            shutil.rmtree(workspace_path)
            log.info(f"Deleted workspace directory: {workspace_path}")
        except Exception as e:
            log.error(f"Failed to delete workspace directory for {app_id}: {e}")
            errors.append(f"Failed to delete workspace: {str(e)}")

    # 2. Delete deployed versions from app storage
    try:
        await app_storage.delete_app(user_id, app_id)
        log.info(f"Deleted app storage for {app_id}")
    except Exception as e:
        log.error(f"Failed to delete app storage for {app_id}: {e}")
        errors.append(f"Failed to delete storage: {str(e)}")

    # 3. Delete database records
    try:
        deleted = app_repository.delete(db, app_id, user_id)
        if not deleted:
            errors.append("Failed to delete database records")
        else:
            log.info(f"Deleted database records for app {app_id}")
    except Exception as e:
        log.error(f"Failed to delete database records for {app_id}: {e}")
        errors.append(f"Failed to delete database records: {str(e)}")

    # If any critical errors occurred, report them but don't fail
    # (partial cleanup is still valuable)
    if errors:
        log.warning(f"App {app_id} deleted with some errors: {errors}")

    return {"success": True, "app_id": app_id}


@router.options("/apps/preview/{app_id}/{path:path}")
@router.options("/apps/preview/{app_id}")
@router.options("/apps/deployed/{app_id}/{path:path}")
@router.options("/apps/deployed/{app_id}")
async def serve_app_options(app_id: str, path: str = ""):
    """Handle CORS preflight requests for sandboxed iframe access."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
        }
    )


@router.head("/apps/preview/{app_id}/", include_in_schema=False)
@router.head("/apps/preview/{app_id}/{path:path}", include_in_schema=True)
@router.head("/apps/preview/{app_id}", include_in_schema=False)
@router.get("/apps/preview/{app_id}/", include_in_schema=False)
@router.get("/apps/preview/{app_id}/{path:path}", include_in_schema=True)
@router.get("/apps/preview/{app_id}", include_in_schema=False)
async def serve_app(
    request: Request,
    app_id: str,
    path: str = "",
    user: dict = Depends(get_current_user),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """
    Serve built app from dist/ storage.
    User must refresh after agent makes changes (build runs automatically).

    Supports HEAD requests to check if app is built without downloading content.

    Uses AppStorageService to serve files - same code path for local and K8S.
    """
    user_id = user.get("id")

    # Serve from AppStorageService (same code path for local and K8S)
    return await _serve_from_app_storage(
        request, app_id, path, user_id, app_storage, is_preview=True
    )


async def _serve_from_app_storage(
    request: Request,
    app_id: str,
    path: str,
    user_id: str,
    app_storage: AppStorageService,
    is_preview: bool = True,
) -> Response:
    """
    Serve app files from AppStorageService (S3/GCS).

    Args:
        request: FastAPI request object
        app_id: App identifier
        path: File path within dist/
        user_id: User identifier
        app_storage: AppStorageService instance
        is_preview: True for preview (no-cache), False for deployed (cached)

    Returns:
        Response with file content
    """
    # Check if app exists in storage
    if not await app_storage.app_exists(user_id, app_id):
        raise HTTPException(
            status_code=404,
            detail="App not built yet - ask agent to make a change to trigger build"
        )

    # For HEAD requests, just return 200 if app exists
    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Resource-Policy": "cross-origin",
            }
        )

    # Default to index.html for directory requests
    if not path or path.endswith("/"):
        file_path = "index.html"
    else:
        file_path = path

    # Get file from storage
    content = await app_storage.get_file(user_id, app_id, file_path)

    if content is None:
        # Check if this is an asset file (has a file extension that indicates a static asset)
        # For these, we should NOT fall back to index.html - return 404 instead
        asset_extensions = {'.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map', '.json', '.webp'}
        file_ext = Path(file_path).suffix.lower()

        if file_ext in asset_extensions:
            # Asset file not found - return 404, don't fall back to index.html
            raise HTTPException(status_code=404, detail=f"Asset not found: {file_path}")

        # SPA fallback: serve index.html for missing routes (client-side routing)
        content = await app_storage.get_file(user_id, app_id, "index.html")
        if content is None:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = "index.html"

    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    # URL rewriting for HTML files (to fix base path)
    if content_type == "text/html":
        html_content = content.decode("utf-8")
        endpoint = "preview" if is_preview else "deployed"
        proxy_prefix = f"/api/v1/apps/{endpoint}/{app_id}"

        # Rewrite absolute URLs to include proxy prefix
        html_content = re.sub(
            r'((?:src|href)=")/(?!/)',
            rf'\1{proxy_prefix}/',
            html_content
        )

        content = html_content.encode("utf-8")

    # Set cache control based on preview vs deployed and file type
    # For preview: always no-store (never cache)
    # For deployed HTML: no-store (so new deployments are always picked up)
    # For deployed assets: long cache (hashes change when content changes)
    if is_preview:
        cache_control = "no-store, must-revalidate"
    elif file_path == "index.html":
        # HTML must never be cached - new versions reference different JS/CSS hashes
        cache_control = "no-store, must-revalidate"
    else:
        # JS/CSS/images with hashes can be cached indefinitely
        cache_control = "public, max-age=31536000, immutable"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": cache_control,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
        }
    )


async def _serve_from_versioned_storage(
    request: Request,
    app_id: str,
    path: str,
    user_id: str,
    app_storage: AppStorageService,
    environment: str,
    deployed_version: Optional[str],
) -> Response:
    """
    Serve app files from versioned AppStorageService storage.

    Args:
        request: FastAPI request object
        app_id: App identifier
        path: File path within the version
        user_id: User identifier
        app_storage: AppStorageService instance
        environment: Target environment (dev, staging, prod)
        deployed_version: Version string from database (e.g., "1.2.3")

    Returns:
        Response with file content
    """
    # Check if we have a deployed version
    if not deployed_version:
        raise HTTPException(
            status_code=404,
            detail=f"App not deployed to {environment} yet - click Deploy button to deploy the app"
        )

    # Check if version exists in storage
    if not await app_storage.version_exists(user_id, app_id, deployed_version):
        raise HTTPException(
            status_code=404,
            detail=f"Version {deployed_version} not found in storage"
        )

    # For HEAD requests, just return 200 if version exists
    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cross-Origin-Resource-Policy": "cross-origin",
            }
        )

    # Default to index.html for directory requests
    if not path or path.endswith("/"):
        file_path = "index.html"
    else:
        file_path = path

    # Get file from versioned storage
    content = await app_storage.get_version_file(user_id, app_id, deployed_version, file_path)

    if content is None:
        # Check if this is an asset file (has a file extension that indicates a static asset)
        # For these, we should NOT fall back to index.html - return 404 instead
        asset_extensions = {'.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.map', '.json', '.webp'}
        file_ext = Path(file_path).suffix.lower()

        if file_ext in asset_extensions:
            # Asset file not found - return 404, don't fall back to index.html
            raise HTTPException(status_code=404, detail=f"Asset not found: {file_path}")

        # SPA fallback: serve index.html for missing routes (client-side routing)
        content = await app_storage.get_version_file(user_id, app_id, deployed_version, "index.html")
        if content is None:
            raise HTTPException(status_code=404, detail="File not found")
        file_path = "index.html"

    # Determine content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    # URL rewriting for HTML files (to fix base path)
    if content_type == "text/html":
        html_content = content.decode("utf-8")
        # Use environment-in-path URL format to avoid query param stripping with module scripts
        # This ensures all sub-resources (JS, CSS, etc.) are served from the correct version
        proxy_prefix = f"/api/v1/apps/deployed/{app_id}/env/{environment}"

        # Rewrite absolute URLs to include proxy prefix with environment
        # For src/href attributes pointing to root-relative paths
        html_content = re.sub(
            r'((?:src|href)=")/(?!/)',
            rf'\1{proxy_prefix}/',
            html_content
        )

        content = html_content.encode("utf-8")

    # Smart caching: no-store for HTML (never cache), long cache for hashed assets
    if file_path == "index.html":
        # HTML must never be cached - new versions reference different JS/CSS hashes
        cache_control = "no-store, must-revalidate"
    else:
        # JS/CSS/images with hashes can be cached indefinitely
        cache_control = "public, max-age=31536000, immutable"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": cache_control,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
        }
    )


# Environment-in-path routes (preferred - avoids query param stripping issues with module scripts)
@router.head("/apps/deployed/{app_id}/env/{environment}/", include_in_schema=False)
@router.head("/apps/deployed/{app_id}/env/{environment}/{path:path}", include_in_schema=True)
@router.get("/apps/deployed/{app_id}/env/{environment}/", include_in_schema=False)
@router.get("/apps/deployed/{app_id}/env/{environment}/{path:path}", include_in_schema=True)
async def serve_deployed_app_with_env_path(
    request: Request,
    app_id: str,
    environment: str,
    path: str = "",
    version: Optional[str] = Query(default=None, description="Override version to serve (for testing)"),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """Serve deployed app with environment in path."""
    if environment not in ("dev", "staging", "prod"):
        raise HTTPException(status_code=400, detail="Invalid environment")
    return await _serve_deployed_app_impl(
        request, app_id, path, environment, version, user, db, app_storage
    )


# Legacy query-param routes (kept for backwards compatibility)
@router.head("/apps/deployed/{app_id}/", include_in_schema=False)
@router.head("/apps/deployed/{app_id}/{path:path}", include_in_schema=True)
@router.head("/apps/deployed/{app_id}", include_in_schema=False)
@router.get("/apps/deployed/{app_id}/", include_in_schema=False)
@router.get("/apps/deployed/{app_id}/{path:path}", include_in_schema=True)
@router.get("/apps/deployed/{app_id}", include_in_schema=False)
async def serve_deployed_app(
    request: Request,
    app_id: str,
    path: str = "",
    environment: str = Query(default="prod", regex="^(dev|staging|prod)$"),
    version: Optional[str] = Query(default=None, description="Override version to serve (for testing)"),
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    app_storage: AppStorageService = Depends(get_app_storage_service),
):
    """Serve deployed app with environment as query param (legacy)."""
    return await _serve_deployed_app_impl(
        request, app_id, path, environment, version, user, db, app_storage
    )


async def _serve_deployed_app_impl(
    request: Request,
    app_id: str,
    path: str,
    environment: str,
    version: Optional[str],
    user: dict,
    db: Optional[Session],
    app_storage: AppStorageService,
):
    """
    Serve deployed app from versioned storage.

    This endpoint serves a deployed version of the app based on the environment.
    The version is looked up from the database ({environment}_version column),
    unless a specific version is provided via query param for testing.

    Args:
        environment: Target environment - "dev", "staging", or "prod" (default: "prod")
        version: Optional version override to test a specific version

    Uses AppStorageService.get_version_file() to serve from versioned storage.
    Same code path for local development and K8S production.
    """
    current_user_id = user.get("id")

    # Look up the app to get owner_user_id and deployed version
    # We need to use the app owner's user_id for storage lookup, not the current user
    deployed_version = version  # Use explicit version if provided
    owner_user_id = current_user_id  # Default to current user

    if db:
        # First try to find the app owned by current user
        app = app_repository.get_by_id(db, app_id, current_user_id)
        if app:
            owner_user_id = app.user_id
            if not deployed_version:
                deployed_version = getattr(app, f"{environment}_version", None)
        else:
            # App not owned by current user - could be a public app
            # Try to find it without user restriction
            from sqlalchemy import select
            from ..repository.models.app_model import AppModel
            stmt = select(AppModel).where(AppModel.app_id == app_id)
            app = db.execute(stmt).scalar_one_or_none()
            if app:
                owner_user_id = app.user_id
                if not deployed_version:
                    deployed_version = getattr(app, f"{environment}_version", None)

    # Serve from AppStorageService using the app owner's user_id
    return await _serve_from_versioned_storage(
        request, app_id, path, owner_user_id, app_storage, environment, deployed_version
    )
