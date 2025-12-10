"""
FastAPI router for managing SAM apps - React applications built via App Agent.

This router handles:
- App CRUD operations (create, list, get, update, archive)
- Build validation and deployment
- Static file serving from built dist/ folder

Note: Workspace initialization is now handled by the claude-code-sam-app container
itself when the agent first connects to the workspace. The gateway only creates
the empty workspace directory.
"""

import json
import logging
import secrets
from pathlib import Path
from typing import Optional

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

from ..dependencies import get_db_optional, get_workspace_base
from ..shared.auth_utils import get_current_user
from ..shared.pagination import PaginatedResponse, PaginationParams
from .dto.requests.app_requests import (
    CreateAppRequest,
    DeployAppRequest,
    UpdateAppRequest,
)
from .dto.responses.app_responses import (
    AppResponse,
    AppVersionResponse,
    CreateAppResponse,
    DeployAppResponse,
)
from ..repository.app_repository import AppRepository

log = logging.getLogger(__name__)

router = APIRouter()
app_repository = AppRepository()



@router.post("/apps", response_model=CreateAppResponse)
async def create_app(
    request: CreateAppRequest,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
):
    """
    Create new app with empty workspace directory.

    This endpoint:
    1. Generates unique app_id (name-based slug + random suffix)
    2. Creates database record (status='draft')
    3. Creates empty workspace directory
    4. Returns app_id and workspace_path

    Note: Workspace initialization (template copying, git init) is handled by
    the claude-code-sam-app container when the agent first connects. The container
    detects the empty workspace and runs /usr/local/bin/init-workspace.sh.

    App names can be duplicated - app_id provides uniqueness.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} creating app: {request.name}")

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
        app_repository.create(
            db,
            app_id=app_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            workspace_id=app_id,
            status="draft",
        )
        log.info(f"App {app_id} saved to database")

    log.info(f"App {app_id} created successfully at {workspace_path}")

    return CreateAppResponse(
        app_id=app_id,
        workspace_path=str(workspace_path),
        workspace_id=app_id,
        status="draft",
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

    # Convert to response models
    app_responses = [
        AppResponse(
            id=app.id,
            app_id=app.app_id,
            user_id=app.user_id,
            name=app.name,
            description=app.description,
            workspace_id=app.workspace_id,
            status=app.status,
            current_version=app.current_version,
            created_time=app.created_time,
            updated_time=app.updated_time,
            archived_time=app.archived_time,
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
            return AppResponse(
                id=app.id,
                app_id=app.app_id,
                user_id=app.user_id,
                name=app.name,
                description=app.description,
                workspace_id=app.workspace_id,
                status=app.status,
                current_version=app.current_version,
                created_time=app.created_time,
                updated_time=app.updated_time,
                archived_time=app.archived_time,
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
        status="draft",  # Always draft until database tracks deployment
        current_version=0,
        created_time=created_time,
        updated_time=updated_time,
        archived_time=None,
    )


@router.patch("/apps/{app_id}", response_model=AppResponse)
async def update_app(
    app_id: str,
    request: UpdateAppRequest,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Update app metadata (name, description)."""
    user_id = user.get("id")
    log.info(f"User {user_id} updating app {app_id}")

    # TODO: Implement database update when models are ready
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="App update not yet implemented - database models needed",
    )


