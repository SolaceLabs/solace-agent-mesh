"""
Defines FastAPI dependency injectors to access shared resources
managed by the RestGatewayComponent.
"""

from fastapi import Depends, HTTPException, status
from typing import TYPE_CHECKING

from solace_ai_connector.common.log import log

if TYPE_CHECKING:
    from .component import RestGatewayComponent

sac_component_instance: "RestGatewayComponent" = None


def set_component_instance(component: "RestGatewayComponent"):
    """Called by the component during its startup to provide its instance."""
    global sac_component_instance
    if sac_component_instance is None:
        sac_component_instance = component
        log.info("[Dependencies] REST Gateway Component instance provided.")
    else:
        log.warning("[Dependencies] REST Gateway Component instance already set.")


from fastapi import Request
from google.adk.artifacts import BaseArtifactService
from typing import Optional


def get_sac_component() -> "RestGatewayComponent":
    """FastAPI dependency to get the SAC component instance."""
    if sac_component_instance is None:
        log.critical(
            "[Dependencies] REST Gateway Component instance accessed before it was set!"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend component not yet initialized.",
        )
    return sac_component_instance


def get_shared_artifact_service(
    component: "RestGatewayComponent" = Depends(get_sac_component),
) -> Optional[BaseArtifactService]:
    """FastAPI dependency to get the shared ArtifactService."""
    return component.shared_artifact_service


def get_user_id(
    request: Request, component: "RestGatewayComponent" = Depends(get_sac_component)
) -> str:
    """
    FastAPI dependency that returns the user's ID.
    It follows the same logic as the component's _extract_initial_claims:
    1. Checks for a forced identity (dev override).
    2. Checks for an authenticated user on the request state.
    3. Falls back to a default identity if auth is not enforced.
    4. Raises 401 if no identity can be determined.
    """
    log_id_prefix = "[Dep:get_user_id]"

    force_identity = component.get_config("force_user_identity")
    if force_identity:
        log.warning(
            "%s DEVELOPMENT MODE: Using forced identity '%s'",
            log_id_prefix,
            force_identity,
        )
        return force_identity

    if (
        hasattr(request.state, "user")
        and request.state.user
        and "id" in request.state.user
    ):
        user_id = request.state.user["id"]
        log.debug(
            "%s Found authenticated user ID in request state: %s",
            log_id_prefix,
            user_id,
        )
        return user_id

    enforce_auth = component.get_config("enforce_authentication", False)
    if not enforce_auth:
        default_identity = component.get_config("default_user_identity")
        if default_identity:
            log.info(
                "%s No authenticated user; using default_user_identity: '%s'",
                log_id_prefix,
                default_identity,
            )
            return default_identity

    log.warning("%s Could not determine user identity. Raising 401.", log_id_prefix)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User identity not found in request state or configuration.",
    )
