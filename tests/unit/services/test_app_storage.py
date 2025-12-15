"""
Unit tests for AppStorageService implementations.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.solace_agent_mesh.services.app_storage import (
    AppStorageService,
    FilesystemAppStorageService,
)


class TestFilesystemAppStorageService:
    """Tests for FilesystemAppStorageService."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage_service(self, temp_dir):
        """Create a FilesystemAppStorageService instance."""
        return FilesystemAppStorageService(base_path=temp_dir)

    @pytest.mark.asyncio
    async def test_sync_dist_copies_files(self, storage_service, temp_dir):
        """Test that sync_dist copies files from source to storage."""
        # Setup: create source dist directory with files
        source_dist = Path(temp_dir) / "source_dist"
        source_dist.mkdir()
        (source_dist / "index.html").write_text("<html>test</html>")
        (source_dist / "assets").mkdir()
        (source_dist / "assets" / "main.js").write_text("console.log('test');")

        # Sync dist
        await storage_service.sync_dist("user1", "app1", source_dist)

        # Verify files were copied
        storage_path = Path(temp_dir) / "user1" / "app1" / "dist"
        assert storage_path.exists()
        assert (storage_path / "index.html").exists()
        assert (storage_path / "assets" / "main.js").exists()

    @pytest.mark.asyncio
    async def test_get_file_returns_content(self, storage_service, temp_dir):
        """Test that get_file returns file content."""
        # Setup: create storage structure
        storage_path = Path(temp_dir) / "user1" / "app1" / "dist"
        storage_path.mkdir(parents=True)
        (storage_path / "index.html").write_bytes(b"<html>content</html>")

        # Get file
        content = await storage_service.get_file("user1", "app1", "index.html")

        assert content == b"<html>content</html>"

    @pytest.mark.asyncio
    async def test_get_file_returns_none_for_missing(self, storage_service):
        """Test that get_file returns None for missing files."""
        content = await storage_service.get_file("user1", "nonexistent", "file.txt")
        assert content is None

    @pytest.mark.asyncio
    async def test_get_file_prevents_traversal(self, storage_service, temp_dir):
        """Test that get_file prevents directory traversal."""
        # Setup: create a file outside the storage path
        secret_file = Path(temp_dir) / "secret.txt"
        secret_file.write_text("secret data")

        # Also create the app storage path
        storage_path = Path(temp_dir) / "user1" / "app1" / "dist"
        storage_path.mkdir(parents=True)

        # Try to access file outside storage (should return None)
        content = await storage_service.get_file("user1", "app1", "../../../secret.txt")
        assert content is None

    @pytest.mark.asyncio
    async def test_list_files_returns_files(self, storage_service, temp_dir):
        """Test that list_files returns all files."""
        # Setup: create storage structure
        storage_path = Path(temp_dir) / "user1" / "app1" / "dist"
        storage_path.mkdir(parents=True)
        (storage_path / "index.html").write_text("")
        (storage_path / "assets").mkdir()
        (storage_path / "assets" / "main.js").write_text("")

        # List files
        files = await storage_service.list_files("user1", "app1")

        assert "index.html" in files
        assert "assets/main.js" in files

    @pytest.mark.asyncio
    async def test_delete_app_removes_directory(self, storage_service, temp_dir):
        """Test that delete_app removes the app directory."""
        # Setup: create storage structure
        app_path = Path(temp_dir) / "user1" / "app1"
        dist_path = app_path / "dist"
        dist_path.mkdir(parents=True)
        (dist_path / "index.html").write_text("")

        # Delete app
        await storage_service.delete_app("user1", "app1")

        assert not app_path.exists()

    @pytest.mark.asyncio
    async def test_app_exists_returns_true(self, storage_service, temp_dir):
        """Test that app_exists returns True when app has files."""
        # Setup: create storage structure
        storage_path = Path(temp_dir) / "user1" / "app1" / "dist"
        storage_path.mkdir(parents=True)
        (storage_path / "index.html").write_text("")

        result = await storage_service.app_exists("user1", "app1")
        assert result is True

    @pytest.mark.asyncio
    async def test_app_exists_returns_false(self, storage_service):
        """Test that app_exists returns False when app doesn't exist."""
        result = await storage_service.app_exists("user1", "nonexistent")
        assert result is False


class TestAppStorageServiceInterface:
    """Tests to verify the abstract interface contract."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Verify that AppStorageService cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AppStorageService()

    def test_filesystem_implements_interface(self, tmp_path):
        """Verify FilesystemAppStorageService implements the interface."""
        service = FilesystemAppStorageService(base_path=str(tmp_path))
        assert isinstance(service, AppStorageService)
        assert hasattr(service, "sync_dist")
        assert hasattr(service, "get_file")
        assert hasattr(service, "list_files")
        assert hasattr(service, "delete_app")
        assert hasattr(service, "app_exists")
