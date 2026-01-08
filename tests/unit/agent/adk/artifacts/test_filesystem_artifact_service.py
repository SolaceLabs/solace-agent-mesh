"""
Unit tests for src/solace_agent_mesh/agent/adk/artifacts/filesystem_artifact_service.py

Tests the FilesystemArtifactService implementation including:
- Initialization and directory creation
- Artifact saving with versioning
- Artifact loading (latest and specific versions)
- Artifact listing and key management
- Artifact deletion
- Version management
- Unicode filename normalization
- User namespace handling
- Error handling and edge cases
"""

import json
import os
import shutil
import tempfile
import unicodedata
from unittest.mock import Mock, patch
import pytest

from google.genai import types as adk_types
from src.solace_agent_mesh.agent.adk.artifacts.filesystem_artifact_service import (
    FilesystemArtifactService,
    METADATA_FILE_SUFFIX
)


@pytest.fixture
def temp_base_path():
    """Create a temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def artifact_service(temp_base_path):
    """Create a FilesystemArtifactService instance for testing"""
    return FilesystemArtifactService(temp_base_path)


@pytest.fixture
def sample_artifact():
    """Create a sample artifact for testing"""
    data = b"Hello, World!"
    mime_type = "text/plain"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


@pytest.fixture
def sample_binary_artifact():
    """Create a sample binary artifact for testing"""
    data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    mime_type = "image/png"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


class TestFilesystemArtifactServiceInit:
    """Tests for FilesystemArtifactService initialization"""

    def test_init_with_valid_path(self, temp_base_path):
        """Test initialization with valid base path"""
        service = FilesystemArtifactService(temp_base_path)
        assert service.base_path == os.path.abspath(temp_base_path)
        assert os.path.exists(service.base_path)

    def test_init_creates_directory(self):
        """Test that initialization creates the base directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = os.path.join(temp_dir, "new_artifacts")
            service = FilesystemArtifactService(base_path)
            assert os.path.exists(service.base_path)

    def test_init_with_empty_path(self):
        """Test initialization with empty base path raises ValueError"""
        with pytest.raises(ValueError, match="base_path cannot be empty"):
            FilesystemArtifactService("")

    def test_init_with_none_path(self):
        """Test initialization with None base path raises ValueError"""
        with pytest.raises(ValueError, match="base_path cannot be empty"):
            FilesystemArtifactService(None)

    @patch('os.makedirs')
    def test_init_with_permission_error(self, mock_makedirs):
        """Test initialization with permission error"""
        mock_makedirs.side_effect = OSError("Permission denied")
        
        with pytest.raises(ValueError, match="Could not create or access base_path"):
            FilesystemArtifactService("/invalid/path")


class TestFilesystemArtifactServiceHelperMethods:
    """Tests for helper methods"""

    def test_file_has_user_namespace_true(self, artifact_service):
        """Test _file_has_user_namespace returns True for user: prefix"""
        assert artifact_service._file_has_user_namespace("user:document.txt")

    def test_file_has_user_namespace_false(self, artifact_service):
        """Test _file_has_user_namespace returns False for regular filename"""
        assert not artifact_service._file_has_user_namespace("document.txt")

    def test_get_artifact_dir_regular_file(self, artifact_service):
        """Test _get_artifact_dir for regular files"""
        result = artifact_service._get_artifact_dir("app", "user1", "session1", "test.txt")
        expected = os.path.join(artifact_service.base_path, "app", "user1", "session1", "test.txt")
        assert result == expected

    def test_get_artifact_dir_user_namespace(self, artifact_service):
        """Test _get_artifact_dir for user namespace files"""
        result = artifact_service._get_artifact_dir("app", "user1", "session1", "user:test.txt")
        expected = os.path.join(artifact_service.base_path, "app", "user1", "user", "test.txt")
        assert result == expected

    def test_get_artifact_dir_sanitizes_paths(self, artifact_service):
        """Test _get_artifact_dir sanitizes path components"""
        result = artifact_service._get_artifact_dir("../app", "user/../1", "session/1", "test/../file.txt")
        expected = os.path.join(artifact_service.base_path, "app", "1", "1", "file.txt")
        assert result == expected

    def test_get_version_path(self, artifact_service):
        """Test _get_version_path constructs correct path"""
        artifact_dir = "/path/to/artifact"
        version = 5
        result = artifact_service._get_version_path(artifact_dir, version)
        expected = os.path.join(artifact_dir, "5")
        assert result == expected

    def test_get_metadata_path(self, artifact_service):
        """Test _get_metadata_path constructs correct path"""
        artifact_dir = "/path/to/artifact"
        version = 3
        result = artifact_service._get_metadata_path(artifact_dir, version)
        expected = os.path.join(artifact_dir, f"3{METADATA_FILE_SUFFIX}")
        assert result == expected

    def test_normalize_filename_unicode(self, artifact_service):
        """Test _normalize_filename_unicode normalizes Unicode characters"""
        # Test with non-breaking space (U+202F)
        filename_with_nbsp = "test\u202ffile.txt"
        normalized = artifact_service._normalize_filename_unicode(filename_with_nbsp)
        expected = unicodedata.normalize("NFKC", filename_with_nbsp)
        assert normalized == expected

    def test_normalize_filename_unicode_regular_string(self, artifact_service):
        """Test _normalize_filename_unicode with regular ASCII string"""
        filename = "regular_file.txt"
        normalized = artifact_service._normalize_filename_unicode(filename)
        assert normalized == filename


