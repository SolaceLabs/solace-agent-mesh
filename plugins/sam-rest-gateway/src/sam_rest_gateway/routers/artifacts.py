"""
FastAPI router for managing artifacts via the REST API.
"""

import io
from typing import List, Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from google.adk.artifacts import BaseArtifactService

from solace_ai_connector.common.log import log
from solace_agent_mesh.common.types import ArtifactInfo
from solace_agent_mesh.agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
)
from ..dependencies import get_sac_component, get_shared_artifact_service, get_user_id
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import RestGatewayComponent

router = APIRouter()


@router.get(
    "/",
    response_model=List[ArtifactInfo],
    summary="List Session Artifacts",
)
async def list_artifacts(
    session_id: str = Query(..., description="The session ID the artifacts belong to."),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Lists all artifacts associated with a specific session for the authenticated user.
    """
    log_prefix = f"[GET /artifacts] User={user_id} Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Artifact service not configured."
        )

    try:
        artifact_info_list = await get_artifact_info_list(
            artifact_service=artifact_service,
            app_name=component.gateway_id,
            user_id=user_id,
            session_id=session_id,
        )
        return artifact_info_list
    except Exception as e:
        log.exception("%s Error listing artifacts: %s", log_prefix, e)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to list artifacts."
        )


@router.get(
    "/{filename}",
    summary="Download Latest Artifact",
)
async def get_latest_artifact(
    filename: str = Path(...),
    session_id: str = Query(..., description="The session ID the artifact belongs to."),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Downloads the content of the latest version of a specific artifact.
    """
    log_prefix = f"[GET /artifacts/{filename}] User={user_id} Session={session_id} -"
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Artifact service not configured."
        )

    try:
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=component.gateway_id,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version="latest",
            return_raw_bytes=True,
        )

        if load_result.get("status") != "success":
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Artifact '{filename}' not found."
            )

        data_bytes = load_result.get("raw_bytes")
        mime_type = load_result.get("mime_type", "application/octet-stream")

        return StreamingResponse(io.BytesIO(data_bytes), media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        log.exception("%s Error loading artifact: %s", log_prefix, e)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to load artifact."
        )


@router.get(
    "/{filename}/versions",
    response_model=List[int],
    summary="List Artifact Versions",
)
async def list_artifact_versions(
    filename: str = Path(...),
    session_id: str = Query(..., description="The session ID the artifact belongs to."),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Lists all available version numbers for a specific artifact.
    """
    log_prefix = (
        f"[GET /artifacts/{filename}/versions] User={user_id} Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Artifact service not configured."
        )

    if not hasattr(artifact_service, "list_versions"):
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"Artifact service '{type(artifact_service).__name__}' does not support version listing.",
        )

    try:
        versions = await artifact_service.list_versions(
            app_name=component.gateway_id,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        return versions
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Artifact '{filename}' not found."
        )
    except Exception as e:
        log.exception("%s Error listing artifact versions: %s", log_prefix, e)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to list artifact versions."
        )


@router.get(
    "/{filename}/versions/{version}",
    summary="Download Specific Artifact Version",
)
async def get_specific_artifact_version(
    filename: str = Path(...),
    version: Union[int, str] = Path(...),
    session_id: str = Query(..., description="The session ID the artifact belongs to."),
    artifact_service: BaseArtifactService = Depends(get_shared_artifact_service),
    user_id: str = Depends(get_user_id),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Downloads the content of a specific version of an artifact.
    """
    log_prefix = (
        f"[GET /artifacts/{filename}/v{version}] User={user_id} Session={session_id} -"
    )
    log.info("%s Request received.", log_prefix)

    if artifact_service is None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Artifact service not configured."
        )

    try:
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=component.gateway_id,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            version=version,
            return_raw_bytes=True,
        )

        if load_result.get("status") != "success":
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Artifact '{filename}' version '{version}' not found.",
            )

        data_bytes = load_result.get("raw_bytes")
        mime_type = load_result.get("mime_type", "application/octet-stream")

        return StreamingResponse(io.BytesIO(data_bytes), media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        log.exception("%s Error loading artifact version: %s", log_prefix, e)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to load artifact version."
        )
