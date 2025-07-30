"""
Router for user-related endpoints.
"""

from fastapi import APIRouter, Depends, Request as FastAPIRequest, HTTPException, status
from typing import Dict, Any

from ....gateway.http_sse.dependencies import get_sac_component, get_api_config
from solace_ai_connector.common.log import log

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent


router = APIRouter()


async def get_current_user(
    request: FastAPIRequest,
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    api_config: Dict[str, Any] = Depends(get_api_config),
) -> Dict[str, Any]:
    """
    Dependency to get the current user. It's the single source of truth for user identity.
    """
    user_identity = await component.authenticate_and_enrich_user(request)
    if not user_identity:
        use_auth = api_config.get("frontend_use_authorization", False)
        if use_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated.",
            )
        else:
            log.warning(
                "Could not identify user. Falling back to sam_dev_user for development."
            )
            return {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }
    return user_identity


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_endpoint(
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves information about the currently authenticated user.
    """
    log.info("[GET /api/v1/users/me] Request received for user: %s", user.get("id"))
    # Adapt the user profile to the format expected by the frontend
    return {
        "username": user.get("name") or user.get("id"),
        "authenticated": user.get("authenticated", False),
        "auth_method": user.get("auth_method", "none"),
        "profile": user,
    }
