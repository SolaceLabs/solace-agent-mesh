"""
User domain entities and business rules.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, EmailStr

from ...shared.types import UserId
from .session_domain import SessionDomain


class UserProfileDomain(BaseModel):
    """User profile domain entity with business rules."""
    
    id: UserId
    name: Optional[str] = None
    email: Optional[str] = None  # Using str instead of EmailStr for flexibility
    username: Optional[str] = None
    authenticated: bool = False
    auth_method: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    preferences: Dict[str, Any] = {}
    
    def update_profile(
        self, 
        name: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None
    ) -> None:
        """Update user profile information."""
        if name is not None:
            self.validate_name(name)
            self.name = name
        
        if email is not None:
            self.validate_email(email)
            self.email = email
        
        if username is not None:
            self.validate_username(username)
            self.username = username
        
        self.updated_at = datetime.now(timezone.utc)
    
    def validate_name(self, name: str) -> None:
        """Validate user name."""
        if not name or len(name.strip()) == 0:
            raise ValueError("Name cannot be empty")
        if len(name) > 100:
            raise ValueError("Name cannot exceed 100 characters")
    
    def validate_email(self, email: str) -> None:
        """Validate email format."""
        if not email or len(email.strip()) == 0:
            raise ValueError("Email cannot be empty")
        if "@" not in email or "." not in email:
            raise ValueError("Invalid email format")
        if len(email) > 255:
            raise ValueError("Email cannot exceed 255 characters")
    
    def validate_username(self, username: str) -> None:
        """Validate username."""
        if not username or len(username.strip()) == 0:
            raise ValueError("Username cannot be empty")
        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")
        # Only allow alphanumeric characters and underscores
        if not username.replace("_", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, and underscores")
    
    def mark_login(self, auth_method: str) -> None:
        """Mark user as logged in."""
        self.authenticated = True
        self.auth_method = auth_method
        self.last_login = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_logout(self) -> None:
        """Mark user as logged out."""
        self.authenticated = False
        self.auth_method = None
        self.updated_at = datetime.now(timezone.utc)
    
    def update_preferences(self, preferences: Dict[str, Any]) -> None:
        """Update user preferences."""
        self.preferences.update(preferences)
        self.updated_at = datetime.now(timezone.utc)
    
    def get_display_name(self) -> str:
        """Get the best available display name for the user."""
        return self.name or self.username or self.id


class UserSessionsDomain(BaseModel):
    """User sessions domain entity."""
    
    user: UserProfileDomain
    sessions: List[SessionDomain] = []
    total_session_count: int = 0
    
    def add_session(self, session: SessionDomain) -> None:
        """Add a session to the user."""
        if session.user_id != self.user.id:
            raise ValueError("Session does not belong to this user")
        
        self.sessions.append(session)
        self.total_session_count += 1
    
    def get_active_sessions(self) -> List[SessionDomain]:
        """Get all active sessions."""
        from ...shared.enums import SessionStatus
        return [session for session in self.sessions if session.status == SessionStatus.ACTIVE]
    
    def get_sessions_by_agent(self, agent_id: str) -> List[SessionDomain]:
        """Get sessions filtered by agent."""
        return [session for session in self.sessions if session.agent_id == agent_id]