class TestFilesystemArtifactServiceSaveArtifact:
    """Tests for save_artifact method"""

    @pytest.mark.asyncio
    async def test_save_artifact_success(self, artifact_service, sample_artifact):
        """Test successful artifact saving"""
        version = await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        assert version == 0
        
        # Verify files were created
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        version_path = artifact_service._get_version_path(artifact_dir, 0)
        metadata_path = artifact_service._get_metadata_path(artifact_dir, 0)
        
        assert os.path.exists(version_path)
        assert os.path.exists(metadata_path)
        
        # Verify content
        with open(version_path, "rb") as f:
            assert f.read() == b"Hello, World!"
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            assert metadata["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_save_artifact_increments_version(self, artifact_service, sample_artifact):
        """Test that saving multiple artifacts increments version"""
        # Save first artifact
        version1 = await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Save second artifact
        version2 = await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        assert version1 == 0
        assert version2 == 1

    @pytest.mark.asyncio
    async def test_save_artifact_user_namespace(self, artifact_service, sample_artifact):
        """Test saving artifact with user namespace"""
        version = await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt",
            artifact=sample_artifact
        )
        
        assert version == 0
        
        # Verify correct directory structure
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "user:document.txt")
        expected_dir = os.path.join(artifact_service.base_path, "test_app", "user1", "user", "document.txt")
        assert artifact_dir == expected_dir

    @pytest.mark.asyncio
    @pytest.mark.parametrize("artifact_mock", [
        Mock(inline_data=None),
        Mock(inline_data=Mock(data=None))
    ])
    async def test_save_artifact_no_data(self, artifact_service, artifact_mock):
        """Test saving artifact with no data raises OSError"""
        with pytest.raises(OSError, match="Failed to save artifact version 0: Artifact Part has no inline_data to save"):
            await artifact_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=artifact_mock
            )

    @pytest.mark.asyncio
    async def test_save_artifact_cleanup_on_error(self, artifact_service, sample_artifact):
        """Test that files are cleaned up on save error"""
        with patch('builtins.open', side_effect=OSError("Write error")):
            with pytest.raises(OSError, match="Failed to save artifact version"):
                await artifact_service.save_artifact(
                    app_name="test_app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                    artifact=sample_artifact
                )

    @pytest.mark.asyncio
    async def test_save_artifact_binary_data(self, artifact_service, sample_binary_artifact):
        """Test saving binary artifact data"""
        version = await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="image.png",
            artifact=sample_binary_artifact
        )
        
        assert version == 0
        
        # Verify binary data was saved correctly
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "image.png")
        version_path = artifact_service._get_version_path(artifact_dir, 0)
        
        with open(version_path, "rb") as f:
            data = f.read()
            assert data.startswith(b"\x89PNG")


class TestFilesystemArtifactServiceLoadArtifact:
    """Tests for load_artifact method"""

    @pytest.mark.asyncio
    async def test_load_artifact_success(self, artifact_service, sample_artifact):
        """Test successful artifact loading"""
        # First save an artifact
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Then load it
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert loaded_artifact is not None
        assert loaded_artifact.inline_data.data == b"Hello, World!"
        assert loaded_artifact.inline_data.mime_type == "text/plain"

    @pytest.mark.asyncio
    async def test_load_artifact_specific_version(self, artifact_service, sample_artifact):
        """Test loading specific artifact version"""
        # Save multiple versions
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Create different artifact for version 1
        artifact_v1 = adk_types.Part.from_bytes(data=b"Version 1", mime_type="text/plain")
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=artifact_v1
        )
        
        # Load specific version
        loaded_v0 = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=0
        )
        
        loaded_v1 = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=1
        )
        
        assert loaded_v0.inline_data.data == b"Hello, World!"
        assert loaded_v1.inline_data.data == b"Version 1"

    @pytest.mark.asyncio
    async def test_load_artifact_latest_version(self, artifact_service, sample_artifact):
        """Test loading latest version when version not specified"""
        # Save multiple versions
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        artifact_v1 = adk_types.Part.from_bytes(data=b"Latest Version", mime_type="text/plain")
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=artifact_v1
        )
        
        # Load without specifying version (should get latest)
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert loaded_artifact.inline_data.data == b"Latest Version"

    @pytest.mark.asyncio
    async def test_load_artifact_not_found(self, artifact_service):
        """Test loading non-existent artifact returns None"""
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt"
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_missing_files(self, artifact_service, sample_artifact):
        """Test loading artifact with missing data or metadata files"""
        # Save artifact first
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Remove data file
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        version_path = artifact_service._get_version_path(artifact_dir, 0)
        os.remove(version_path)
        
        # Try to load
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_corrupted_metadata(self, artifact_service, sample_artifact):
        """Test loading artifact with corrupted metadata file"""
        # Save artifact first
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Corrupt metadata file
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        metadata_path = artifact_service._get_metadata_path(artifact_dir, 0)
        with open(metadata_path, "w") as f:
            f.write("invalid json")
        
        # Try to load
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert loaded_artifact is None

    @pytest.mark.asyncio
    async def test_load_artifact_user_namespace(self, artifact_service, sample_artifact):
        """Test loading artifact with user namespace"""
        # Save artifact with user namespace
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt",
            artifact=sample_artifact
        )
        
        # Load it
        loaded_artifact = await artifact_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt"
        )
        
        assert loaded_artifact is not None
        assert loaded_artifact.inline_data.data == b"Hello, World!"


