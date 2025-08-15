"""
User-related response DTOs.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from ....shared.types import UserId
from .session_responses import SessionResponse


class UserProfileResponse(BaseModel):
    """Response DTO for user profile information."""
    id: UserId
    name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    authenticated: bool = False
    auth_method: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class CurrentUserResponse(BaseModel):
    """Response DTO for current user endpoint."""
    username: str
    authenticated: bool
    auth_method: str
    profile: UserProfileResponse


class UserSessionsResponse(BaseModel):
    """Response DTO for user's sessions."""
    user_id: UserId
    sessions: List[SessionResponse]
    total_count: int


class UserPreferencesResponse(BaseModel):
    """Response DTO for user preferences."""
    user_id: UserId
    preferences: Dict[str, Any]
    updated_at: Optional[datetime] = None


class AuthenticationResponse(BaseModel):
    """Response DTO for authentication result."""
    authenticated: bool
    user: Optional[UserProfileResponse] = None
    token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None