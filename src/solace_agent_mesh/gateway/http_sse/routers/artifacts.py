"""
FastAPI router for managing session-specific artifacts via REST endpoints.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
    Request as FastAPIRequest,
)
from pydantic import BaseModel, Field
from fastapi.responses import Response, StreamingResponse

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


import io
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlparse

from ....common.a2a.types import ArtifactInfo
from ....common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_recursively_in_string,
)
from ....common.utils.embeds.types import ResolutionMode
from ....common.utils.mime_helpers import is_text_based_mime_type
from ....common.utils.templates import resolve_template_blocks_in_string
from ..dependencies import (
    get_project_service_optional,
    ValidatedUserConfig,
    get_sac_component,
    get_session_validator,
    get_shared_artifact_service,
    get_user_id,
    get_session_manager,
    get_session_business_service_optional,
    get_db_optional,
)
from ..services.project_service import ProjectService


from ..session_manager import SessionManager
from ..services.session_service import SessionService
from sqlalchemy.orm import Session

from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
    process_artifact_upload,
)

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

log = logging.getLogger(__name__)

LOAD_FILE_CHUNK_SIZE = 1024 * 1024  # 1MB chunks

class ArtifactUploadResponse(BaseModel):
    """Response model for artifact upload with camelCase fields."""

    uri: str
    session_id: str = Field(..., alias="sessionId")
    filename: str
    size: int
    mime_type: str = Field(..., alias="mimeType")
    metadata: dict[str, Any]
    created_at: str = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


router = APIRouter()


def _resolve_storage_context(
    session_id: str,
    project_id: str | None,
    user_id: str,
    validate_session: Callable[[str, str], bool],
    project_service: ProjectService | None,
    log_prefix: str
) -> tuple[str, str, str]:
    """
    Resolve storage context from session or project parameters.

    Returns:
        tuple: (storage_user_id, storage_session_id, context_type)

    Raises:
        HTTPException: If no valid context found
    """
    # Priority 1: Session context
    if session_id and session_id.strip() and session_id not in ["null", "undefined"]:
        if not validate_session(session_id, user_id):
            log.warning("%s Session validation failed", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied.",
            )
        return user_id, session_id, "session"

    # Priority 2: Project context (only if persistence is enabled)
    elif project_id and project_id.strip() and project_id not in ["null", "undefined"]:
        if project_service is None:
            log.warning("%s Project context requested but persistence not enabled", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Project context requires database configuration.",
            )

        from ....gateway.http_sse.dependencies import SessionLocal

        if SessionLocal is None:
            log.warning("%s Project context requested but database not configured", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Project context requires database configuration.",
            )

        db = SessionLocal()
        try:
            project = project_service.get_project(db, project_id, user_id)
            if not project:
                log.warning("%s Project not found or access denied", log_prefix)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found or access denied.",
                )
            return project.user_id, f"project-{project_id}", "project"
        except HTTPException:
            raise
        except Exception as e:
            log.error("%s Error resolving project context: %s", log_prefix, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resolve project context"
            )
        finally:
            db.close()

    # No valid context
    log.warning("%s No valid context found", log_prefix)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No valid context provided.",
    )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=ArtifactUploadResponse,
    summary="Upload Artifact (Body-Based Session Management)",
    description="Uploads file with sessionId and filename in request body. Creates session if sessionId is null/empty.",
)
async def upload_artifact_with_session(
    request: FastAPIRequest,
    upload_file: UploadFile = File(..., description="The file content to upload"),
    sessionId: str | None = Form(
        None,
        description="Session ID (null/empty to create new session)",
        alias="sessionId",
    ),
    filename: str = Form(..., description="The name of the artifact to create/update"),
    metadata_json: str | None = Form(
        None, description="JSON string of artifact metadata (e.g., description, source)"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:create"])),
    session_manager: SessionManager = Depends(get_session_manager),
    session_service: SessionService | None = Depends(
        get_session_business_service_optional
    ),
    db: Session | None = Depends(get_db_optional),
):
    """
    Uploads a file to create a new version of the specified artifact.

    Key features:
    - Session ID and filename provided in request body (not URL)
    - Automatically creates new session if session_id is null/empty
    - Consistent with chat API patterns
    """
    log_prefix = f"[POST /artifacts/upload] User {user_id}: "

    # Handle session creation logic (matching chat API pattern)
    effective_session_id = None
    is_new_session = False  # Track if we created a new session

    # Use session ID from request body (matching sessionId pattern in session APIs)
    if sessionId and sessionId.strip():
        effective_session_id = sessionId.strip()
        log.info("%sUsing existing session: %s", log_prefix, effective_session_id)
    else:
        # Create new session when no sessionId provided (like chat does for new conversations)
        effective_session_id = session_manager.create_new_session_id(request)
        is_new_session = True  # Mark that we created this session
        log.info(
            "%sCreated new session for file upload: %s",
            log_prefix,
            effective_session_id,
        )

        # Persist session in database if persistence is available (matching chat pattern)
        if session_service and db:
            try:
                session_service.create_session(
                    db=db,
                    user_id=user_id,
                    session_id=effective_session_id,
                    agent_id=None,  # Will be determined when first message is sent
                    name=None,  # Will be set when first message is sent
                )
                db.commit()
                log.info(
                    "%sSession created and committed to database: %s",
                    log_prefix,
                    effective_session_id,
                )
            except Exception as session_error:
                db.rollback()
                log.warning(
                    "%sSession persistence failed, continuing with in-memory session: %s",
                    log_prefix,
                    session_error,
                )
        else:
            log.debug(
                "%sNo persistence available - using in-memory session: %s",
                log_prefix,
                effective_session_id,
            )

    # Validate inputs
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    if not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload is required.",
        )

    # Validate artifact service availability
    if not artifact_service:
        log.error("%sArtifact service is not configured.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    # Validate session (now that we have an effective_session_id)
    # Skip validation if we just created the session to avoid race conditions
    if not is_new_session and not validate_session(effective_session_id, user_id):
        log.warning(
            "%sSession validation failed for session: %s",
            log_prefix,
            effective_session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid session or insufficient permissions.",
        )

    log.info(
        "%sUploading file '%s' to session '%s'",
        log_prefix,
        filename.strip(),
        effective_session_id,
    )

    try:
        # ===== VALIDATE FILE SIZE BEFORE READING =====
        max_upload_size = component.get_config("gateway_max_upload_size_bytes")
        
        # Check Content-Length header first (if available)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                file_size = int(content_length)
                
                if file_size > max_upload_size:
                    error_msg = (
                        f"File upload rejected: size {file_size:,} bytes "
                        f"exceeds maximum {max_upload_size:,} bytes "
                        f"({file_size / (1024*1024):.2f} MB > {max_upload_size / (1024*1024):.2f} MB)"
                    )
                    log.warning("%s %s", log_prefix, error_msg)
                    
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=error_msg  # Use string instead of dict
                    )
            except ValueError:
                log.warning("%s Invalid Content-Length header: %s", log_prefix, content_length)
        
        # Read file content in chunks with size validation
        chunk_size = LOAD_FILE_CHUNK_SIZE
        content_bytes = bytearray()
        total_bytes_read = 0
        
        try:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break  # End of file
                
                chunk_len = len(chunk)
                total_bytes_read += chunk_len
                
                # Validate size during reading (fail fast)
                if total_bytes_read > max_upload_size:
                    error_msg = (
                        f"File '{upload_file.filename}' rejected: size exceeds maximum {max_upload_size:,} bytes "
                        f"(read {total_bytes_read:,} bytes so far, "
                        f"{total_bytes_read / (1024*1024):.2f} MB > {max_upload_size / (1024*1024):.2f} MB)"
                    )
                    log.warning("%s %s", log_prefix, error_msg)
                    
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=error_msg
                    )
                
                content_bytes.extend(chunk)
            
            # Convert to bytes for consistency with existing code
            content_bytes = bytes(content_bytes)
            
            log.debug(
                "%s File read successfully in chunks: %d bytes total",
                log_prefix,
                total_bytes_read
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions (size limit exceeded)
            raise
        except Exception as read_error:
            log.exception("%s Error reading uploaded file: %s", log_prefix, read_error)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read uploaded file"
            )

        mime_type = upload_file.content_type or "application/octet-stream"
        filename_clean = filename.strip()

        log.debug(
            "%sProcessing file: %s (%d bytes, %s)",
            log_prefix,
            filename_clean,
            len(content_bytes),
            mime_type,
        )

        # Use the common upload helper
        upload_result = await process_artifact_upload(
            artifact_service=artifact_service,
            component=component,
            user_id=user_id,
            session_id=effective_session_id,
            filename=filename_clean,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_json=metadata_json,
            log_prefix=log_prefix,
        )

        if upload_result["status"] != "success":
            error_msg = upload_result.get("message", "Failed to upload artifact")
            error_type = upload_result.get("error", "unknown")

            if error_type in ["invalid_filename", "empty_file"]:
                status_code = status.HTTP_400_BAD_REQUEST
            elif error_type == "file_too_large":
                status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            log.error("%s%s", log_prefix, error_msg)
            raise HTTPException(status_code=status_code, detail=error_msg)

        artifact_uri = upload_result["artifact_uri"]
        saved_version = upload_result["version"]

        log.info(
            "%sArtifact stored successfully: %s (%d bytes), version: %s",
            log_prefix,
            artifact_uri,
            len(content_bytes),
            saved_version,
        )

        # Get metadata from upload result (it was already parsed and validated)
        metadata_dict = {}
        if metadata_json and metadata_json.strip():
            try:
                metadata_dict = json.loads(metadata_json.strip())
                if not isinstance(metadata_dict, dict):
                    metadata_dict = {}
            except json.JSONDecodeError:
                metadata_dict = {}

        # Return standardized response using Pydantic model (ensures camelCase conversion)
        return ArtifactUploadResponse(
            uri=artifact_uri,
            session_id=effective_session_id,  # Will be returned as "sessionId" due to alias
            filename=filename_clean,
            size=len(content_bytes),
            mime_type=mime_type,  # Will be returned as "mimeType" due to alias
            metadata=metadata_dict,
            created_at=datetime.now(
                timezone.utc
            ).isoformat(),  # Will be returned as "createdAt" due to alias
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        log.exception("%sUnexpected error storing artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store artifact due to an internal error.",
        )
    finally:
        # Ensure file is properly closed
        try:
            await upload_file.close()
        except Exception as close_error:
            log.warning("%sError closing upload file: %s", log_prefix, close_error)


@router.get(
    "/{session_id}/{filename}/versions",
    response_model=list[int],
    summary="List Artifact Versions",
    description="Retrieves a list of available version numbers for a specific artifact.",
)
async def list_artifact_versions(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists the available integer versions for a given artifact filename
    associated with the specified context (session or project).
    """

    log_prefix = f"[ArtifactRouter:ListVersions:{filename}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context
    storage_user_id, storage_session_id, context_type = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service not available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    if not hasattr(artifact_service, "list_versions"):
        log.warning(
            "%s Configured artifact service (%s) does not support listing versions.",
            log_prefix,
            type(artifact_service).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Version listing not supported by the configured '{type(artifact_service).__name__}' artifact service.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
        )
        log.info("%s Found versions: %s", log_prefix, versions)
        return versions
    except FileNotFoundError:
        log.warning("%s Artifact not found.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        )
    except Exception as e:
        log.exception("%s Error listing artifact versions: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list artifact versions: {str(e)}",
        )


@router.get(
    "/{session_id}",
    response_model=list[ArtifactInfo],
    summary="List Artifact Information",
    description="Retrieves detailed information for artifacts available for the specified user session.",
)
@router.get(
    "/",
    response_model=list[ArtifactInfo],
    summary="List Artifact Information",
    description="Retrieves detailed information for artifacts available for the current user session.",
)
async def list_artifacts(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to list artifacts for (or 'null' for project context)"
    ),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists detailed information (filename, size, type, modified date, uri)
    for all artifacts associated with the specified context (session or project).
    """

    log_prefix = f"[ArtifactRouter:ListInfo] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context (projects vs sessions). This allows for project artiacts
    # to be listed before a session is created.
    try:
        storage_user_id, storage_session_id, context_type = _resolve_storage_context(
            session_id, project_id, user_id, validate_session, project_service, log_prefix
        )
    except HTTPException:
        log.info("%s No valid context found, returning empty list", log_prefix)
        return []

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        artifact_info_list = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
        )

        log.info("%s Returning %d artifact details.", log_prefix, len(artifact_info_list))
        return artifact_info_list

    except Exception as e:
        log.exception("%s Error retrieving artifact details: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve artifact details: {str(e)}",
        )


@router.get(
    "/{session_id}/{filename}",
    summary="Get Latest Artifact Content",
    description="Retrieves the content of the latest version of a specific artifact.",
)
async def get_latest_artifact(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of the latest version of the specified artifact
    associated with the specified context (session or project).
    """
    log_prefix = (
        f"[ArtifactRouter:GetLatest:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    # Resolve storage context
    storage_user_id, storage_session_id, context_type = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
        )

        if artifact_part is None or artifact_part.inline_data is None:
            log.warning("%s Artifact not found or has no data.", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact '{filename}' not found or is empty.",
            )

        data_bytes = artifact_part.inline_data.data
        mime_type = artifact_part.inline_data.mime_type or "application/octet-stream"
        log.info(
            "%s Artifact loaded successfully (%d bytes, %s).",
            log_prefix,
            len(data_bytes),
            mime_type,
        )

        if is_text_based_mime_type(mime_type) and component.enable_embed_resolution:
            log.info(
                "%s Artifact is text-based. Attempting recursive embed resolution.",
                log_prefix,
            )
            try:
                original_content_string = data_bytes.decode("utf-8")

                context_for_resolver = {
                    "artifact_service": artifact_service,
                    "session_context": {
                        "app_name": component.gateway_id,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                }
                config_for_resolver = {
                    "gateway_max_artifact_resolve_size_bytes": component.gateway_max_artifact_resolve_size_bytes,
                    "gateway_recursive_embed_depth": component.gateway_recursive_embed_depth,
                }

                resolved_content_string = await resolve_embeds_recursively_in_string(
                    text=original_content_string,
                    context=context_for_resolver,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES,
                    resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                # Also resolve any template blocks in the artifact
                resolved_content_string = await resolve_template_blocks_in_string(
                    text=resolved_content_string,
                    artifact_service=artifact_service,
                    session_context=context_for_resolver["session_context"],
                    log_identifier=f"{log_prefix}[TemplateResolve]",
                )
                log.info(
                    "%s Template block resolution complete. Final size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                data_bytes = resolved_content_string.encode("utf-8")
            except UnicodeDecodeError as ude:
                log.warning(
                    "%s Failed to decode artifact for recursive resolution: %s. Serving original content.",
                    log_prefix,
                    ude,
                )
            except Exception as resolve_err:
                log.exception(
                    "%s Error during recursive embed resolution: %s. Serving original content.",
                    log_prefix,
                    resolve_err,
                )
        else:
            log.info(
                "%s Artifact is not text-based or embed resolution is disabled. Serving original content.",
                log_prefix,
            )

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except FileNotFoundError:
        log.warning("%s Artifact not found by service.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found.",
        )
    except Exception as e:
        log.exception("%s Error loading artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load artifact: {str(e)}",
        )


@router.get(
    "/{session_id}/{filename}/versions/{version}",
    summary="Get Specific Artifact Version Content",
    description="Retrieves the content of a specific version of an artifact.",
)
async def get_specific_artifact_version(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to get artifacts from (or 'null' for project context)"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    version: int | str = Path(
        ...,
        title="Version",
        description="The specific version number to retrieve, or 'latest'",
    ),
    project_id: Optional[str] = Query(None, description="Project ID for project context"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of a specific version of the specified artifact
    associated with the specified context (session or project).
    """
    log_prefix = f"[ArtifactRouter:GetVersion:{filename} v{version}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Resolve storage context
    storage_user_id, storage_session_id, context_type = _resolve_storage_context(
        session_id, project_id, user_id, validate_session, project_service, log_prefix
    )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        log.info("%s Using %s context: storage_user_id=%s, storage_session_id=%s", 
                log_prefix, context_type, storage_user_id, storage_session_id)

        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
            filename=filename,
            version=version,
            load_metadata_only=False,
            return_raw_bytes=True,
            log_identifier_prefix="[ArtifactRouter:GetVersion]",
        )

        if load_result.get("status") != "success":
            error_message = load_result.get(
                "message", f"Failed to load artifact '{filename}' version '{version}'."
            )
            log.warning("%s %s", log_prefix, error_message)
            if (
                "not found" in error_message.lower()
                or "no versions available" in error_message.lower()
            ):
                status_code = status.HTTP_404_NOT_FOUND
            elif "invalid version" in error_message.lower():
                status_code = status.HTTP_400_BAD_REQUEST
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(status_code=status_code, detail=error_message)

        data_bytes = load_result.get("raw_bytes")
        mime_type = load_result.get("mime_type", "application/octet-stream")
        resolved_version_from_helper = load_result.get("version")
        if data_bytes is None:
            log.error(
                "%s Helper (with return_raw_bytes=True) returned success but no raw_bytes for '%s' v%s (resolved to %s).",
                log_prefix,
                filename,
                version,
                resolved_version_from_helper,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error retrieving artifact content.",
            )

        log.info(
            "%s Artifact '%s' version %s (resolved to %s) loaded successfully (%d bytes, %s). Streaming content.",
            log_prefix,
            filename,
            version,
            resolved_version_from_helper,
            len(data_bytes),
            mime_type,
        )

        if is_text_based_mime_type(mime_type) and component.enable_embed_resolution:
            log.info(
                "%s Artifact is text-based. Attempting recursive embed resolution.",
                log_prefix,
            )
            try:
                original_content_string = data_bytes.decode("utf-8")

                context_for_resolver = {
                    "artifact_service": artifact_service,
                    "session_context": {
                        "app_name": component.gateway_id,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                }
                config_for_resolver = {
                    "gateway_max_artifact_resolve_size_bytes": component.gateway_max_artifact_resolve_size_bytes,
                    "gateway_recursive_embed_depth": component.gateway_recursive_embed_depth,
                }

                resolved_content_string = await resolve_embeds_recursively_in_string(
                    text=original_content_string,
                    context=context_for_resolver,
                    resolver_func=evaluate_embed,
                    types_to_resolve=LATE_EMBED_TYPES,
                    resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                # Also resolve any template blocks in the artifact
                resolved_content_string = await resolve_template_blocks_in_string(
                    text=resolved_content_string,
                    artifact_service=artifact_service,
                    session_context=context_for_resolver["session_context"],
                    log_identifier=f"{log_prefix}[TemplateResolve]",
                )
                log.info(
                    "%s Template block resolution complete. Final size: %d bytes.",
                    log_prefix,
                    len(resolved_content_string),
                )

                data_bytes = resolved_content_string.encode("utf-8")
            except UnicodeDecodeError as ude:
                log.warning(
                    "%s Failed to decode artifact for recursive resolution: %s. Serving original content.",
                    log_prefix,
                    ude,
                )
            except Exception as resolve_err:
                log.exception(
                    "%s Error during recursive embed resolution: %s. Serving original content.",
                    log_prefix,
                    resolve_err,
                )
        else:
            log.info(
                "%s Artifact is not text-based or embed resolution is disabled. Serving original content.",
                log_prefix,
            )

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(data_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except FileNotFoundError:
        log.warning("%s Artifact version not found by service.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' version {version} not found.",
        )
    except ValueError as ve:
        log.warning("%s Invalid request (e.g., version format): %s", log_prefix, ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(ve)}",
        )
    except Exception as e:
        log.exception("%s Error loading artifact version: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load artifact version: {str(e)}",
        )


@router.get(
    "/by-uri",
    response_class=StreamingResponse,
    summary="Get Artifact by URI",
    description="Resolves a formal artifact:// URI and streams its content. This endpoint is secure and validates that the requesting user is authorized to access the specified artifact.",
)
async def get_artifact_by_uri(
    uri: str,
    requesting_user_id: str = Depends(get_user_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Resolves an artifact:// URI and streams its content.
    This allows fetching artifacts from any context, not just the current user's session,
    after performing an authorization check.
    """
    log_id_prefix = "[ArtifactRouter:by-uri]"
    log.info(
        "%s Received request for URI: %s from user: %s",
        log_id_prefix,
        uri,
        requesting_user_id,
    )
    artifact_service = component.get_shared_artifact_service()
    if not artifact_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact service not available.",
        )

    try:
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme != "artifact":
            raise ValueError("Invalid URI scheme, must be 'artifact'.")

        app_name = parsed_uri.netloc
        path_parts = parsed_uri.path.strip("/").split("/")
        if not app_name or len(path_parts) != 3:
            raise ValueError(
                "Invalid URI path structure. Expected artifact://app_name/user_id/session_id/filename"
            )

        owner_user_id, session_id, filename = path_parts

        query_params = parse_qs(parsed_uri.query)
        version_list = query_params.get("version")
        if not version_list or not version_list[0]:
            raise ValueError("Version query parameter is required.")
        version = version_list[0]

        log.info(
            "%s Parsed URI: app=%s, owner=%s, session=%s, file=%s, version=%s",
            log_id_prefix,
            app_name,
            owner_user_id,
            session_id,
            filename,
            version,
        )

        log.info(
            "%s User '%s' authorized to access artifact URI.",
            log_id_prefix,
            requesting_user_id,
        )

        loaded_artifact = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=owner_user_id,
            session_id=session_id,
            filename=filename,
            version=int(version),
            return_raw_bytes=True,
            log_identifier_prefix=log_id_prefix,
            component=component,
        )

        if loaded_artifact.get("status") != "success":
            raise HTTPException(status_code=404, detail=loaded_artifact.get("message"))

        content_bytes = loaded_artifact.get("raw_bytes")
        mime_type = loaded_artifact.get("mime_type", "application/octet-stream")

        filename_encoded = quote(filename)
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            },
        )

    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid artifact URI: {e}")
    except Exception as e:
        log.exception("%s Error fetching artifact by URI: %s", log_id_prefix, e)
        raise HTTPException(
            status_code=500, detail="Internal server error fetching artifact by URI"
        )


@router.delete(
    "/{session_id}/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Artifact",
    description="Deletes an artifact and all its versions.",
)
async def delete_artifact(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to delete artifacts from"
    ),
    filename: str = Path(
        ..., title="Filename", description="The name of the artifact to delete"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:delete"])),
):
    """
    Deletes the specified artifact (including all its versions)
    associated with the current user and session ID.
    """
    log_prefix = (
        f"[ArtifactRouter:Delete:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    # Validate session exists and belongs to user
    if not validate_session(session_id, user_id):
        log.warning("%s Session validation failed or access denied.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied.",
        )

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")

        await artifact_service.delete_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

        log.info("%s Artifact deletion request processed successfully.", log_prefix)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        log.exception("%s Error deleting artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete artifact: {str(e)}",
        )
