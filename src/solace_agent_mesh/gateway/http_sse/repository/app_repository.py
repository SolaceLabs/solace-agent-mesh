"""
App repository implementation using SQLAlchemy.
"""

import uuid
from sqlalchemy.orm import Session as DBSession

from ..shared import now_epoch_ms
from ..shared.pagination import PaginationParams
from .models.app_model import AppModel, CreateAppModel


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
        """List all apps for a user."""
        query = (
            db.query(AppModel)
            .filter(
                AppModel.user_id == user_id,
                AppModel.archived_time.is_(None),
            )
            .order_by(AppModel.updated_time.desc())
        )

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.page_size)

        return query.all()

    def count_by_user(self, db: DBSession, user_id: str) -> int:
        """Count total apps for a user."""
        return (
            db.query(AppModel)
            .filter(
                AppModel.user_id == user_id,
                AppModel.archived_time.is_(None),
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
