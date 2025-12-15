"""
Unit tests for WorkspaceManager and workspace types.
"""

import asyncio
import json
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.solace_agent_mesh.services.workspace import (
    WorkspaceConfig,
    WorkspaceManager,
    WorkspaceType,
    AppWorkspaceConfig,
    RepoWorkspaceConfig,
)


class TestWorkspaceType:
    """Tests for WorkspaceType enum."""

    def test_workspace_types_exist(self):
        """Verify all expected workspace types exist."""
        assert WorkspaceType.APP.value == "app"
        assert WorkspaceType.REPO.value == "repo"
        assert WorkspaceType.GENERIC.value == "generic"


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig dataclass."""

    def test_app_config_auto_created(self):
        """Test that AppWorkspaceConfig is auto-created for APP type."""
        config = WorkspaceConfig(
            type=WorkspaceType.APP,
            user_id="user1",
            workspace_id="app1",
            workspace_name="My App",
        )
        assert config.app_config is not None
        assert config.app_config.sync_dist is True

    def test_repo_config_required(self):
        """Test that repo_config is required for REPO type."""
        with pytest.raises(ValueError, match="repo_config is required"):
            WorkspaceConfig(
                type=WorkspaceType.REPO,
                user_id="user1",
                workspace_id="repo1",
                workspace_name="My Repo",
            )

    def test_repo_config_valid(self):
        """Test that REPO type with repo_config is valid."""
        config = WorkspaceConfig(
            type=WorkspaceType.REPO,
            user_id="user1",
            workspace_id="repo1",
            workspace_name="My Repo",
            repo_config=RepoWorkspaceConfig(repo_url="https://github.com/test/repo"),
        )
        assert config.repo_config is not None
        assert config.repo_config.repo_url == "https://github.com/test/repo"

    def test_generic_config_valid(self):
        """Test that GENERIC type doesn't require extra config."""
        config = WorkspaceConfig(
            type=WorkspaceType.GENERIC,
            user_id="user1",
            workspace_id="workspace1",
            workspace_name="Generic Workspace",
        )
        assert config.app_config is None
        assert config.repo_config is None


class TestWorkspaceManager:
    """Tests for WorkspaceManager."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Create a mock artifact service."""
        service = MagicMock()
        service.load_artifact = AsyncMock(return_value=None)
        service.save_artifact = AsyncMock(return_value=0)
        service.delete_artifact = AsyncMock()
        return service

    @pytest.fixture
    def mock_app_storage_service(self):
        """Create a mock app storage service."""
        service = MagicMock()
        service.sync_dist = AsyncMock()
        service.delete_app = AsyncMock()
        return service

    @pytest.fixture
    def workspace_manager(self, mock_artifact_service, mock_app_storage_service):
        """Create a WorkspaceManager instance."""
        return WorkspaceManager(
            artifact_service=mock_artifact_service,
            app_storage_service=mock_app_storage_service,
        )

    @pytest.mark.asyncio
    async def test_initialize_new_workspace(self, workspace_manager, mock_artifact_service):
        """Test initializing a new workspace (no existing tarball)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()

            config = WorkspaceConfig(
                type=WorkspaceType.GENERIC,
                user_id="user1",
                workspace_id="ws1",
                workspace_name="Test Workspace",
            )

            await workspace_manager.initialize(config, local_path)

            # Should have tried to load tarball
            mock_artifact_service.load_artifact.assert_called_once()
            # Should be marked as new workspace
            assert config.is_new_workspace is True

    @pytest.mark.asyncio
    async def test_initialize_existing_workspace(self, workspace_manager, mock_artifact_service):
        """Test initializing an existing workspace (tarball exists)."""
        # Create a mock tarball
        tarball_data = BytesIO()
        with tarfile.open(fileobj=tarball_data, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="test.txt")
            content = b"test content"
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
        tarball_bytes = tarball_data.getvalue()

        # Mock artifact with tarball data
        mock_artifact = MagicMock()
        mock_artifact.inline_data = MagicMock()
        mock_artifact.inline_data.data = tarball_bytes
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_artifact)

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()

            config = WorkspaceConfig(
                type=WorkspaceType.GENERIC,
                user_id="user1",
                workspace_id="ws1",
                workspace_name="Test Workspace",
            )

            await workspace_manager.initialize(config, local_path)

            # Should not be marked as new workspace
            assert config.is_new_workspace is False
            # Should have extracted the tarball
            assert (local_path / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_finalize_creates_tarball(self, workspace_manager, mock_artifact_service):
        """Test that finalize creates and uploads a tarball."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            (local_path / "src").mkdir()
            (local_path / "src" / "main.py").write_text("print('hello')")

            config = WorkspaceConfig(
                type=WorkspaceType.GENERIC,
                user_id="user1",
                workspace_id="ws1",
                workspace_name="Test Workspace",
            )

            await workspace_manager.finalize(config, local_path)

            # Should have saved the tarball
            mock_artifact_service.save_artifact.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_syncs_dist_for_app(
        self, workspace_manager, mock_artifact_service, mock_app_storage_service
    ):
        """Test that finalize syncs dist/ for APP type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            dist_path = local_path / "dist"
            dist_path.mkdir()
            (dist_path / "index.html").write_text("<html></html>")

            config = WorkspaceConfig(
                type=WorkspaceType.APP,
                user_id="user1",
                workspace_id="app1",
                workspace_name="Test App",
                app_config=AppWorkspaceConfig(sync_dist=True),
            )

            await workspace_manager.finalize(config, local_path)

            # Should have synced dist
            mock_app_storage_service.sync_dist.assert_called_once_with(
                "user1", "app1", dist_path
            )

    @pytest.mark.asyncio
    async def test_finalize_skips_dist_sync_when_disabled(
        self, workspace_manager, mock_artifact_service, mock_app_storage_service
    ):
        """Test that finalize skips dist sync when sync_dist is False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            dist_path = local_path / "dist"
            dist_path.mkdir()

            config = WorkspaceConfig(
                type=WorkspaceType.APP,
                user_id="user1",
                workspace_id="app1",
                workspace_name="Test App",
                app_config=AppWorkspaceConfig(sync_dist=False),
            )

            await workspace_manager.finalize(config, local_path)

            # Should not have synced dist
            mock_app_storage_service.sync_dist.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_deletes_ephemeral(
        self, workspace_manager, mock_artifact_service, mock_app_storage_service
    ):
        """Test that cleanup deletes ephemeral workspaces."""
        config = WorkspaceConfig(
            type=WorkspaceType.APP,
            user_id="user1",
            workspace_id="app1",
            workspace_name="Ephemeral App",
            ephemeral=True,
        )

        await workspace_manager.cleanup(config)

        # Should have deleted from artifact service
        mock_artifact_service.delete_artifact.assert_called_once()
        # Should have deleted from app storage
        mock_app_storage_service.delete_app.assert_called_once_with("user1", "app1")

    @pytest.mark.asyncio
    async def test_cleanup_skips_non_ephemeral(
        self, workspace_manager, mock_artifact_service, mock_app_storage_service
    ):
        """Test that cleanup skips non-ephemeral workspaces."""
        config = WorkspaceConfig(
            type=WorkspaceType.APP,
            user_id="user1",
            workspace_id="app1",
            workspace_name="Persistent App",
            ephemeral=False,
        )

        await workspace_manager.cleanup(config)

        # Should not have deleted anything
        mock_artifact_service.delete_artifact.assert_not_called()
        mock_app_storage_service.delete_app.assert_not_called()


