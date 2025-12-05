"""
Router for user-related endpoints.
Maintains backward compatibility with original API format.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_config_resolver, get_user_config
from solace_agent_mesh.shared.api.auth_utils import get_current_user
from ....common.middleware.config_resolver import ConfigResolver

log = logging.getLogger(__name__)

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


@router.get("/me/capabilities", response_model=dict[str, Any])
async def get_user_capabilities(
    scopes: str = Query(..., description="Comma-separated list of scopes to check"),
    user_config: dict[str, Any] = Depends(get_user_config),
    config_resolver: ConfigResolver = Depends(get_config_resolver),
):
    """
    Check if the current user has access to a list of scopes.

    Args:
        scopes: Comma-separated list of scopes to check (e.g., "sam:agent_builder:read,sam:connectors:read")
        user_config: User configuration resolved from dependencies
        config_resolver: ConfigResolver instance for checking scope access

    Returns:
        Dictionary with "capabilities" key containing a mapping of each scope to its access status (true/false)
    """
    user_id = user_config.get("user_profile", {}).get("id", "unknown")
    log.info(f"[GET /api/v1/users/me/capabilities] Request received for user: {user_id}")

    # Parse the comma-separated scopes
    scope_list = [scope.strip() for scope in scopes.split(",") if scope.strip()]

    if not scope_list:
        log.warning(f"[GET /api/v1/users/me/capabilities] No scopes provided for user: {user_id}")
        return {"capabilities": {}}

    log.debug(f"[GET /api/v1/users/me/capabilities] Checking scopes for user {user_id}: {scope_list}")

    # Check each scope using the same logic as ValidatedUserConfig
    capabilities = {}
    for scope in scope_list:
        # Use is_feature_enabled with the same structure as ValidatedUserConfig
        has_access = config_resolver.is_feature_enabled(
            user_config,
            {"tool_metadata": {"required_scopes": [scope]}},
            {},
        )
        capabilities[scope] = has_access
        log.debug(f"[GET /api/v1/users/me/capabilities] User {user_id} scope '{scope}': {has_access}")

    return {"capabilities": capabilities}
