"""
Filesystem implementation of App Storage Service.

Used for local development where files are stored on the local filesystem.
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from .base import AppStorageService

logger = logging.getLogger(__name__)


class FilesystemAppStorageService(AppStorageService):
    """
    Local filesystem implementation for app storage.

    Directory structure:
    {base_path}/{user_id}/{app_id}/
    ├── latest/           # Current workspace build (preview)
    │   ├── dist/         # Built files from workspace
    │   └── VERSION       # Version metadata
    └── versions/         # Deployed version snapshots
        ├── 0.0.1/
        ├── 0.0.2/
        └── ...
    """

    def __init__(
        self,
        base_path: str,
        workspace_base: Optional[str] = None,
    ):
        """
        Initialize filesystem app storage.

        Args:
            base_path: Root directory for app storage
            workspace_base: If provided and matches base_path pattern,
                           sync_dist becomes a no-op (already in place)
        """
        self.base_path = Path(base_path).expanduser().resolve()
        self.workspace_base = Path(workspace_base).expanduser().resolve() if workspace_base else None

        # Create base directory
        self.base_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"FilesystemAppStorageService initialized at {self.base_path}")

    def _get_latest_path(self, user_id: str, app_id: str) -> Path:
        """Get the storage path for an app's latest (preview) directory."""
        return self.base_path / user_id / app_id / "latest"

    def _get_app_dist_path(self, user_id: str, app_id: str) -> Path:
        """Get the storage path for an app's latest dist files."""
        return self._get_latest_path(user_id, app_id) / "dist"

    def _is_same_location(self, user_id: str, app_id: str, dist_path: Path) -> bool:
        """Check if dist_path is already at the storage location."""
        # With the new latest/ structure, workspace and storage are always different
        # so we always need to sync
        return False

    async def sync_dist(
        self,
        user_id: str,
        app_id: str,
        dist_path: Path,
    ) -> None:
        """
        Sync dist/ directory to storage.

        If storage location is the same as workspace location,
        this is a no-op. Otherwise, copies files.
        """
        log_prefix = f"[FSAppStorage:Sync:{app_id}] "

        if not dist_path.exists():
            logger.warning(f"{log_prefix}Source dist path does not exist: {dist_path}")
            return

        # Check if already in place
        if self._is_same_location(user_id, app_id, dist_path):
            logger.debug(f"{log_prefix}dist/ already at storage location, skipping sync")
            return

        storage_path = self._get_app_dist_path(user_id, app_id)

        def _sync():
            # Remove existing dist if present
            if storage_path.exists():
                shutil.rmtree(storage_path)

            # Copy dist to storage
            shutil.copytree(dist_path, storage_path)

            # Count files for logging
            file_count = sum(1 for _ in storage_path.rglob("*") if _.is_file())
            return file_count

        file_count = await asyncio.to_thread(_sync)
        logger.info(f"{log_prefix}Synced {file_count} files to {storage_path}")

    async def get_file(
        self,
        user_id: str,
        app_id: str,
        path: str,
    ) -> Optional[bytes]:
        """Get a file from storage."""
        log_prefix = f"[FSAppStorage:Get:{app_id}] "

        storage_path = self._get_app_dist_path(user_id, app_id)
        file_path = storage_path / path

        # Security: prevent directory traversal
        try:
            file_path = file_path.resolve()
            if not file_path.is_relative_to(storage_path.resolve()):
                logger.warning(f"{log_prefix}Path traversal attempt: {path}")
                return None
        except (ValueError, OSError):
            return None

        if not file_path.exists() or not file_path.is_file():
            logger.debug(f"{log_prefix}File not found: {path}")
            return None

        def _read():
            return file_path.read_bytes()

        try:
            content = await asyncio.to_thread(_read)
            logger.debug(f"{log_prefix}Read {len(content)} bytes from {path}")
            return content
        except OSError as e:
            logger.error(f"{log_prefix}Failed to read {path}: {e}")
            return None

    async def list_files(
        self,
        user_id: str,
        app_id: str,
        prefix: str = "",
    ) -> list[str]:
        """List files in the app's dist/."""
        storage_path = self._get_app_dist_path(user_id, app_id)

        if not storage_path.exists():
            return []

        def _list():
            files = []
            search_path = storage_path / prefix if prefix else storage_path

            if not search_path.exists():
                return []

            for file_path in search_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(storage_path)
                    files.append(str(rel_path))

            return sorted(files)

        return await asyncio.to_thread(_list)

    async def delete_app(
        self,
        user_id: str,
        app_id: str,
    ) -> None:
        """Delete all files for an app."""
        log_prefix = f"[FSAppStorage:Delete:{app_id}] "

        # Delete the app directory (parent of dist/)
        app_path = self.base_path / user_id / app_id

        if not app_path.exists():
            logger.debug(f"{log_prefix}App directory does not exist")
            return

        def _delete():
            shutil.rmtree(app_path)

        await asyncio.to_thread(_delete)
        logger.info(f"{log_prefix}Deleted app storage at {app_path}")

    async def app_exists(
        self,
        user_id: str,
        app_id: str,
    ) -> bool:
        """Check if an app has stored files."""
        storage_path = self._get_app_dist_path(user_id, app_id)
        return storage_path.exists() and any(storage_path.iterdir())

    def _get_version_path(self, user_id: str, app_id: str, version: str) -> Path:
        """Get the storage path for a specific version."""
        return self.base_path / user_id / app_id / "versions" / version

    async def deploy_version(
        self,
        user_id: str,
        app_id: str,
        version: str,
        source_path: Path,
    ) -> None:
        """Deploy a specific version from local dist/ to versioned storage."""
        log_prefix = f"[FSAppStorage:Deploy:{app_id}:{version}] "

        if not source_path.exists():
            logger.warning(f"{log_prefix}Source path does not exist: {source_path}")
            return

        version_path = self._get_version_path(user_id, app_id, version)

        def _deploy():
            # Remove existing version if present
            if version_path.exists():
                shutil.rmtree(version_path)

            # Copy dist to version path
            shutil.copytree(source_path, version_path)

            # Count files for logging
            file_count = sum(1 for _ in version_path.rglob("*") if _.is_file())
            return file_count

        file_count = await asyncio.to_thread(_deploy)
        logger.info(f"{log_prefix}Deployed {file_count} files to {version_path}")

    async def get_version_file(
        self,
        user_id: str,
        app_id: str,
        version: str,
        path: str,
    ) -> Optional[bytes]:
        """Get a file from a specific deployed version."""
        log_prefix = f"[FSAppStorage:GetVersion:{app_id}:{version}] "

        version_path = self._get_version_path(user_id, app_id, version)
        file_path = version_path / path

        # Security: prevent directory traversal
        try:
            file_path = file_path.resolve()
            if not file_path.is_relative_to(version_path.resolve()):
                logger.warning(f"{log_prefix}Path traversal attempt: {path}")
                return None
        except (ValueError, OSError):
            return None

        if not file_path.exists() or not file_path.is_file():
            logger.debug(f"{log_prefix}File not found: {path}")
            return None

        def _read():
            return file_path.read_bytes()

        try:
            content = await asyncio.to_thread(_read)
            logger.debug(f"{log_prefix}Read {len(content)} bytes from {path}")
            return content
        except OSError as e:
            logger.error(f"{log_prefix}Failed to read {path}: {e}")
            return None

    async def version_exists(
        self,
        user_id: str,
        app_id: str,
        version: str,
    ) -> bool:
        """Check if a specific version exists in storage."""
        version_path = self._get_version_path(user_id, app_id, version)
        return version_path.exists() and any(version_path.iterdir())

    async def list_versions(
        self,
        user_id: str,
        app_id: str,
    ) -> list[str]:
        """List all deployed versions for an app."""
        versions_path = self.base_path / user_id / app_id / "versions"

        if not versions_path.exists():
            return []

        def _list():
            versions = []
            for item in versions_path.iterdir():
                if item.is_dir() and any(item.iterdir()):
                    versions.append(item.name)
            # Sort by semver (newest first)
            try:
                versions.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
            except (ValueError, AttributeError):
                versions.sort(reverse=True)
            return versions

        return await asyncio.to_thread(_list)

    def _get_preview_version_path(self, user_id: str, app_id: str) -> Path:
        """Get the storage path for an app's preview VERSION file."""
        return self._get_latest_path(user_id, app_id) / "VERSION"

    async def sync_preview_metadata(
        self,
        user_id: str,
        app_id: str,
        version_file_path: Path,
    ) -> None:
        """
        Sync the VERSION file to preview storage.

        Copies the VERSION file from workspace to app storage so that
        preview version info is available even without workspace.
        """
        log_prefix = f"[FSAppStorage:SyncMeta:{app_id}] "

        if not version_file_path.exists():
            logger.debug(f"{log_prefix}VERSION file does not exist: {version_file_path}")
            return

        storage_version_path = self._get_preview_version_path(user_id, app_id)

        def _sync():
            # Ensure parent directory exists
            storage_version_path.parent.mkdir(parents=True, exist_ok=True)
            # Copy VERSION file
            shutil.copy2(version_file_path, storage_version_path)

        await asyncio.to_thread(_sync)
        logger.info(f"{log_prefix}Synced VERSION file to {storage_version_path}")

    async def get_preview_version(
        self,
        user_id: str,
        app_id: str,
    ) -> Optional[dict]:
        """
        Get the preview VERSION file contents from storage.

        Returns:
            Parsed VERSION file contents as dict, or None if not found
        """
        log_prefix = f"[FSAppStorage:GetVersion:{app_id}] "

        storage_version_path = self._get_preview_version_path(user_id, app_id)

        if not storage_version_path.exists():
            logger.debug(f"{log_prefix}VERSION file not found in storage")
            return None

        def _read():
            with open(storage_version_path) as f:
                return json.load(f)

        try:
            version_data = await asyncio.to_thread(_read)
            logger.debug(f"{log_prefix}Read VERSION: {version_data.get('version')}")
            return version_data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"{log_prefix}Failed to read VERSION: {e}")
            return None
