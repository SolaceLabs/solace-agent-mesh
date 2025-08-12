"""
User API controller using 3-tiered architecture.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from solace_ai_connector.common.log import log

from ..dto.requests.user_requests import GetCurrentUserRequest
from ..dto.responses.user_responses import CurrentUserResponse, UserProfileResponse

# Import the current user dependency from shared utilities
from ...shared.auth_utils import get_current_user

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_endpoint(
    user: dict = Depends(get_current_user),
):
    """
    Retrieves information about the currently authenticated user.
    """
    user_id = user.get("id")
    log.info("[GET /api/v1/users/me] Request received for user: %s", user_id)
    
    try:
        # Simplified user endpoint - return current user info without database lookup
        # Since we're focusing on persistence fixes, not user management
        
        # Handle potential username validation error gracefully
        clean_username = None
        try:
            username = user.get("name") or user_id
            # Simple validation - replace invalid characters
            clean_username = "".join(c for c in username if c.isalnum() or c == "_")[:50]
        except Exception as e:
            log.error("Error getting current user profile for user %s: %s", user_id, e)
        
        # Convert to response DTOs
        profile_response = UserProfileResponse(
            id=user_id,
            name=user.get("name"),
            email=user.get("email"),
            username=clean_username,
            authenticated=user.get("authenticated", True),
            auth_method=user.get("auth_method", "unknown"),
            created_at=None,  # Not stored in database
            updated_at=None,  # Not stored in database 
            last_login=None   # Not stored in database
        )
        
        return CurrentUserResponse(
            username=user.get("name") or user_id,
            authenticated=user.get("authenticated", True),
            auth_method=user.get("auth_method", "unknown"),
            profile=profile_response
        )
        
    except Exception as e:
        log.error("Error getting current user profile for user %s: %s", user_id, e)
        # Fallback to the original response format
        return CurrentUserResponse(
            username=user.get("name") or user.get("id"),
            authenticated=user.get("authenticated", False),
            auth_method=user.get("auth_method", "none"),
            profile=UserProfileResponse(
                id=user.get("id"),
                name=user.get("name"),
                email=user.get("email"),
                authenticated=user.get("authenticated", False),
                auth_method=user.get("auth_method")
            )
        )