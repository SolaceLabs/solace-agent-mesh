"""
Unit tests for src/solace_agent_mesh/agent/adk/artifacts/azure_artifact_service.py

Tests the AzureArtifactService implementation including:
- Initialization and Azure client setup
- Container validation and access checks
- Artifact saving with versioning
- Artifact loading (latest and specific versions)
- Artifact listing and key management
- Artifact deletion
- Version management
- Unicode filename normalization
- User namespace handling
- Error handling and Azure exceptions
"""

import unicodedata
from unittest.mock import Mock, patch

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from google.genai import types as adk_types

from src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service import (
    AzureArtifactService,
)


def _make_blob_mock(blob_name: str) -> Mock:
    """Create a mock blob object with a real .name attribute.

    Mock(name=...) sets the mock's internal identifier, not an accessible attribute.
    """
    blob = Mock()
    blob.name = blob_name
    return blob


def _make_mock_container_client():
    container_client = Mock()
    container_client.get_container_properties.return_value = {}
    return container_client


def _make_mock_blob_service_client(container_client=None):
    blob_service_client = Mock()
    blob_service_client.account_name = "testaccount"
    if container_client is None:
        container_client = _make_mock_container_client()
    blob_service_client.get_container_client.return_value = container_client
    return blob_service_client


@pytest.fixture
def mock_container_client():
    return _make_mock_container_client()


@pytest.fixture
def mock_blob_service_client(mock_container_client):
    return _make_mock_blob_service_client(mock_container_client)


@pytest.fixture
def azure_service(mock_blob_service_client, mock_container_client):
    with patch(
        "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient"
    ) as MockBlobServiceClient:
        MockBlobServiceClient.return_value = mock_blob_service_client
        service = AzureArtifactService(
            container_name="test-container",
            account_name="testaccount",
            account_key="testkey",
        )
    return service


@pytest.fixture
def sample_artifact():
    data = b"Hello, World!"
    mime_type = "text/plain"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


@pytest.fixture
def sample_binary_artifact():
    data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    mime_type = "image/png"
    return adk_types.Part.from_bytes(data=data, mime_type=mime_type)


class TestAzureArtifactServiceInit:
    """Tests for AzureArtifactService initialization"""

    def test_init_with_connection_string(self):
        mock_bsc = _make_mock_blob_service_client()
        with patch(
            "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient"
        ) as MockBlobServiceClient:
            MockBlobServiceClient.from_connection_string.return_value = mock_bsc
            service = AzureArtifactService(
                container_name="test-container",
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;",
            )
        assert service.container_name == "test-container"
        MockBlobServiceClient.from_connection_string.assert_called_once()

    def test_init_with_account_name_and_key(self):
        mock_bsc = _make_mock_blob_service_client()
        with patch(
            "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient"
        ) as MockBlobServiceClient:
            MockBlobServiceClient.return_value = mock_bsc
            service = AzureArtifactService(
                container_name="test-container",
                account_name="testaccount",
                account_key="testkey",
            )
        assert service.container_name == "test-container"
        assert service.account_name == "testaccount"
        MockBlobServiceClient.assert_called_once_with(
            account_url="https://testaccount.blob.core.windows.net",
            credential="testkey",
        )

    def test_init_with_empty_container_name(self):
        with pytest.raises(ValueError, match="container_name cannot be empty"):
            AzureArtifactService(
                container_name="",
                account_name="testaccount",
            )

    def test_init_with_none_container_name(self):
        with pytest.raises(ValueError, match="container_name cannot be empty"):
            AzureArtifactService(
                container_name=None,
                account_name="testaccount",
            )

    def test_init_no_credentials(self):
        with pytest.raises(ValueError, match="Either 'connection_string'"):
            AzureArtifactService(container_name="test-container")

    def test_init_container_not_found(self):
        mock_cc = _make_mock_container_client()
        mock_cc.get_container_properties.side_effect = ResourceNotFoundError(
            "Not found"
        )
        mock_bsc = _make_mock_blob_service_client(mock_cc)

        with patch(
            "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient"
        ) as MockBlobServiceClient:
            MockBlobServiceClient.return_value = mock_bsc
            with pytest.raises(
                ValueError, match="Azure container 'test-container' does not exist"
            ):
                AzureArtifactService(
                    container_name="test-container",
                    account_name="testaccount",
                    account_key="testkey",
                )

    def test_init_container_access_denied(self):
        mock_cc = _make_mock_container_client()
        error = HttpResponseError("Forbidden")
        error.status_code = 403
        mock_cc.get_container_properties.side_effect = error
        mock_bsc = _make_mock_blob_service_client(mock_cc)

        with patch(
            "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient"
        ) as MockBlobServiceClient:
            MockBlobServiceClient.return_value = mock_bsc
            with pytest.raises(ValueError, match="Access denied to Azure container"):
                AzureArtifactService(
                    container_name="test-container",
                    account_name="testaccount",
                    account_key="testkey",
                )