class TestTarballExclusions:
    """Tests for tarball exclusion rules."""

    @pytest.fixture
    def workspace_manager(self):
        """Create a WorkspaceManager with mock services."""
        mock_artifact = MagicMock()
        mock_artifact.save_artifact = AsyncMock(return_value=0)
        return WorkspaceManager(artifact_service=mock_artifact)

    @pytest.mark.asyncio
    async def test_excludes_node_modules(self, workspace_manager):
        """Test that node_modules is excluded from tarball."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            (local_path / "src").mkdir()
            (local_path / "src" / "main.js").write_text("console.log('hello')")
            (local_path / "node_modules").mkdir()
            (local_path / "node_modules" / "package").mkdir()
            (local_path / "node_modules" / "package" / "index.js").write_text("")

            # Create tarball
            tarball = await workspace_manager._create_tarball(local_path)

            # Extract and verify node_modules is excluded
            with tarfile.open(fileobj=BytesIO(tarball), mode="r:gz") as tar:
                names = tar.getnames()
                assert "src/main.js" in names
                assert not any("node_modules" in name for name in names)

    @pytest.mark.asyncio
    async def test_excludes_dist(self, workspace_manager):
        """Test that dist/ is excluded from tarball."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            (local_path / "src").mkdir()
            (local_path / "src" / "main.js").write_text("console.log('hello')")
            (local_path / "dist").mkdir()
            (local_path / "dist" / "bundle.js").write_text("")

            # Create tarball
            tarball = await workspace_manager._create_tarball(local_path)

            # Extract and verify dist is excluded
            with tarfile.open(fileobj=BytesIO(tarball), mode="r:gz") as tar:
                names = tar.getnames()
                assert "src/main.js" in names
                assert not any("dist" in name for name in names)

    @pytest.mark.asyncio
    async def test_excludes_git(self, workspace_manager):
        """Test that .git is excluded from tarball."""
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / "workspace"
            local_path.mkdir()
            (local_path / "src").mkdir()
            (local_path / "src" / "main.js").write_text("console.log('hello')")
            (local_path / ".git").mkdir()
            (local_path / ".git" / "config").write_text("")

            # Create tarball
            tarball = await workspace_manager._create_tarball(local_path)

            # Extract and verify .git is excluded
            with tarfile.open(fileobj=BytesIO(tarball), mode="r:gz") as tar:
                names = tar.getnames()
                assert "src/main.js" in names
                assert not any(".git" in name for name in names)
