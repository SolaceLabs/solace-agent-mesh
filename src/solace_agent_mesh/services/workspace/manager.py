"""
Workspace Manager - Handles workspace lifecycle for Claude Code execution.

Responsibilities:
1. Initialize: Download tarball and extract to local path
2. Finalize: Create tarball, upload, sync dist/ to app storage
3. Cleanup: Delete ephemeral workspaces

Note: Template initialization and npm install are handled by the container's
init script, not here. WorkspaceManager runs on the host and can't access
the template inside the container image.
"""

import asyncio
import io
import logging
import os
import tarfile
from pathlib import Path
from typing import Optional, Set

from ..app_storage.base import AppStorageService
from .types import WorkspaceConfig, WorkspaceType

logger = logging.getLogger(__name__)

# Files/directories to exclude from workspace tarball
TARBALL_EXCLUDES: Set[str] = {
    "node_modules",
    "dist",
    ".git",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "*.pyc",
    "*.pyo",
}


class WorkspaceManager:
    """
    Manages workspace lifecycle for Claude Code execution.

    Handles:
    - Downloading workspace tarballs from artifact service
    - Type-specific initialization (APP: template copy, npm install)
    - Type-specific finalization (APP: sync dist/ to app storage)
    - Uploading workspace tarballs
    - Cleanup of ephemeral workspaces
    """

    def __init__(
        self,
        artifact_service,  # BaseArtifactService - avoid circular import
        app_storage_service: Optional[AppStorageService] = None,
    ):
        """
        Initialize WorkspaceManager.

        Args:
            artifact_service: Artifact service for workspace tarball storage
            app_storage_service: App storage service for dist/ files (required for APP type)
        """
        self.artifact_service = artifact_service
        self.app_storage_service = app_storage_service

    async def initialize(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """
        Prepare workspace before Claude Code runs.

        1. Download existing workspace tarball (if exists)
        2. Extract to local_path
        3. Run type-specific initialization

        Args:
            config: Workspace configuration
            local_path: Local directory for workspace
        """
        log_prefix = f"[WorkspaceManager:Init:{config.workspace_id}] "
        logger.info(f"{log_prefix}Initializing {config.type.value} workspace")

        # Ensure local path exists
        local_path.mkdir(parents=True, exist_ok=True)

        # Try to download existing workspace tarball
        tarball = await self._load_workspace_tarball(config.user_id, config.workspace_id)

        if tarball:
            logger.info(f"{log_prefix}Found existing workspace tarball, extracting")
            await self._extract_tarball(tarball, local_path)
            config.is_new_workspace = False
        elif any(local_path.iterdir()):
            # Local path has content but no tarball - this is an existing workspace
            # that was created before WorkspaceManager was enabled. Don't overwrite it.
            logger.info(f"{log_prefix}No tarball but local workspace exists, preserving existing files")
            config.is_new_workspace = False
        else:
            logger.info(f"{log_prefix}No existing workspace found, will initialize new")
            config.is_new_workspace = True

        # Type-specific initialization
        if config.type == WorkspaceType.APP:
            await self._init_app_workspace(config, local_path)
        elif config.type == WorkspaceType.REPO:
            await self._init_repo_workspace(config, local_path)
        elif config.type == WorkspaceType.GENERIC:
            pass  # No special initialization

        logger.info(f"{log_prefix}Initialization complete")

    async def finalize(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """
        Process workspace after Claude Code completes.

        1. Create tarball of source files (excluding node_modules, dist, etc.)
        2. Upload tarball to artifact service
        3. Run type-specific finalization (e.g., sync dist/)

        Args:
            config: Workspace configuration
            local_path: Local directory containing workspace
        """
        log_prefix = f"[WorkspaceManager:Finalize:{config.workspace_id}] "
        logger.info(f"{log_prefix}Finalizing {config.type.value} workspace")

        # Create and upload workspace tarball (source files only)
        tarball = await self._create_tarball(local_path)
        await self._save_workspace_tarball(config.user_id, config.workspace_id, tarball)
        logger.info(f"{log_prefix}Uploaded workspace tarball ({len(tarball)} bytes)")

        # Type-specific finalization
        if config.type == WorkspaceType.APP:
            await self._finalize_app_workspace(config, local_path)
        elif config.type == WorkspaceType.REPO:
            await self._finalize_repo_workspace(config, local_path)

        logger.info(f"{log_prefix}Finalization complete")

    async def cleanup(
        self,
        config: WorkspaceConfig,
    ) -> None:
        """
        Remove workspace (for ephemeral workspaces).

        Args:
            config: Workspace configuration
        """
        if not config.ephemeral:
            return

        log_prefix = f"[WorkspaceManager:Cleanup:{config.workspace_id}] "
        logger.info(f"{log_prefix}Cleaning up ephemeral workspace")

        await self._delete_workspace(config.user_id, config.workspace_id)

        # Also delete from app storage if APP type
        if config.type == WorkspaceType.APP and self.app_storage_service:
            await self.app_storage_service.delete_app(config.user_id, config.workspace_id)

        logger.info(f"{log_prefix}Cleanup complete")

    # ========== Type-specific initialization ==========

    async def _init_app_workspace(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """
        Initialize APP workspace from tarball.

        Note: Template copying and npm install are handled by the container's
        init script (initialize_workspace_if_needed), not here. The template
        lives inside the container image and isn't accessible from the host
        where WorkspaceManager runs.

        WorkspaceManager only handles tarball-based persistence:
        - Extract existing tarball (done in initialize() before this)
        - Create tarball after execution (done in finalize())
        - Sync dist/ to app storage (done in finalize())
        """
        log_prefix = f"[WorkspaceManager:InitApp:{config.workspace_id}] "
        logger.debug(f"{log_prefix}APP workspace init complete (template handled by container)")

    async def _init_repo_workspace(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """Initialize REPO workspace: git clone (future)."""
        log_prefix = f"[WorkspaceManager:InitRepo:{config.workspace_id}] "

        if not config.is_new_workspace:
            # Existing workspace, just do git pull
            logger.info(f"{log_prefix}Existing repo workspace, skipping clone")
            return

        repo_config = config.repo_config
        if not repo_config or not repo_config.repo_url:
            logger.warning(f"{log_prefix}No repo_url configured, skipping clone")
            return

        logger.info(f"{log_prefix}Cloning {repo_config.repo_url} branch {repo_config.branch}")

        proc = await asyncio.create_subprocess_exec(
            "git", "clone",
            "--branch", repo_config.branch,
            "--single-branch",
            "--depth", "1",
            repo_config.repo_url,
            str(local_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"{log_prefix}Git clone failed: {stderr.decode()}")
            raise RuntimeError(f"Git clone failed: {stderr.decode()}")

        logger.info(f"{log_prefix}Clone complete")

    # ========== Type-specific finalization ==========

    async def _finalize_app_workspace(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """Finalize APP workspace: sync dist/ to app storage."""
        log_prefix = f"[WorkspaceManager:FinalizeApp:{config.workspace_id}] "

        if not config.app_config or not config.app_config.sync_dist:
            return

        if not self.app_storage_service:
            logger.warning(f"{log_prefix}No app_storage_service configured, skipping dist sync")
            return

        dist_path = local_path / "dist"
        if not dist_path.exists():
            logger.debug(f"{log_prefix}No dist/ directory, skipping sync")
            return

        logger.info(f"{log_prefix}Syncing dist/ to app storage")
        await self.app_storage_service.sync_dist(
            config.user_id,
            config.workspace_id,
            dist_path,
        )

        # Also sync VERSION file so preview version info is available without workspace
        version_file = local_path / "VERSION"
        if version_file.exists():
            logger.info(f"{log_prefix}Syncing VERSION file to app storage")
            await self.app_storage_service.sync_preview_metadata(
                config.user_id,
                config.workspace_id,
                version_file,
            )

    async def _finalize_repo_workspace(
        self,
        config: WorkspaceConfig,
        local_path: Path,
    ) -> None:
        """Finalize REPO workspace (git operations handled by Claude Code)."""
        # Git commit/push/PR creation is handled by Claude Code itself
        pass

    # ========== Tarball operations ==========

    async def _create_tarball(self, local_path: Path) -> bytes:
        """Create tarball of workspace source files."""
        def _create():
            buffer = io.BytesIO()

            def exclude_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
                name = tarinfo.name
                # Check against excludes
                for exclude in TARBALL_EXCLUDES:
                    if exclude.startswith("*"):
                        if name.endswith(exclude[1:]):
                            return None
                    elif exclude in name.split(os.sep):
                        return None
                return tarinfo

            with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
                for item in local_path.iterdir():
                    tar.add(
                        item,
                        arcname=item.name,
                        filter=exclude_filter,
                    )

            return buffer.getvalue()

        return await asyncio.to_thread(_create)

    async def _extract_tarball(self, tarball: bytes, local_path: Path) -> None:
        """Extract tarball to local path."""
        def _extract():
            buffer = io.BytesIO(tarball)
            with tarfile.open(fileobj=buffer, mode="r:gz") as tar:
                tar.extractall(local_path, filter="data")

        await asyncio.to_thread(_extract)

    # ========== Artifact service operations ==========

    async def _load_workspace_tarball(
        self,
        user_id: str,
        workspace_id: str,
    ) -> Optional[bytes]:
        """Load workspace tarball from artifact service."""
        try:
            artifact = await self.artifact_service.load_artifact(
                app_name="workspaces",
                user_id=user_id,
                session_id=workspace_id,
                filename="workspace.tar.gz",
            )
            if artifact and artifact.inline_data:
                return artifact.inline_data.data
            return None
        except Exception as e:
            logger.warning(f"Failed to load workspace tarball: {e}")
            return None

    async def _save_workspace_tarball(
        self,
        user_id: str,
        workspace_id: str,
        tarball: bytes,
    ) -> None:
        """Save workspace tarball to artifact service."""
        from google.genai import types as adk_types

        artifact = adk_types.Part.from_bytes(
            data=tarball,
            mime_type="application/gzip",
        )

        await self.artifact_service.save_artifact(
            app_name="workspaces",
            user_id=user_id,
            session_id=workspace_id,
            filename="workspace.tar.gz",
            artifact=artifact,
        )

    async def _delete_workspace(
        self,
        user_id: str,
        workspace_id: str,
    ) -> None:
        """Delete workspace from artifact service."""
        try:
            await self.artifact_service.delete_artifact(
                app_name="workspaces",
                user_id=user_id,
                session_id=workspace_id,
                filename="workspace.tar.gz",
            )
        except Exception as e:
            logger.warning(f"Failed to delete workspace: {e}")
