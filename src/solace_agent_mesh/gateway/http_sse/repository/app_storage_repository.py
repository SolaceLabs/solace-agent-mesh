"""
Repository for app storage CRUD operations.
"""

import json
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_

from ..shared import now_epoch_ms
from .models.app_storage_model import AppStorageModel

log = logging.getLogger(__name__)


class AppStorageRepository:
    """Repository for app storage key-value operations."""

    def get(
        self,
        db: DBSession,
        user_id: str,
        app_id: str,
        key: str,
    ) -> Optional[Any]:
        """
        Get a storage value by key.

        Returns:
            The deserialized value, or None if not found.
        """
        log.debug(f"[AppStorage] GET user={user_id} app={app_id} key={key}")

        record = (
            db.query(AppStorageModel)
            .filter(
                and_(
                    AppStorageModel.user_id == user_id,
                    AppStorageModel.app_id == app_id,
                    AppStorageModel.key == key,
                )
            )
            .first()
        )

        if record:
            value = json.loads(record.value)
            log.info(f"[AppStorage] GET found: user={user_id} app={app_id} key={key}")
            return value

        log.info(f"[AppStorage] GET not found: user={user_id} app={app_id} key={key}")
        return None

    def set(
        self,
        db: DBSession,
        user_id: str,
        app_id: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Set a storage value (upsert - insert or update).

        Args:
            db: Database session
            user_id: User ID
            app_id: App ID
            key: Storage key
            value: JSON-serializable value
        """
        log.info(f"[AppStorage] SET user={user_id} app={app_id} key={key}")
        now = now_epoch_ms()
        value_json = json.dumps(value)

        # Check if record exists
        record = (
            db.query(AppStorageModel)
            .filter(
                and_(
                    AppStorageModel.user_id == user_id,
                    AppStorageModel.app_id == app_id,
                    AppStorageModel.key == key,
                )
            )
            .first()
        )

        if record:
            # Update existing
            log.debug(f"[AppStorage] Updating existing record for key={key}")
            record.value = value_json
            record.updated_time = now
        else:
            # Insert new
            log.debug(f"[AppStorage] Creating new record for key={key}")
            record = AppStorageModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                app_id=app_id,
                key=key,
                value=value_json,
                created_time=now,
                updated_time=now,
            )
            db.add(record)

        db.commit()
        log.info(f"[AppStorage] SET complete: user={user_id} app={app_id} key={key} value_size={len(value_json)} bytes")

    def delete(
        self,
        db: DBSession,
        user_id: str,
        app_id: str,
        key: str,
    ) -> bool:
        """
        Delete a storage value by key.

        Returns:
            True if a record was deleted, False if not found.
        """
        log.info(f"[AppStorage] DELETE user={user_id} app={app_id} key={key}")

        result = (
            db.query(AppStorageModel)
            .filter(
                and_(
                    AppStorageModel.user_id == user_id,
                    AppStorageModel.app_id == app_id,
                    AppStorageModel.key == key,
                )
            )
            .delete()
        )

        db.commit()

        if result > 0:
            log.info(f"[AppStorage] DELETE success: user={user_id} app={app_id} key={key}")
            return True
        else:
            log.info(f"[AppStorage] DELETE not found: user={user_id} app={app_id} key={key}")
            return False

    def list_keys(
        self,
        db: DBSession,
        user_id: str,
        app_id: str,
        prefix: Optional[str] = None,
    ) -> list[str]:
        """
        List all storage keys for a user+app, optionally filtered by prefix.

        Returns:
            List of key names.
        """
        log.info(f"[AppStorage] LIST user={user_id} app={app_id} prefix={prefix}")

        query = db.query(AppStorageModel.key).filter(
            and_(
                AppStorageModel.user_id == user_id,
                AppStorageModel.app_id == app_id,
            )
        )

        if prefix:
            query = query.filter(AppStorageModel.key.like(f"{prefix}%"))

        keys = [row[0] for row in query.all()]

        log.info(f"[AppStorage] LIST found {len(keys)} keys for user={user_id} app={app_id}")
        return keys

    def clear(
        self,
        db: DBSession,
        user_id: str,
        app_id: str,
    ) -> int:
        """
        Clear all storage for a user+app.

        Returns:
            Number of records deleted.
        """
        log.info(f"[AppStorage] CLEAR user={user_id} app={app_id}")

        result = (
            db.query(AppStorageModel)
            .filter(
                and_(
                    AppStorageModel.user_id == user_id,
                    AppStorageModel.app_id == app_id,
                )
            )
            .delete()
        )

        db.commit()

        log.info(f"[AppStorage] CLEAR deleted {result} records for user={user_id} app={app_id}")
        return result