class TestAzureArtifactServiceHelperMethods:
    """Tests for helper methods"""

    def test_file_has_user_namespace_true(self, azure_service):
        assert azure_service._file_has_user_namespace("user:document.txt")

    def test_file_has_user_namespace_false(self, azure_service):
        assert not azure_service._file_has_user_namespace("document.txt")

    def test_get_object_key_regular_file(self, azure_service):
        result = azure_service._get_object_key(
            "app", "user1", "session1", "test.txt", 5
        )
        assert result == "app/user1/session1/test.txt/5"

    def test_get_object_key_user_namespace(self, azure_service):
        result = azure_service._get_object_key(
            "app", "user1", "session1", "user:test.txt", 3
        )
        assert result == "app/user1/user/test.txt/3"

    def test_get_object_key_strips_app_slashes(self, azure_service):
        result = azure_service._get_object_key(
            "/app/", "user1", "session1", "test.txt", 1
        )
        assert result == "app/user1/session1/test.txt/1"

    def test_normalize_filename_unicode(self, azure_service):
        filename_with_nbsp = "test\u202ffile.txt"
        normalized = azure_service._normalize_filename_unicode(filename_with_nbsp)
        expected = unicodedata.normalize("NFKC", filename_with_nbsp)
        assert normalized == expected

    def test_normalize_filename_unicode_regular_string(self, azure_service):
        filename = "regular_file.txt"
        normalized = azure_service._normalize_filename_unicode(filename)
        assert normalized == filename


class TestAzureArtifactServiceSaveArtifact:
    """Tests for save_artifact method"""

    @pytest.mark.asyncio
    async def test_save_artifact_success(self, azure_service, sample_artifact):
        mock_blob_client = Mock()
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[]):
            version = await azure_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact,
            )

        assert version == 0
        mock_blob_client.upload_blob.assert_called_once()
        call_kwargs = mock_blob_client.upload_blob.call_args[1]
        assert call_kwargs["data"] == b"Hello, World!"
        assert call_kwargs["overwrite"] is True
        assert call_kwargs["metadata"]["original_filename"] == "test.txt"

    @pytest.mark.asyncio
    async def test_save_artifact_increments_version(
        self, azure_service, sample_artifact
    ):
        mock_blob_client = Mock()
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", side_effect=[[0], [0, 1]]):
            version1 = await azure_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact,
            )
            version2 = await azure_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=sample_artifact,
            )

        assert version1 == 1
        assert version2 == 2

    @pytest.mark.asyncio
    async def test_save_artifact_user_namespace(self, azure_service, sample_artifact):
        mock_blob_client = Mock()
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[]):
            version = await azure_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="user:document.txt",
                artifact=sample_artifact,
            )

        assert version == 0
        azure_service.container_client.get_blob_client.assert_called_with(
            "test_app/user1/user/document.txt/0"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "artifact_mock",
        [
            Mock(inline_data=None),
            Mock(inline_data=Mock(data=None)),
        ],
    )
    async def test_save_artifact_no_data(self, azure_service, artifact_mock):
        with pytest.raises(
            ValueError, match="Artifact Part has no inline_data to save"
        ):
            await azure_service.save_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
                artifact=artifact_mock,
            )

    @pytest.mark.asyncio
    async def test_save_artifact_http_error(self, azure_service, sample_artifact):
        mock_blob_client = Mock()
        mock_blob_client.upload_blob.side_effect = HttpResponseError("Forbidden")
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[]):
            with pytest.raises(OSError, match="Failed to save artifact version"):
                await azure_service.save_artifact(
                    app_name="test_app",
                    user_id="user1",
                    session_id="session1",
                    filename="test.txt",
                    artifact=sample_artifact,
                )


