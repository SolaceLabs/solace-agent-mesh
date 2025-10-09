"""
Router for user-related endpoints.
Maintains backward compatibility with original API format.
"""

from typing import Any

from fastapi import APIRouter, Depends
from solace_ai_connector.common.log import log

from .. import dependencies
from ..shared.auth_utils import get_current_user
from .dto.requests.user_requests import UpdateDefaultCredentialsRequest
from .dto.responses.user_responses import UpdateDefaultCredentialsResponse

router = APIRouter()


@router.get("/me", response_model=dict[str, Any])
async def get_current_user_endpoint(
    user: dict = Depends(get_current_user),
):
    log.info("[GET /api/v1/users/me] Request received.")

    # Get the user ID with proper priority
    username = (
        user.get("id")  # Primary ID from AuthMiddleware
        or user.get("user_id")
        or user.get("username")
        or user.get("email")
        or "anonymous"
    )

    return {
        "username": username,
        "authenticated": user.get("authenticated", False),
        "auth_method": user.get("auth_method", "none"),
    }


@router.put("/default-credentials", response_model=UpdateDefaultCredentialsResponse)
async def update_default_credentials(
    request: UpdateDefaultCredentialsRequest,
    user: dict = Depends(get_current_user),
):
    """
    Update default user credentials for development mode.

    This endpoint allows updating the default user credentials that are used
    when the gateway is running in development mode (use_auth=False).
    The credentials persist only for the current runtime session.
    """
    log.info(
        "[PUT /api/v1/users/default-credentials] Request received to update default credentials."
    )

    # Update global state
    dependencies.update_default_user_credentials(
        {"id": request.id, "name": request.name, "email": request.email}
    )

    updated_credentials = dependencies.get_default_user_credentials()

    log.info(
        f"[PUT /api/v1/users/default-credentials] Default credentials updated to: {updated_credentials}"
    )

    return UpdateDefaultCredentialsResponse(
        success=True,
        message="Default credentials updated successfully",
        credentials=updated_credentials,
    )