@router.post("/apps/{app_id}/deploy", response_model=DeployAppResponse)
async def deploy_app(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
    workspace_base: str = Depends(get_workspace_base),
):
    """
    Deploy new version of app.

    This endpoint:
    1. Reads VERSION file from workspace (created by build_and_version.sh)
    2. Validates that dist/ folder exists
    3. Creates deployments/{version}/ directory
    4. Copies dist/ contents to deployments/{version}/
    5. Updates/creates 'prod' symlink to point to new version
    6. Updates database status to 'deployed'
    7. Returns success with version number

    Note: The actual build and versioning is done by Claude Code via build_and_version.sh
    during development. This endpoint just copies the already-built files to deployment.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deploying app {app_id}")

    # Get workspace path
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

    log.info(f"Deploying app {app_id} version {version_str}")

    # Check if dist/ folder exists
    dist_path = workspace_path / "dist"
    if not dist_path.exists() or not dist_path.is_dir():
        log.error(f"dist/ folder not found for app {app_id}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=["dist/ folder not found. App must be built first."],
        )

    # Create deployments directory structure
    deployments_path = workspace_path / "deployments"
    deployments_path.mkdir(exist_ok=True)

    # Create version-specific deployment directory
    version_deployment_path = deployments_path / version_str
    if version_deployment_path.exists():
        log.warning(f"Deployment directory for version {version_str} already exists, will overwrite")
        import shutil
        shutil.rmtree(version_deployment_path)

    # Copy dist/ to deployments/{version}/
    try:
        import shutil
        shutil.copytree(dist_path, version_deployment_path)
        log.info(f"Copied dist/ to {version_deployment_path}")
    except Exception as e:
        log.error(f"Failed to copy dist/ for app {app_id}: {e}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=[f"Failed to copy build files: {str(e)}"],
        )

    # Update/create 'prod' symlink
    prod_link = deployments_path / "prod"
    if prod_link.exists() or prod_link.is_symlink():
        prod_link.unlink()

    try:
        prod_link.symlink_to(version_str, target_is_directory=True)
        log.info(f"Updated prod symlink to point to {version_str}")
    except Exception as e:
        log.error(f"Failed to create prod symlink for app {app_id}: {e}")
        return DeployAppResponse(
            success=False,
            version=0,
            errors=[f"Failed to create prod symlink: {str(e)}"],
        )

    # Update database status to 'deployed' and set current_version
    if db:
        try:
            # Parse version string to integer for current_version field
            # For semver "1.2.3", we'll convert to integer 123 for storage
            version_int = int(version_str.replace(".", ""))

            # Update app status and version
            app_repository.update(
                db,
                app_id,
                user_id,
                status="deployed",
                current_version=version_int,
            )
            log.info(f"Updated app {app_id} status to 'deployed', version {version_int}")
        except Exception as e:
            log.error(f"Failed to update database for app {app_id}: {e}")
            # Don't fail deployment if DB update fails - files are already deployed
            # Just log the error

    log.info(f"Successfully deployed app {app_id} version {version_str}")

    return DeployAppResponse(
        success=True,
        version=int(version_str.replace(".", "")),  # Convert "1.2.3" to 123 for response
        errors=None,
    )


@router.delete("/apps/{app_id}")
async def archive_app(
    app_id: str,
    user: dict = Depends(get_current_user),
    db: Optional[Session] = Depends(get_db_optional),
):
    """Soft delete app (mark as archived)."""
    user_id = user.get("id")
    log.info(f"User {user_id} archiving app {app_id}")

    # TODO: Update database when models are ready
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="App archival not yet implemented - database models needed",
    )


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
    workspace_base: str = Depends(get_workspace_base),
):
    """
    Serve built app from dist/ folder.
    User must refresh after agent makes changes (build runs automatically).

    Supports HEAD requests to check if app is built without downloading content.
    """
    user_id = user.get("id")

    # Verify user owns app
    workspace_base = Path(workspace_base)
    workspace_path = workspace_base / user_id / "apps" / app_id

    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="App not found")

    # Serve from dist/ folder
    dist_path = workspace_path / "dist"

    if not dist_path.exists():
        raise HTTPException(
            status_code=404,
            detail="App not built yet - ask agent to make a change to trigger build"
        )

    # For HEAD requests, just return 200 if dist exists
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
        file_path = dist_path / "index.html"
    else:
        file_path = dist_path / path

    # Security: Prevent directory traversal
    try:
        file_path = file_path.resolve()
        if not file_path.is_relative_to(dist_path):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=403, detail="Invalid path")

    if not file_path.exists():
        # SPA fallback: serve index.html for missing routes
        file_path = dist_path / "index.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

    # Read file
    try:
        content = file_path.read_bytes()
    except OSError as e:
        log.error(f"Failed to read file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")

    # Determine content type
    import mimetypes
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        content_type = "application/octet-stream"

    # URL rewriting for HTML files (to fix base path)
    if content_type == "text/html":
        html_content = content.decode("utf-8")
        proxy_prefix = f"/api/v1/apps/preview/{app_id}"

        # Rewrite absolute URLs to include proxy prefix
        import re
        html_content = re.sub(
            r'((?:src|href)=")/(?!/)',
            rf'\1{proxy_prefix}/',
            html_content
        )

        content = html_content.encode("utf-8")

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "no-cache",  # Force refresh to see updates
            "Access-Control-Allow-Origin": "*",  # Allow sandboxed iframe access
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",  # Allow cross-origin resource loading
        }
    )


@router.get("/apps/deployed/{app_id}/{path:path}", include_in_schema=True)
@router.get("/apps/deployed/{app_id}", include_in_schema=False)
async def serve_deployed_app(
    request: Request,
    app_id: str,
    path: str = "",
    user: dict = Depends(get_current_user),
    workspace_base: str = Depends(get_workspace_base),
):
    """
    Serve deployed app from deployments/prod/ folder.

    This endpoint serves the production-deployed version of the app,
    which is created when the user clicks the Deploy button.
    The 'prod' symlink points to the latest deployed version.
    """
    user_id = user.get("id")

    # Verify user owns app
    workspace_base_path = Path(workspace_base)
    workspace_path = workspace_base_path / user_id / "apps" / app_id

    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="App not found")

    # Serve from deployments/prod/ folder
    prod_path = workspace_path / "deployments" / "prod"

    if not prod_path.exists():
        raise HTTPException(
            status_code=404,
            detail="App not deployed yet - click Deploy button to deploy the app"
        )

    # Default to index.html for directory requests
    if not path or path.endswith("/"):
        file_path = prod_path / "index.html"
    else:
        file_path = prod_path / path

    # Security: Prevent directory traversal
    try:
        file_path = file_path.resolve()
        # Resolve prod symlink and check it's under workspace
        if not file_path.is_relative_to(workspace_path):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=403, detail="Invalid path")

    if not file_path.exists():
        # SPA fallback: serve index.html for missing routes
        file_path = prod_path / "index.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

    # Read file
    try:
        content = file_path.read_bytes()
    except OSError as e:
        log.error(f"Failed to read file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")

    # Determine content type
    import mimetypes
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        content_type = "application/octet-stream"

    # URL rewriting for HTML files (to fix base path)
    if content_type == "text/html":
        html_content = content.decode("utf-8")
        proxy_prefix = f"/api/v1/apps/deployed/{app_id}"

        # Rewrite absolute URLs to include proxy prefix
        import re
        html_content = re.sub(
            r'((?:src|href)=")/(?!/)',
            rf'\1{proxy_prefix}/',
            html_content
        )

        content = html_content.encode("utf-8")

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache deployed version
            "Access-Control-Allow-Origin": "*",  # Allow sandboxed iframe access
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",  # Allow cross-origin resource loading
        }
    )