class TestAzureArtifactServiceLoadArtifact:
    """Tests for load_artifact method"""

    @pytest.mark.asyncio
    async def test_load_artifact_success(self, azure_service):
        mock_blob_client = Mock()
        mock_downloader = Mock()
        mock_downloader.readall.return_value = b"Hello, World!"
        mock_downloader.properties.content_settings.content_type = "text/plain"
        mock_blob_client.download_blob.return_value = mock_downloader
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[0]):
            loaded = await azure_service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

        assert loaded is not None
        assert loaded.inline_data.data == b"Hello, World!"
        assert loaded.inline_data.mime_type == "text/plain"
        azure_service.container_client.get_blob_client.assert_called_with(
            "test_app/user1/session1/test.txt/0"
        )

    @pytest.mark.asyncio
    async def test_load_artifact_specific_version(self, azure_service):
        mock_blob_client = Mock()
        mock_downloader = Mock()
        mock_downloader.readall.return_value = b"Version 5 data"
        mock_downloader.properties.content_settings.content_type = "text/plain"
        mock_blob_client.download_blob.return_value = mock_downloader
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        loaded = await azure_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=5,
        )

        assert loaded is not None
        assert loaded.inline_data.data == b"Version 5 data"
        azure_service.container_client.get_blob_client.assert_called_with(
            "test_app/user1/session1/test.txt/5"
        )

    @pytest.mark.asyncio
    async def test_load_artifact_latest_version(self, azure_service):
        mock_blob_client = Mock()
        mock_downloader = Mock()
        mock_downloader.readall.return_value = b"Latest version data"
        mock_downloader.properties.content_settings.content_type = "text/plain"
        mock_blob_client.download_blob.return_value = mock_downloader
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[0, 1, 2, 5]):
            loaded = await azure_service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

        assert loaded is not None
        assert loaded.inline_data.data == b"Latest version data"
        azure_service.container_client.get_blob_client.assert_called_with(
            "test_app/user1/session1/test.txt/5"
        )

    @pytest.mark.asyncio
    async def test_load_artifact_not_found(self, azure_service):
        mock_blob_client = Mock()
        mock_blob_client.download_blob.side_effect = ResourceNotFoundError("Not found")
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        loaded = await azure_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt",
            version=0,
        )

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_artifact_no_versions_available(self, azure_service):
        with patch.object(azure_service, "list_versions", return_value=[]):
            loaded = await azure_service.load_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_artifact_http_error(self, azure_service):
        mock_blob_client = Mock()
        mock_blob_client.download_blob.side_effect = HttpResponseError("Forbidden")
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        loaded = await azure_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
            version=0,
        )

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_artifact_user_namespace(self, azure_service):
        mock_blob_client = Mock()
        mock_downloader = Mock()
        mock_downloader.readall.return_value = b"User document data"
        mock_downloader.properties.content_settings.content_type = "text/plain"
        mock_blob_client.download_blob.return_value = mock_downloader
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        loaded = await azure_service.load_artifact(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt",
            version=0,
        )

        assert loaded is not None
        azure_service.container_client.get_blob_client.assert_called_with(
            "test_app/user1/user/document.txt/0"
        )


class TestAzureArtifactServiceListArtifactKeys:
    """Tests for list_artifact_keys method"""

    @pytest.mark.asyncio
    async def test_list_artifact_keys_empty(self, azure_service):
        azure_service.container_client.list_blobs.return_value = []

        keys = await azure_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
        )

        assert keys == []

    @pytest.mark.asyncio
    async def test_list_artifact_keys_session_artifacts(self, azure_service):
        session_blobs = [
            _make_blob_mock("test_app/user1/session1/doc1.txt/0"),
            _make_blob_mock("test_app/user1/session1/doc1.txt/1"),
            _make_blob_mock("test_app/user1/session1/doc2.txt/0"),
        ]
        user_blobs = []

        azure_service.container_client.list_blobs.side_effect = [
            session_blobs,
            user_blobs,
        ]

        keys = await azure_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
        )

        assert sorted(keys) == ["doc1.txt", "doc2.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_user_artifacts(self, azure_service):
        session_blobs = []
        user_blobs = [
            _make_blob_mock("test_app/user1/user/profile.txt/0"),
            _make_blob_mock("test_app/user1/user/settings.txt/0"),
        ]

        azure_service.container_client.list_blobs.side_effect = [
            session_blobs,
            user_blobs,
        ]

        keys = await azure_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
        )

        assert sorted(keys) == ["user:profile.txt", "user:settings.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_mixed(self, azure_service):
        session_blobs = [
            _make_blob_mock("test_app/user1/session1/session_doc.txt/0"),
        ]
        user_blobs = [
            _make_blob_mock("test_app/user1/user/user_doc.txt/0"),
        ]

        azure_service.container_client.list_blobs.side_effect = [
            session_blobs,
            user_blobs,
        ]

        keys = await azure_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
        )

        assert sorted(keys) == ["session_doc.txt", "user:user_doc.txt"]

    @pytest.mark.asyncio
    async def test_list_artifact_keys_http_error(self, azure_service):
        azure_service.container_client.list_blobs.side_effect = HttpResponseError(
            "Forbidden"
        )

        keys = await azure_service.list_artifact_keys(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
        )

        assert keys == []


