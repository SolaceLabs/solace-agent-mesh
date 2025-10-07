"""
FastAPI router for managing session-specific artifacts via REST endpoints.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
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

from solace_ai_connector.common.log import log

from ....common.a2a.types import ArtifactInfo
from ....common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_recursively_in_string,
)
from ....common.utils.mime_helpers import is_text_based_mime_type
from ..dependencies import (
    ValidatedUserConfig,
    get_sac_component,
    get_session_validator,
    get_shared_artifact_service,
    get_user_config,
    get_user_id,
    get_session_manager,
    get_session_business_service_optional,
    get_db_optional,
)

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

from ..session_manager import SessionManager
from ..services.session_service import SessionService
from sqlalchemy.orm import Session

from ....agent.utils.artifact_helpers import (
    DEFAULT_SCHEMA_MAX_KEYS,
    format_artifact_uri,
    get_artifact_info_list,
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)


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
    sessionId: str | None = Form(None, description="Session ID (null/empty to create new session)", alias="sessionId"),
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
    session_service: SessionService | None = Depends(get_session_business_service_optional),
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

    # Use session ID from request body (matching sessionId pattern in session APIs)
    if sessionId and sessionId.strip():
        effective_session_id = sessionId.strip()
        log.info("%sUsing existing session: %s", log_prefix, effective_session_id)
    else:
        # Create new session when no sessionId provided (like chat does for new conversations)
        effective_session_id = session_manager.create_new_session_id(request)
        log.info("%sCreated new session for file upload: %s", log_prefix, effective_session_id)

        # Persist session in database if persistence is available (matching chat pattern)
        if session_service and db:
            try:
                session_service.create_session(
                    db=db,
                    user_id=user_id,
                    session_id=effective_session_id,
                    agent_id=None,  # Will be determined when first message is sent
                    name=None,      # Will be set when first message is sent
                )
                db.commit()
                log.info("%sSession created and committed to database: %s", log_prefix, effective_session_id)
            except Exception as session_error:
                db.rollback()
                log.warning("%sSession persistence failed, continuing with in-memory session: %s",
                           log_prefix, session_error)
        else:
            log.debug("%sNo persistence available - using in-memory session: %s",
                     log_prefix, effective_session_id)

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
    if not validate_session(effective_session_id, user_id):
        log.warning("%sSession validation failed for session: %s", log_prefix, effective_session_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid session or insufficient permissions.",
        )

    log.info("%sUploading file '%s' to session '%s'", log_prefix, filename.strip(), effective_session_id)

    try:
        # Read and validate file content
        content_bytes = await upload_file.read()
        if not content_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty.",
            )

        mime_type = upload_file.content_type or "application/octet-stream"
        filename_clean = filename.strip()

        log.debug("%sProcessing file: %s (%d bytes, %s)", log_prefix, filename_clean, len(content_bytes), mime_type)

        # Parse and validate metadata
        metadata = {}
        if metadata_json and metadata_json.strip():
            try:
                metadata = json.loads(metadata_json.strip())
                if not isinstance(metadata, dict):
                    raise ValueError("Metadata must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                log.warning("%sInvalid metadata JSON: %s", log_prefix, e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON in metadata field: {str(e)}",
                )

        app_name = component.get_config("name", "A2A_WebUI_App")

        # Store the artifact using the service
        artifact_uri = await artifact_service.store(
            app_name=app_name,
            user_id=user_id,
            session_id=effective_session_id,
            filename=filename_clean,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata=metadata,
        )

        log.info("%sArtifact stored successfully: %s (%d bytes)", log_prefix, artifact_uri, len(content_bytes))

        # Return standardized response using Pydantic model (ensures camelCase conversion)
        return ArtifactUploadResponse(
            uri=artifact_uri,
            session_id=effective_session_id,  # Will be returned as "sessionId" due to alias
            filename=filename_clean,
            size=len(content_bytes),
            mime_type=mime_type,  # Will be returned as "mimeType" due to alias
            metadata=metadata,
            created_at=datetime.now(timezone.utc).isoformat(),  # Will be returned as "createdAt" due to alias
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
        ..., title="Session ID", description="The session ID to get artifacts from"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists the available integer versions for a given artifact filename
    associated with the current user and session ID.
    """

    log_prefix = f"[ArtifactRouter:ListVersions:{filename}] User={user_id}, Session={session_id} -"
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

        versions = await artifact_service.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        log.info("%s Found versions: %s", log_prefix, versions)
        return versions
    except FileNotFoundError:
        log.warning("%s Artifact not found.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{filename}' not found for this session.",
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
        ..., title="Session ID", description="The session ID to list artifacts for"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:list"])),
):
    """
    Lists detailed information (filename, size, type, modified date, uri)
    for all artifacts associated with the specified user and session ID
    by calling the artifact helper function.
    """

    log_prefix = f"[ArtifactRouter:ListInfo] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    # Validate session exists and belongs to user
    if not validate_session(session_id, user_id):
        log.warning(
            "%s Session validation failed for session_id=%s, user_id=%s",
            log_prefix,
            session_id,
            user_id,
        )
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

        artifact_info_list = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        log.info(
            "%s Returning %d artifact details.", log_prefix, len(artifact_info_list)
        )
        return artifact_info_list

    except Exception as e:
        log.exception(
            "%s Error retrieving artifact details via helper: %s", log_prefix, e
        )
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
        ..., title="Session ID", description="The session ID to get artifacts from"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of the latest version of the specified artifact
    associated with the current user and session ID.
    """
    log_prefix = (
        f"[ArtifactRouter:GetLatest:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        log.error("%s Artifact service is not configured or available.", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Artifact service is not configured.",
        )

    try:
        app_name = component.get_config("name", "A2A_WebUI_App")
        artifact_part = await artifact_service.load_artifact(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
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
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                data_bytes = resolved_content_string.encode("utf-8")
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(data_bytes),
                )
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
        ..., title="Session ID", description="The session ID to get artifacts from"
    ),
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    version: int | str = Path(
        ...,
        title="Version",
        description="The specific version number to retrieve, or 'latest'",
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:load"])),
):
    """
    Retrieves the content of a specific version of the specified artifact
    associated with the current user and session ID.
    """
    log_prefix = f"[ArtifactRouter:GetVersion:{filename} v{version}] User={user_id}, Session={session_id} -"
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

        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
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
                    log_identifier=f"{log_prefix}[RecursiveResolve]",
                    config=config_for_resolver,
                    max_depth=component.gateway_recursive_embed_depth,
                    max_total_size=component.gateway_max_artifact_resolve_size_bytes,
                )
                data_bytes = resolved_content_string.encode("utf-8")
                log.info(
                    "%s Recursive embed resolution complete. New size: %d bytes.",
                    log_prefix,
                    len(data_bytes),
                )
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


@router.post(
    "/{session_id}/{filename}",
    status_code=status.HTTP_201_CREATED,
    response_model=dict[str, Any],
    summary="Upload Artifact (Create/Update Version with Metadata)",
    description="Uploads file content and optional metadata to create or update an artifact version.",
)
async def upload_artifact(
    session_id: str = Path(
        ..., title="Session ID", description="The session ID to upload artifacts to"
    ),
    filename: str = Path(
        ..., title="Filename", description="The name of the artifact to create/update"
    ),
    upload_file: UploadFile = File(..., description="The file content to upload"),
    metadata_json: str | None = Form(
        None, description="JSON string of artifact metadata (e.g., description, source)"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    validate_session: Callable[[str, str], bool] = Depends(get_session_validator),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_config: dict = Depends(ValidatedUserConfig(["tool:artifact:create"])),
):
    """
    Uploads a file to create a new version of the specified artifact
    associated with the current user and session ID. Also saves associated metadata.
    """
    log_prefix = (
        f"[ArtifactRouter:Post:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info(
        "%s Request received. Upload filename: '%s', content type: %s, Metadata provided: %s",
        log_prefix,
        upload_file.filename,
        upload_file.content_type,
    )

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
        content_bytes = await upload_file.read()
        if not content_bytes:
            log.warning("%s Uploaded file is empty.", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file cannot be empty.",
            )

        mime_type = upload_file.content_type or "application/octet-stream"

        parsed_metadata = {}
        if metadata_json:
            try:
                parsed_metadata = json.loads(metadata_json)
                if not isinstance(parsed_metadata, dict):
                    log.warning(
                        "%s Metadata JSON did not parse to a dictionary. Ignoring.",
                        log_prefix,
                    )
                    parsed_metadata = {}
            except json.JSONDecodeError as json_err:
                log.warning(
                    "%s Failed to parse metadata_json: %s. Proceeding without it.",
                    log_prefix,
                    json_err,
                )

        app_name = component.get_config("name", "A2A_WebUI_App")
        current_timestamp = datetime.now(timezone.utc)

        save_result = await save_artifact_with_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_dict=parsed_metadata,
            timestamp=current_timestamp,
            schema_max_keys=component.get_config(
                "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
            ),
        )

        if save_result["status"] == "success":
            log.info(
                "%s Artifact and metadata processing completed. Data version: %s, Metadata version: %s. Message: %s",
                log_prefix,
                save_result.get("data_version"),
                save_result.get("metadata_version"),
                save_result.get("message"),
            )
            saved_version = save_result.get("data_version")
            artifact_uri = format_artifact_uri(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                version=saved_version,
            )
            log.info(
                "%s Successfully saved artifact. Returning URI: %s",
                log_prefix,
                artifact_uri,
            )
            return {
                "filename": filename,
                "data_version": saved_version,
                "metadata_version": save_result.get("metadata_version"),
                "mime_type": mime_type,
                "size": len(content_bytes),
                "message": save_result.get("message"),
                "status": save_result["status"],
                "uri": artifact_uri,
            }
        else:
            log.error(
                "%s Failed to save artifact and metadata: %s",
                log_prefix,
                save_result.get("message"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=save_result.get(
                    "message", "Failed to save artifact with metadata."
                ),
            )

    except HTTPException:
        raise
    except Exception as e:
        log.exception("%s Error saving artifact: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save artifact: {str(e)}",
        )
    finally:
        await upload_file.close()
        log.debug("%s Upload file closed.", log_prefix)


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
