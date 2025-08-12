"""
User repository interface and implementation.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import json

from .base_repository import IBaseRepository, BaseRepository
from ..models.user_models import User as UserModel
from ...shared.types import UserId


class IUserRepository(IBaseRepository[UserModel]):
    """User repository interface."""
    
    @abstractmethod
    def get_by_username(self, username: str) -> Optional[UserModel]:
        """Get user by username."""
        pass
    
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email."""
        pass
    
    @abstractmethod
    def update_info(self, user_id: UserId, user_info: Dict[str, Any]) -> Optional[UserModel]:
        """Update user information."""
        pass
    
    @abstractmethod
    def create_or_update(self, user_id: UserId, user_info: Dict[str, Any]) -> UserModel:
        """Create or update user information."""
        pass


class UserRepository(BaseRepository[UserModel], IUserRepository):
    """User repository implementation."""
    
    def __init__(self, db: Session):
        super().__init__(db, UserModel)
    
    def get_by_username(self, username: str) -> Optional[UserModel]:
        """Get user by username."""
        # Since username is stored in the info JSON field, we need to query differently
        users = self.db.query(UserModel).all()
        for user in users:
            if user.info:
                try:
                    user_data = json.loads(user.info)
                    if user_data.get("username") == username or user_data.get("name") == username:
                        return user
                except (json.JSONDecodeError, TypeError):
                    continue
        return None
    
    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email."""
        # Since email is stored in the info JSON field, we need to query differently
        users = self.db.query(UserModel).all()
        for user in users:
            if user.info:
                try:
                    user_data = json.loads(user.info)
                    if user_data.get("email") == email:
                        return user
                except (json.JSONDecodeError, TypeError):
                    continue
        return None
    
    def update_info(self, user_id: UserId, user_info: Dict[str, Any]) -> Optional[UserModel]:
        """Update user information."""
        # Serialize user_info to JSON string
        info_json = json.dumps(user_info)
        return self.update(user_id, {"info": info_json})
    
    def create_or_update(self, user_id: UserId, user_info: Dict[str, Any]) -> UserModel:
        """Create or update user information."""
        existing_user = self.get_by_id(user_id)
        
        if existing_user:
            # Update existing user
            return self.update_info(user_id, user_info)
        else:
            # Create new user
            info_json = json.dumps(user_info)
            user_data = {
                "id": user_id,
                "info": info_json
            }
            return self.create(user_data)