class TestAzureArtifactServiceDeleteArtifact:
    """Tests for delete_artifact method"""

    @pytest.mark.asyncio
    async def test_delete_artifact_success(self, azure_service):
        mock_blob_client = Mock()
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[0, 1, 2]):
            await azure_service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

        assert mock_blob_client.delete_blob.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_artifact_no_versions(self, azure_service):
        mock_blob_client = Mock()
        azure_service.container_client.get_blob_client.return_value = mock_blob_client

        with patch.object(azure_service, "list_versions", return_value=[]):
            await azure_service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="nonexistent.txt",
            )

        mock_blob_client.delete_blob.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_artifact_partial_failure(self, azure_service):
        mock_blob_clients = [Mock(), Mock(), Mock()]
        mock_blob_clients[1].delete_blob.side_effect = HttpResponseError("Forbidden")
        azure_service.container_client.get_blob_client.side_effect = mock_blob_clients

        with patch.object(azure_service, "list_versions", return_value=[0, 1, 2]):
            await azure_service.delete_artifact(
                app_name="test_app",
                user_id="user1",
                session_id="session1",
                filename="test.txt",
            )

        for client in mock_blob_clients:
            client.delete_blob.assert_called_once()


class TestAzureArtifactServiceListVersions:
    """Tests for list_versions method"""

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, azure_service):
        azure_service.container_client.list_blobs.return_value = []

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="nonexistent.txt",
        )

        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_single(self, azure_service):
        blobs = [_make_blob_mock("test_app/user1/session1/test.txt/0")]
        azure_service.container_client.list_blobs.return_value = blobs

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
        )

        assert versions == [0]

    @pytest.mark.asyncio
    async def test_list_versions_multiple(self, azure_service):
        blobs = [
            _make_blob_mock("test_app/user1/session1/test.txt/0"),
            _make_blob_mock("test_app/user1/session1/test.txt/2"),
            _make_blob_mock("test_app/user1/session1/test.txt/1"),
            _make_blob_mock("test_app/user1/session1/test.txt/5"),
        ]
        azure_service.container_client.list_blobs.return_value = blobs

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
        )

        assert versions == [0, 1, 2, 5]

    @pytest.mark.asyncio
    async def test_list_versions_ignores_non_numeric(self, azure_service):
        blobs = [
            _make_blob_mock("test_app/user1/session1/test.txt/0"),
            _make_blob_mock("test_app/user1/session1/test.txt/metadata"),
            _make_blob_mock("test_app/user1/session1/test.txt/1"),
            _make_blob_mock("test_app/user1/session1/test.txt/invalid"),
        ]
        azure_service.container_client.list_blobs.return_value = blobs

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
        )

        assert versions == [0, 1]

    @pytest.mark.asyncio
    async def test_list_versions_http_error(self, azure_service):
        azure_service.container_client.list_blobs.side_effect = HttpResponseError(
            "Forbidden"
        )

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="test.txt",
        )

        assert versions == []

    @pytest.mark.asyncio
    async def test_list_versions_user_namespace(self, azure_service):
        blobs = [
            _make_blob_mock("test_app/user1/user/document.txt/0"),
            _make_blob_mock("test_app/user1/user/document.txt/1"),
        ]
        azure_service.container_client.list_blobs.return_value = blobs

        versions = await azure_service.list_versions(
            app_name="test_app",
            user_id="user1",
            session_id="session1",
            filename="user:document.txt",
        )

        assert versions == [0, 1]
        azure_service.container_client.list_blobs.assert_called_once_with(
            name_starts_with="test_app/user1/user/document.txt/"
        )
