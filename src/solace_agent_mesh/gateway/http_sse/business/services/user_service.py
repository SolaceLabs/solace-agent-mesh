"""
User business service layer.
"""

from typing import Optional, Dict, Any
import json
from datetime import datetime, timezone

from ..domain.user_domain import UserProfileDomain, UserSessionsDomain
from ...data.repositories.user_repository import IUserRepository
from ...shared.types import UserId


class UserService:
    """Business service for user operations."""
    
    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository
    
    def get_user_profile(self, user_id: UserId) -> Optional[UserProfileDomain]:
        """Get user profile by ID."""
        user_model = self.user_repository.get_by_id(user_id)
        
        if not user_model:
            return None
        
        return self._model_to_domain(user_model)
    
    def get_user_by_username(self, username: str) -> Optional[UserProfileDomain]:
        """Get user by username."""
        user_model = self.user_repository.get_by_username(username)
        
        if not user_model:
            return None
        
        return self._model_to_domain(user_model)
    
    def get_user_by_email(self, email: str) -> Optional[UserProfileDomain]:
        """Get user by email."""
        user_model = self.user_repository.get_by_email(email)
        
        if not user_model:
            return None
        
        return self._model_to_domain(user_model)
    
    def create_or_update_user(
        self,
        user_id: UserId,
        user_info: Dict[str, Any]
    ) -> UserProfileDomain:
        """Create or update user profile."""
        # Create domain entity for validation
        domain = UserProfileDomain(
            id=user_id,
            name=user_info.get("name"),
            email=user_info.get("email"),
            username=user_info.get("username"),
            authenticated=user_info.get("authenticated", False),
            auth_method=user_info.get("auth_method"),
            preferences=user_info.get("preferences", {})
        )
        
        # Validate using domain rules
        if domain.name:
            domain.validate_name(domain.name)
        if domain.email:
            domain.validate_email(domain.email)
        if domain.username:
            domain.validate_username(domain.username)
        
        # Store in repository
        user_model = self.user_repository.create_or_update(user_id, user_info)
        
        return self._model_to_domain(user_model)
    
    def update_user_profile(
        self,
        user_id: UserId,
        name: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None
    ) -> Optional[UserProfileDomain]:
        """Update user profile information."""
        # Get existing user
        existing_user = self.get_user_profile(user_id)
        if not existing_user:
            return None
        
        # Update using domain rules
        existing_user.update_profile(name=name, email=email, username=username)
        
        # Convert back to storage format
        user_info = {
            "name": existing_user.name,
            "email": existing_user.email,
            "username": existing_user.username,
            "authenticated": existing_user.authenticated,
            "auth_method": existing_user.auth_method,
            "preferences": existing_user.preferences
        }
        
        # Update in repository
        updated_model = self.user_repository.update_info(user_id, user_info)
        
        if not updated_model:
            return None
        
        return self._model_to_domain(updated_model)
    
    def authenticate_user(
        self,
        user_id: UserId,
        auth_method: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> UserProfileDomain:
        """Authenticate a user and update their profile."""
        if user_info is None:
            user_info = {}
        
        # Get or create user
        existing_user = self.get_user_profile(user_id)
        
        if existing_user:
            # Update existing user
            existing_user.mark_login(auth_method)
            
            # Merge any new info
            if user_info:
                for key, value in user_info.items():
                    if key in ["name", "email", "username"] and value:
                        setattr(existing_user, key, value)
            
            # Convert to storage format
            storage_info = {
                "name": existing_user.name,
                "email": existing_user.email,
                "username": existing_user.username,
                "authenticated": existing_user.authenticated,
                "auth_method": existing_user.auth_method,
                "preferences": existing_user.preferences,
                "last_login": existing_user.last_login.isoformat() if existing_user.last_login else None
            }
            
            self.user_repository.update_info(user_id, storage_info)
            return existing_user
        else:
            # Create new user
            user_info.update({
                "authenticated": True,
                "auth_method": auth_method,
                "last_login": datetime.now(timezone.utc).isoformat()
            })
            
            return self.create_or_update_user(user_id, user_info)
    
    def logout_user(self, user_id: UserId) -> Optional[UserProfileDomain]:
        """Logout a user."""
        existing_user = self.get_user_profile(user_id)
        if not existing_user:
            return None
        
        existing_user.mark_logout()
        
        # Update in repository
        storage_info = {
            "name": existing_user.name,
            "email": existing_user.email,
            "username": existing_user.username,
            "authenticated": existing_user.authenticated,
            "auth_method": existing_user.auth_method,
            "preferences": existing_user.preferences
        }
        
        self.user_repository.update_info(user_id, storage_info)
        return existing_user
    
    def update_user_preferences(
        self,
        user_id: UserId,
        preferences: Dict[str, Any]
    ) -> Optional[UserProfileDomain]:
        """Update user preferences."""
        existing_user = self.get_user_profile(user_id)
        if not existing_user:
            return None
        
        existing_user.update_preferences(preferences)
        
        # Update in repository
        storage_info = {
            "name": existing_user.name,
            "email": existing_user.email,
            "username": existing_user.username,
            "authenticated": existing_user.authenticated,
            "auth_method": existing_user.auth_method,
            "preferences": existing_user.preferences
        }
        
        self.user_repository.update_info(user_id, storage_info)
        return existing_user
    
    def _model_to_domain(self, model) -> UserProfileDomain:
        """Convert database model to domain entity."""
        # Parse user info from JSON
        user_info = {}
        if model.info:
            try:
                user_info = json.loads(model.info)
            except (json.JSONDecodeError, TypeError):
                user_info = {}
        
        # Parse last_login if it exists
        last_login = None
        if user_info.get("last_login"):
            try:
                last_login = datetime.fromisoformat(user_info["last_login"])
            except (ValueError, TypeError):
                pass
        
        return UserProfileDomain(
            id=model.id,
            name=user_info.get("name"),
            email=user_info.get("email"),
            username=user_info.get("username"),
            authenticated=user_info.get("authenticated", False),
            auth_method=user_info.get("auth_method"),
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=last_login,
            preferences=user_info.get("preferences", {})
        )