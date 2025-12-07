"""
Local filesystem implementation of workspace service.

Manages workspace directories on the local filesystem with metadata
stored in .workspace-metadata.json files within each workspace.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_workspace_service import BaseWorkspaceService

log = logging.getLogger(__name__)


class LocalFilesystemWorkspaceService(BaseWorkspaceService):
    """
    Workspace service backed by local filesystem.

    Directory structure:
        {base_path}/
            {user_id}/
                sessions/{workspace_id}/
                    .workspace-metadata.json
                    ... user files ...
                apps/{workspace_id}/
                    .workspace-metadata.json
                    ... user files ...
    """

    METADATA_FILENAME = ".workspace-metadata.json"

    def __init__(self, base_path: str = "/claude-workspaces"):
        """
        Initialize the local filesystem workspace service.

        Args:
            base_path: Root directory for all workspaces
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Initialized LocalFilesystemWorkspaceService at {self.base_path}")

    def _get_workspace_dir(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> Path:
        """Get workspace directory path."""
        type_dir = "sessions" if workspace_type == "session" else "apps"
        return self.base_path / user_id / type_dir / workspace_id

    def _get_metadata_file(self, workspace_dir: Path) -> Path:
        """Get metadata file path."""
        return workspace_dir / self.METADATA_FILENAME

    async def create_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Create workspace directory."""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)

        if workspace_dir.exists():
            raise ValueError(
                f"Workspace already exists: {workspace_id} "
                f"(type: {workspace_type}, user: {user_id})"
            )

        # Create directory
        workspace_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"Created workspace directory: {workspace_dir}")

        # Store metadata
        metadata_file = self._get_metadata_file(workspace_dir)
        workspace_metadata = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "workspace_type": workspace_type,
            "created_at": datetime.now().timestamp(),
            "updated_at": datetime.now().timestamp(),
            **(metadata or {}),
        }
        metadata_file.write_text(json.dumps(workspace_metadata, indent=2))
        log.debug(f"Wrote metadata to {metadata_file}")

        return workspace_dir

    async def get_workspace_path(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> Optional[Path]:
        """Get workspace path if it exists."""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        return workspace_dir if workspace_dir.exists() else None

    async def list_workspaces(
        self,
        user_id: str,
        workspace_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List user's workspaces."""
        workspaces = []
        user_dir = self.base_path / user_id

        if not user_dir.exists():
            return []

        types_to_scan = (
            ["sessions", "apps"]
            if not workspace_type
            else ["sessions" if workspace_type == "session" else "apps"]
        )

        for type_dir in types_to_scan:
            type_path = user_dir / type_dir
            if not type_path.exists():
                continue

            for workspace_dir in type_path.iterdir():
                if not workspace_dir.is_dir():
                    continue

                metadata_file = self._get_metadata_file(workspace_dir)
                if metadata_file.exists():
                    try:
                        metadata = json.loads(metadata_file.read_text())
                    except (json.JSONDecodeError, OSError) as e:
                        log.warning(f"Failed to read metadata for {workspace_dir}: {e}")
                        metadata = {
                            "workspace_id": workspace_dir.name,
                            "workspace_type": type_dir.rstrip("s"),
                        }
                else:
                    metadata = {
                        "workspace_id": workspace_dir.name,
                        "workspace_type": type_dir.rstrip("s"),
                    }

                metadata["path"] = workspace_dir
                workspaces.append(metadata)

        return workspaces

    async def delete_workspace(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> bool:
        """Delete workspace."""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)

        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
            log.info(f"Deleted workspace: {workspace_dir}")
            return True

        log.debug(f"Workspace not found for deletion: {workspace_dir}")
        return False

    async def get_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Get workspace metadata."""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        metadata_file = self._get_metadata_file(workspace_dir)

        if metadata_file.exists():
            try:
                return json.loads(metadata_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"Failed to read metadata from {metadata_file}: {e}")
                return None

        return None

    async def update_metadata(
        self,
        workspace_id: str,
        user_id: str,
        workspace_type: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Update workspace metadata."""
        workspace_dir = self._get_workspace_dir(workspace_id, user_id, workspace_type)
        metadata_file = self._get_metadata_file(workspace_dir)

        if not workspace_dir.exists():
            raise ValueError(
                f"Workspace does not exist: {workspace_id} "
                f"(type: {workspace_type}, user: {user_id})"
            )

        existing = {}
        if metadata_file.exists():
            try:
                existing = json.loads(metadata_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Failed to read existing metadata, starting fresh: {e}")

        existing.update(metadata)
        existing["updated_at"] = datetime.now().timestamp()

        metadata_file.write_text(json.dumps(existing, indent=2))
        log.debug(f"Updated metadata at {metadata_file}")
