"""
Repository implementation for app tag data operations.
"""
from typing import List
import uuid

from sqlalchemy.orm import Session as DBSession

from .models import AppTagModel
from ..shared import now_epoch_ms


class AppTagRepository:
    """SQLAlchemy implementation of app tag repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def add_tag(self, app_id: str, tag: str) -> AppTagModel:
        """
        Add a tag to an app.

        Args:
            app_id: The app's internal ID (not app_id slug)
            tag: The tag text (will be normalized to lowercase)

        Returns:
            AppTagModel: The created tag record
        """
        normalized_tag = tag.lower().strip()

        model = AppTagModel(
            id=str(uuid.uuid4()),
            app_id=app_id,
            tag=normalized_tag,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_tags_for_app(self, app_id: str) -> List[str]:
        """
        Get all tags for an app.

        Args:
            app_id: The app's internal ID

        Returns:
            List[str]: List of tag strings
        """
        models = self.db.query(AppTagModel).filter(
            AppTagModel.app_id == app_id
        ).order_by(AppTagModel.tag).all()
        return [model.tag for model in models]

    def remove_tag(self, app_id: str, tag: str) -> bool:
        """
        Remove a tag from an app.

        Args:
            app_id: The app's internal ID
            tag: The tag to remove

        Returns:
            bool: True if removed successfully, False otherwise
        """
        normalized_tag = tag.lower().strip()
        result = self.db.query(AppTagModel).filter(
            AppTagModel.app_id == app_id,
            AppTagModel.tag == normalized_tag
        ).delete()
        self.db.commit()
        return result > 0

    def set_tags(self, app_id: str, tags: List[str]) -> List[str]:
        """
        Set all tags for an app (replaces existing tags).

        Args:
            app_id: The app's internal ID
            tags: List of tags to set

        Returns:
            List[str]: The final list of tags
        """
        # Remove all existing tags
        self.db.query(AppTagModel).filter(
            AppTagModel.app_id == app_id
        ).delete()

        # Add new tags (deduplicated and normalized)
        normalized_tags = list(set(tag.lower().strip() for tag in tags if tag.strip()))

        for tag in normalized_tags:
            model = AppTagModel(
                id=str(uuid.uuid4()),
                app_id=app_id,
                tag=tag,
                created_at=now_epoch_ms(),
            )
            self.db.add(model)

        self.db.commit()
        return sorted(normalized_tags)

    def search_apps_by_tag(self, tag: str) -> List[str]:
        """
        Find all app IDs that have a specific tag.

        Args:
            tag: The tag to search for

        Returns:
            List[str]: List of app IDs (internal IDs)
        """
        normalized_tag = tag.lower().strip()
        results = self.db.query(AppTagModel.app_id).filter(
            AppTagModel.tag == normalized_tag
        ).all()
        return [r[0] for r in results]

    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags across all apps.

        Returns:
            List[str]: List of unique tag strings, sorted alphabetically
        """
        results = self.db.query(AppTagModel.tag).distinct().order_by(AppTagModel.tag).all()
        return [r[0] for r in results]
