"""
Router for user-related endpoints.
"""

from fastapi import APIRouter, Depends, Request as FastAPIRequest
from typing import Dict, Any

from ....gateway.http_sse.dependencies import get_session_manager
from ....gateway.http_sse.session_manager import SessionManager
from solace_ai_connector.common.log import log

router = APIRouter()

@router.get("/me", response_model=Dict[str, Any])
async def get_current_user(
    request: FastAPIRequest,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Retrieves information about the currently authenticated user.
    Uses request.state.user (set by AuthMiddleware) when available,
    falls back to SessionManager for legacy compatibility.
    """
    log.info("[GET /api/v1/users/me] Request received.")
    
    if hasattr(request.state, 'user') and request.state.user:
        user_info = request.state.user
        log.debug("Using user info from AuthMiddleware")
        return {
            "username": user_info.get("email") or user_info.get("id") or user_info.get("user_id") or user_info.get("username"),
            "authenticated": user_info["authenticated"],
            "auth_method": user_info["auth_method"]
        }
    
    try:
        user_id = session_manager.get_a2a_client_id(request)
        access_token = session_manager.get_access_token(request)
        is_authenticated = bool(access_token) or bool(session_manager.force_user_identity)
        
        auth_method = "none"
        if session_manager.force_user_identity:
            auth_method = "forced"
        elif is_authenticated:
            auth_method = "oidc"

        log.debug(f"Using SessionManager fallback: {user_id}, authenticated: {is_authenticated}")
        
        return {
            "username": user_id,
            "authenticated": is_authenticated,
            "auth_method": auth_method
        }
    except Exception as e:
        log.error(f"Error accessing session in /users/me: {e}")
        return {
            "username": "anonymous",
            "authenticated": False,
            "auth_method": "none"
        }