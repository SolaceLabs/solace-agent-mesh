"""
FastAPI router for managing session-specific artifacts via REST endpoints.
"""

from typing import (
    List,
    Dict,
    Optional,
    Union,
    Any,
    TYPE_CHECKING,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Path,
    status,
    Form,
)
from fastapi.responses import StreamingResponse, Response
from google.adk.artifacts import BaseArtifactService
import io
import json
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, quote

from ..dependencies import (
    get_shared_artifact_service,
    get_sac_component,
    ensure_session_id,
    get_user_id,
    get_config_resolver,
    get_user_config,
)

from solace_ai_connector.common.log import log

from ....common.middleware import ConfigResolver
from ....common.types import ArtifactInfo
from ....common.utils.mime_helpers import is_text_based_mime_type
from ....common.utils.embeds import (
    resolve_embeds_recursively_in_string,
    evaluate_embed,
    LATE_EMBED_TYPES,
)


if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent
from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    save_artifact_with_metadata,
    load_artifact_content_or_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)

router = APIRouter()


@router.get(
    "/{filename}/versions",
    response_model=List[int],
    summary="List Artifact Versions",
    description="Retrieves a list of available version numbers for a specific artifact.",
)
async def list_artifact_versions(
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Lists the available integer versions for a given artifact filename
    associated with the current user and session ID.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:list"]}, {}
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to list artifact versions"
        )

    log_prefix = f"[ArtifactRouter:ListVersions:{filename}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

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
    "/",
    response_model=List[ArtifactInfo],
    summary="List Artifact Information",
    description="Retrieves detailed information for artifacts available for the current user session.",
)
async def list_artifacts(
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Lists detailed information (filename, size, type, modified date, uri)
    for all artifacts associated with the current user and session ID
    by calling the artifact helper function.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:list"]}, {}
    ):
        raise HTTPException(status_code=403, detail="Not authorized to list artifacts")

    log_prefix = f"[ArtifactRouter:ListInfo] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

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
    "/{filename}",
    summary="Get Latest Artifact Content",
    description="Retrieves the content of the latest version of a specific artifact.",
)
async def get_latest_artifact(
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Retrieves the content of the latest version of the specified artifact
    associated with the current user and session ID.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:load"]}, {}
    ):
        raise HTTPException(status_code=403, detail="Not authorized to load artifact")
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
    "/{filename}/versions/{version}",
    summary="Get Specific Artifact Version Content",
    description="Retrieves the content of a specific version of an artifact.",
)
async def get_specific_artifact_version(
    filename: str = Path(..., title="Filename", description="The name of the artifact"),
    version: Union[int, str] = Path(
        ...,
        title="Version",
        description="The specific version number to retrieve, or 'latest'",
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Retrieves the content of a specific version of the specified artifact
    associated with the current user and session ID.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:load"]}, {}
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to load artifact version"
        )
    log_prefix = f"[ArtifactRouter:GetVersion:{filename} v{version}] User={user_id}, Session={session_id} -"
    log.info("%s Request received.", log_prefix)

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
            log_identifier_prefix=f"[ArtifactRouter:GetVersion]",
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
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Resolves an artifact:// URI and streams its content.
    This allows fetching artifacts from any context, not just the current user's session,
    after performing an authorization check.
    """
    log_id_prefix = f"[ArtifactRouter:by-uri]"
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

        if not config_resolver.is_feature_enabled(
            user_config, {"required_scopes": ["tool:artifact:load"]}, {}
        ):
            raise HTTPException(
                status_code=403, detail="Not authorized to load artifact by URI"
            )
            log.warning(
                "%s Authorization denied for user '%s' to access artifact URI '%s'",
                log_id_prefix,
                requesting_user_id,
                uri,
            )
            raise HTTPException(
                status_code=403, detail="Permission denied to access this artifact."
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
    "/{filename}",
    status_code=status.HTTP_201_CREATED,
    response_model=Dict[str, Any],
    summary="Upload Artifact (Create/Update Version with Metadata)",
    description="Uploads file content and optional metadata to create or update an artifact version.",
)
async def upload_artifact(
    filename: str = Path(
        ..., title="Filename", description="The name of the artifact to create/update"
    ),
    upload_file: UploadFile = File(..., description="The file content to upload"),
    metadata_json: Optional[str] = Form(
        None, description="JSON string of artifact metadata (e.g., description, source)"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Uploads a file to create a new version of the specified artifact
    associated with the current user and session ID. Also saves associated metadata.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:create"]}, {}
    ):
        raise HTTPException(status_code=403, detail="Not authorized to upload artifact")
    log_prefix = (
        f"[ArtifactRouter:Post:{filename}] User={user_id}, Session={session_id} -"
    )
    log.info(
        "%s Request received. Upload filename: '%s', content type: %s",
        log_prefix,
        upload_file.filename,
        upload_file.content_type,
        f"Metadata provided: {bool(metadata_json)}",
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

        if save_result["status"] in ["success", "partial_success"]:
            log.info(
                "%s Artifact and metadata processing completed. Data version: %s, Metadata version: %s. Message: %s",
                log_prefix,
                save_result.get("data_version"),
                save_result.get("metadata_version"),
                save_result.get("message"),
            )
            return {
                "filename": filename,
                "data_version": save_result.get("data_version"),
                "metadata_version": save_result.get("metadata_version"),
                "mime_type": mime_type,
                "size": len(content_bytes),
                "message": save_result.get("message"),
                "status": save_result["status"],
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
    "/{filename}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Artifact",
    description="Deletes an artifact and all its versions.",
)
async def delete_artifact(
    filename: str = Path(
        ..., title="Filename", description="The name of the artifact to delete"
    ),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    session_id: str = Depends(ensure_session_id),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
    user_config: dict = Depends(get_user_config),
):
    """
    Deletes the specified artifact (including all its versions)
    associated with the current user and session ID.
    """
    if not config_resolver.is_feature_enabled(
        user_config, {"required_scopes": ["tool:artifact:delete"]}, {}
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete artifact")
    log_prefix = (
        f"[ArtifactRouter:Delete:{filename}] User={user_id}, Session={session_id} -"
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
