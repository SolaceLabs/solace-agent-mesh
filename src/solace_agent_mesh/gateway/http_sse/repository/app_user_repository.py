"""
Repository implementation for app user access data operations.
"""
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session as DBSession

from .models import AppUserModel
from .entities.app_user import AppUser
from ..shared import now_epoch_ms


class AppUserRepository:
    """SQLAlchemy implementation of app user repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def add_user_to_app(
        self,
        app_id: str,
        user_id: str,
        role: str,
        added_by_user_id: str
    ) -> AppUser:
        """
        Add a user to an app with a specific role.

        Args:
            app_id: The app ID
            user_id: The user ID to add
            role: The role to assign (owner, editor, viewer)
            added_by_user_id: The user ID who is granting access

        Returns:
            AppUser: The created app user access record
        """
        model = AppUserModel(
            id=str(uuid.uuid4()),
            app_id=app_id,
            user_id=user_id,
            role=role,
            added_at=now_epoch_ms(),
            added_by_user_id=added_by_user_id,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def get_app_users(self, app_id: str) -> List[AppUser]:
        """
        Get all users who have access to an app.

        Args:
            app_id: The app ID

        Returns:
            List[AppUser]: List of users with access to the app
        """
        models = self.db.query(AppUserModel).filter(
            AppUserModel.app_id == app_id
        ).all()
        return [self._model_to_entity(model) for model in models]

    def get_user_apps_access(self, user_id: str) -> List[AppUser]:
        """
        Get all apps a user has access to.

        Args:
            user_id: The user ID

        Returns:
            List[AppUser]: List of app access records for the user
        """
        models = self.db.query(AppUserModel).filter(
            AppUserModel.user_id == user_id
        ).all()
        return [self._model_to_entity(model) for model in models]

    def get_user_app_ids(self, user_id: str) -> List[str]:
        """
        Get all app IDs a user has access to.

        Args:
            user_id: The user ID

        Returns:
            List[str]: List of app IDs the user has access to
        """
        results = self.db.query(AppUserModel.app_id).filter(
            AppUserModel.user_id == user_id
        ).all()
        return [r[0] for r in results]

    def get_user_app_access(
        self,
        app_id: str,
        user_id: str
    ) -> Optional[AppUser]:
        """
        Get a specific user's access to an app.

        Args:
            app_id: The app ID
            user_id: The user ID

        Returns:
            Optional[AppUser]: The access record if found, None otherwise
        """
        model = self.db.query(AppUserModel).filter(
            AppUserModel.app_id == app_id,
            AppUserModel.user_id == user_id
        ).first()

        return self._model_to_entity(model) if model else None

    def update_user_role(
        self,
        app_id: str,
        user_id: str,
        new_role: str
    ) -> Optional[AppUser]:
        """
        Update a user's role for an app.

        Args:
            app_id: The app ID
            user_id: The user ID
            new_role: The new role to assign

        Returns:
            Optional[AppUser]: The updated access record if found, None otherwise
        """
        model = self.db.query(AppUserModel).filter(
            AppUserModel.app_id == app_id,
            AppUserModel.user_id == user_id
        ).first()

        if not model:
            return None

        model.role = new_role
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def remove_user_from_app(
        self,
        app_id: str,
        user_id: str
    ) -> bool:
        """
        Remove a user's access to an app.

        Args:
            app_id: The app ID
            user_id: The user ID to remove

        Returns:
            bool: True if removed successfully, False otherwise
        """
        result = self.db.query(AppUserModel).filter(
            AppUserModel.app_id == app_id,
            AppUserModel.user_id == user_id
        ).delete()
        self.db.commit()
        return result > 0

    def user_has_access(
        self,
        app_id: str,
        user_id: str
    ) -> bool:
        """
        Check if a user has access to an app.

        Args:
            app_id: The app ID
            user_id: The user ID

        Returns:
            bool: True if user has access, False otherwise
        """
        count = self.db.query(AppUserModel).filter(
            AppUserModel.app_id == app_id,
            AppUserModel.user_id == user_id
        ).count()
        return count > 0

    def _model_to_entity(self, model: AppUserModel) -> AppUser:
        """Convert SQLAlchemy model to domain entity."""
        return AppUser(
            id=model.id,
            app_id=model.app_id,
            user_id=model.user_id,
            role=model.role.value if hasattr(model.role, 'value') else model.role,
            added_at=model.added_at,
            added_by_user_id=model.added_by_user_id,
        )
