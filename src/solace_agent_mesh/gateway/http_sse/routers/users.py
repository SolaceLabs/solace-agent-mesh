"""
Router for user-related endpoints.
Maintains backward compatibility with original API format.
"""

from typing import Any

from fastapi import APIRouter, Depends
from solace_ai_connector.common.log import log

from ..shared.auth_utils import get_current_user

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