class TestFilesystemArtifactServiceListArtifactKeys:
    """Tests for list_artifact_keys method"""

    @pytest.mark.asyncio
    async def test_list_artifact_keys_empty(self, artifact_service):
        """Test listing artifact keys when none exist"""
        keys = await artifact_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert keys == []

    @pytest.mark.asyncio
    async def test_list_artifact_keys_session_artifacts(self, artifact_service, sample_artifact):
        """Test listing session-scoped artifact keys"""
        # Save some artifacts
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="doc1.txt",
            artifact=sample_artifact
        )
        
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="doc2.txt",
            artifact=sample_artifact
        )
        
        keys = await artifact_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["doc1.txt", "doc2.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_user_artifacts(self, artifact_service, sample_artifact):
        """Test listing user-scoped artifact keys"""
        # Save user-scoped artifacts
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:profile.txt",
            artifact=sample_artifact
        )
        
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:settings.txt",
            artifact=sample_artifact
        )
        
        keys = await artifact_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["user:profile.txt", "user:settings.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_mixed(self, artifact_service, sample_artifact):
        """Test listing mixed session and user artifact keys"""
        # Save mixed artifacts
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="session_doc.txt",
            artifact=sample_artifact
        )
        
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:user_doc.txt",
            artifact=sample_artifact
        )
        
        keys = await artifact_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1"
        )
        
        assert sorted(keys) == ["session_doc.txt", "user:user_doc.txt"]


class TestFilesystemArtifactServiceDeleteArtifact:
    """Tests for delete_artifact method"""

    @pytest.mark.asyncio
    async def test_delete_artifact_success(self, artifact_service, sample_artifact):
        """Test successful artifact deletion"""
        # Save artifact first
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Verify it exists
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        assert os.path.exists(artifact_dir)
        
        # Delete it
        await artifact_service.delete_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        # Verify it's gone
        assert not os.path.exists(artifact_dir)

    @pytest.mark.asyncio
    async def test_delete_artifact_not_found(self, artifact_service):
        """Test deleting non-existent artifact (should not raise error)"""
        # Should not raise an exception
        await artifact_service.delete_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt"
        )

    @pytest.mark.asyncio
    async def test_delete_artifact_multiple_versions(self, artifact_service, sample_artifact):
        """Test deleting artifact with multiple versions"""
        # Save multiple versions
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        artifact_v1 = adk_types.Part.from_bytes(data=b"Version 1", mime_type="text/plain")
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=artifact_v1
        )
        
        # Delete artifact (should remove all versions)
        await artifact_service.delete_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        # Verify all versions are gone
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        assert not os.path.exists(artifact_dir)


class TestFilesystemArtifactServiceListVersions:
    """Tests for list_versions method"""

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, artifact_service):
        """Test listing versions when artifact doesn't exist"""
        versions = await artifact_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt"
        )
        
        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_single(self, artifact_service, sample_artifact):
        """Test listing versions with single version"""
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        versions = await artifact_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0]

    @pytest.mark.asyncio
    async def test_list_versions_multiple(self, artifact_service, sample_artifact):
        """Test listing versions with multiple versions"""
        # Save multiple versions
        for i in range(5):
            artifact = adk_types.Part.from_bytes(data=f"Version {i}".encode(), mime_type="text/plain")
            await artifact_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=artifact
            )
        
        versions = await artifact_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_list_versions_ignores_non_numeric(self, artifact_service, sample_artifact):
        """Test that list_versions ignores non-numeric files"""
        # Save artifact
        await artifact_service.save_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            artifact=sample_artifact
        )
        
        # Add some non-numeric files to the directory
        artifact_dir = artifact_service._get_artifact_dir("test_app", "user1", "session1", "test.txt")
        with open(os.path.join(artifact_dir, "not_a_version.txt"), "w") as f:
            f.write("test")
        with open(os.path.join(artifact_dir, "0.meta"), "w") as f:
            f.write("{}")
        
        versions = await artifact_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt"
        )
        
        assert versions == [0]  # Should only include numeric files