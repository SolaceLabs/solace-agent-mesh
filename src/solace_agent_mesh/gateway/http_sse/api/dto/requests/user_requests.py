"""
User-related request DTOs.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from ....shared.types import UserId


class GetCurrentUserRequest(BaseModel):
    """Request DTO for getting current user information."""
    # No additional fields needed - user identity comes from authentication
    pass


class AuthenticateUserRequest(BaseModel):
    """Request DTO for user authentication."""
    # This would be populated by the authentication middleware
    token: Optional[str] = None
    auth_method: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None


class UserProfileRequest(BaseModel):
    """Request DTO for user profile operations."""
    user_id: UserId
    include_sessions: bool = Field(False, description="Include user's sessions in response")
    include_preferences: bool = Field(False, description="Include user preferences")