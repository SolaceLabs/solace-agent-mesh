"""
Abstract base class for workspace management services.

This module defines the interface for workspace services that manage
filesystem directories for persistent workspaces. All implementations
must provide real filesystem paths that can be volume-mounted into
containers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseWorkspaceService(ABC):
    """
    Abstract service for managing workspace directories.

    CRITICAL: All implementations must provide real filesystem paths
    that can be volume-mounted into containers. The workspace service
    does not abstract filesystem operations - it only manages the
    lifecycle and metadata of workspace directories.

    This is similar to how SQLAlchemy abstracts database access, but
    with a key difference: it returns real filesystem Paths, not
    abstracted file operations.
    """

    @abstractmethod
    async def create_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,  # "session" | "app"
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Create a new workspace directory.

        Args:
            workspace_id: Unique identifier for the workspace
            user_id: User who owns the workspace
            workspace_type: Type of workspace ("session" for temporary,
                          "app" for persistent)
            metadata: Optional metadata to store with the workspace

        Returns:
            Path object pointing to workspace directory on host filesystem.
            This path MUST be mountable into containers.

        Raises:
            ValueError: If workspace already exists
            OSError: If directory creation fails
        """
        pass

    @abstractmethod
    async def get_workspace_path(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> Optional[Path]:
        """
        Get filesystem path for existing workspace.

        Args:
            workspace_id: Unique identifier for the workspace
            user_id: User who owns the workspace
            workspace_type: Type of workspace ("session" | "app")

        Returns:
            Path object if workspace exists, None otherwise.
            Path MUST be mountable into containers.
        """
        pass

    @abstractmethod
    async def list_workspaces(
        self,
        user_id: str,
        workspace_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List user's workspaces with metadata.

        Args:
            user_id: User whose workspaces to list
            workspace_type: Optional filter for workspace type

        Returns:
            List of workspace info dicts containing:
                - workspace_id: str
                - path: Path (mountable filesystem path)
                - workspace_type: str
                - created_at: float (epoch timestamp)
                - metadata: Dict (any additional metadata)
        """
        pass

    @abstractmethod
    async def delete_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> bool:
        """
        Delete workspace directory and metadata.

        Args:
            workspace_id: Unique identifier for the workspace
            user_id: User who owns the workspace
            workspace_type: Type of workspace ("session" | "app")

        Returns:
            True if workspace was deleted, False if it didn't exist
        """
        pass

    @abstractmethod
    async def get_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get workspace metadata.

        Args:
            workspace_id: Unique identifier for the workspace
            user_id: User who owns the workspace
            workspace_type: Type of workspace ("session" | "app")

        Returns:
            Metadata dict if workspace exists, None otherwise
        """
        pass

    @abstractmethod
    async def update_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Update workspace metadata.

        Args:
            workspace_id: Unique identifier for the workspace
            user_id: User who owns the workspace
            workspace_type: Type of workspace ("session" | "app")
            metadata: Metadata updates to apply (merged with existing)

        Raises:
            ValueError: If workspace doesn't exist
        """
        pass
