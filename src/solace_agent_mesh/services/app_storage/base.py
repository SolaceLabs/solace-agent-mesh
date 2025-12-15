"""
Abstract base class for App Storage Service.

Defines the interface for storing and serving built app dist/ files.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class AppStorageService(ABC):
    """
    Abstract interface for serving built apps.

    Directory structure:
    {storage_root}/{user_id}/{app_id}/
    ├── latest/           # Current workspace build (preview)
    │   ├── dist/         # Built files from workspace
    │   └── VERSION       # Version metadata
    └── versions/         # Deployed version snapshots
        ├── 0.0.1/
        ├── 0.0.2/
        └── ...

    This service handles storage and retrieval of built app files.
    It's separate from workspace storage because:
    1. dist/ needs to be served directly by the Gateway
    2. dist/ is regenerated on every build (not incrementally edited)
    3. Different caching/serving requirements than source files
    """

    @abstractmethod
    async def sync_dist(
        self,
        user_id: str,
        app_id: str,
        dist_path: Path,
    ) -> None:
        """
        Sync dist/ directory to latest/ storage after build.

        This uploads all files from the local dist/ directory to
        {storage}/{user_id}/{app_id}/latest/dist/, replacing any existing files.

        Args:
            user_id: User identifier
            app_id: App identifier
            dist_path: Local path to dist/ directory
        """
        pass

    @abstractmethod
    async def get_file(
        self,
        user_id: str,
        app_id: str,
        path: str,
    ) -> Optional[bytes]:
        """
        Get a file from the app's latest/dist/ for serving preview.

        Args:
            user_id: User identifier
            app_id: App identifier
            path: Relative path within dist/ (e.g., "index.html", "assets/main.js")

        Returns:
            File contents as bytes, or None if not found
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        user_id: str,
        app_id: str,
        prefix: str = "",
    ) -> list[str]:
        """
        List files in the app's latest/dist/.

        Args:
            user_id: User identifier
            app_id: App identifier
            prefix: Optional prefix to filter files

        Returns:
            List of relative file paths
        """
        pass

    @abstractmethod
    async def delete_app(
        self,
        user_id: str,
        app_id: str,
    ) -> None:
        """
        Delete all files for an app.

        Args:
            user_id: User identifier
            app_id: App identifier
        """
        pass

    @abstractmethod
    async def app_exists(
        self,
        user_id: str,
        app_id: str,
    ) -> bool:
        """
        Check if an app has any stored preview files in latest/dist/.

        Args:
            user_id: User identifier
            app_id: App identifier

        Returns:
            True if the app has stored preview files
        """
        pass

    @abstractmethod
    async def deploy_version(
        self,
        user_id: str,
        app_id: str,
        version: str,
        source_path: Path,
    ) -> None:
        """
        Deploy a specific version from local dist/ to versioned storage.

        Copies files from source_path to a versioned location:
        {user_id}/{app_id}/versions/{version}/

        Args:
            user_id: User identifier
            app_id: App identifier
            version: Version string (e.g., "1.2.3")
            source_path: Local path to dist/ directory to deploy
        """
        pass

    @abstractmethod
    async def get_version_file(
        self,
        user_id: str,
        app_id: str,
        version: str,
        path: str,
    ) -> Optional[bytes]:
        """
        Get a file from a specific deployed version.

        Args:
            user_id: User identifier
            app_id: App identifier
            version: Version string (e.g., "1.2.3")
            path: Relative path within the version (e.g., "index.html")

        Returns:
            File contents as bytes, or None if not found
        """
        pass

    @abstractmethod
    async def version_exists(
        self,
        user_id: str,
        app_id: str,
        version: str,
    ) -> bool:
        """
        Check if a specific version exists in storage.

        Args:
            user_id: User identifier
            app_id: App identifier
            version: Version string (e.g., "1.2.3")

        Returns:
            True if the version exists
        """
        pass

    @abstractmethod
    async def list_versions(
        self,
        user_id: str,
        app_id: str,
    ) -> list[str]:
        """
        List all deployed versions for an app.

        Args:
            user_id: User identifier
            app_id: App identifier

        Returns:
            List of version strings, sorted newest first
        """
        pass

    @abstractmethod
    async def sync_preview_metadata(
        self,
        user_id: str,
        app_id: str,
        version_file_path: Path,
    ) -> None:
        """
        Sync the VERSION file to latest/ storage.

        This should be called after sync_dist to copy the VERSION file to
        {storage}/{user_id}/{app_id}/latest/VERSION so that preview version
        info is available even without workspace.

        Args:
            user_id: User identifier
            app_id: App identifier
            version_file_path: Local path to VERSION file
        """
        pass

    @abstractmethod
    async def get_preview_version(
        self,
        user_id: str,
        app_id: str,
    ) -> Optional[dict]:
        """
        Get the preview VERSION file contents from latest/ storage.

        Reads {storage}/{user_id}/{app_id}/latest/VERSION.

        Args:
            user_id: User identifier
            app_id: App identifier

        Returns:
            Parsed VERSION file contents as dict, or None if not found
        """
        pass
