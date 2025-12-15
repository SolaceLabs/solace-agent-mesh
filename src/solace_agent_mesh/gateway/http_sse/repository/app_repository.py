"""
App repository implementation using SQLAlchemy.
"""

import uuid
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

from ..shared import now_epoch_ms
from ..shared.pagination import PaginationParams
from .models.app_model import AppModel, CreateAppModel
from .models.app_user_model import AppUserModel


class AppRepository:
    """Repository for app CRUD operations."""

    def create(
        self,
        db: DBSession,
        app_id: str,
        user_id: str,
        name: str,
        workspace_id: str,
        description: str | None = None,
        status: str = "draft",
        icon_emoji: str | None = None,
        icon_background: str | None = None,
    ) -> AppModel:
        """Create a new app."""
        now = now_epoch_ms()

        app = AppModel(
            id=str(uuid.uuid4()),
            app_id=app_id,
            user_id=user_id,
            name=name,
            description=description,
            workspace_id=workspace_id,
            status=status,
            current_version=0,
            icon_emoji=icon_emoji,
            icon_background=icon_background,
            created_time=now,
            updated_time=now,
        )

        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    def get_by_id(self, db: DBSession, app_id: str, user_id: str) -> AppModel | None:
        """Get app by app_id and user_id."""
        return (
            db.query(AppModel)
            .filter(
                AppModel.app_id == app_id,
                AppModel.user_id == user_id,
                AppModel.archived_time.is_(None),
            )
            .first()
        )

    def list_by_user(
        self,
        db: DBSession,
        user_id: str,
        pagination: PaginationParams | None = None,
    ) -> list[AppModel]:
        """
        List all apps visible to a user.

        Visibility rules:
        - User is the creator (user_id matches) - for backwards compatibility
        - OR user has access via app_users table (any role)
        - OR app is public (is_public = True)
        """
        # Subquery for app IDs the user has access to via app_users
        accessible_app_ids = (
            db.query(AppUserModel.app_id)
            .filter(AppUserModel.user_id == user_id)
            .subquery()
        )

        query = (
            db.query(AppModel)
            .filter(
                AppModel.archived_time.is_(None),
                or_(
                    AppModel.user_id == user_id,  # Creator (backwards compat)
                    AppModel.id.in_(accessible_app_ids),
                    AppModel.is_public == True,  # noqa: E712
                ),
            )
            .order_by(AppModel.updated_time.desc())
        )

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        return query.all()

    def count_by_user(self, db: DBSession, user_id: str) -> int:
        """
        Count total apps visible to a user.

        Same visibility rules as list_by_user.
        """
        # Subquery for app IDs the user has access to via app_users
        accessible_app_ids = (
            db.query(AppUserModel.app_id)
            .filter(AppUserModel.user_id == user_id)
            .subquery()
        )

        return (
            db.query(AppModel)
            .filter(
                AppModel.archived_time.is_(None),
                or_(
                    AppModel.user_id == user_id,  # Creator (backwards compat)
                    AppModel.id.in_(accessible_app_ids),
                    AppModel.is_public == True,  # noqa: E712
                ),
            )
            .count()
        )

    def update(
        self,
        db: DBSession,
        app_id: str,
        user_id: str,
        **kwargs,
    ) -> AppModel | None:
        """Update app metadata."""
        app = self.get_by_id(db, app_id, user_id)
        if not app:
            return None

        for key, value in kwargs.items():
            if hasattr(app, key) and value is not None:
                setattr(app, key, value)

        app.updated_time = now_epoch_ms()
        db.commit()
        db.refresh(app)
        return app

    def archive(self, db: DBSession, app_id: str, user_id: str) -> bool:
        """Soft delete an app."""
        app = self.get_by_id(db, app_id, user_id)
        if not app:
            return False

        app.archived_time = now_epoch_ms()
        db.commit()
        return True
