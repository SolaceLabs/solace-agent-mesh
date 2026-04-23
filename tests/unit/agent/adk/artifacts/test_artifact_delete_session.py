"""Unit tests for artifact service delete_session_artifacts methods."""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from botocore.exceptions import ClientError
from azure.core.exceptions import HttpResponseError

from src.solace_agent_mesh.agent.adk.artifacts.s3_artifact_service import S3ArtifactService
from src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service import AzureArtifactService


class TestS3ArtifactServiceDeleteSession:
    @pytest.fixture
    def mock_s3_client(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_lists_and_deletes_prefix(self, mock_s3_client):
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)

        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "app1/user1/session1/file1.txt/0"},
                    {"Key": "app1/user1/session1/file1.txt/1"},
                    {"Key": "app2/user1/session1/file2.txt/0"},
                ]
            }
        ]
        mock_s3_client.get_paginator.return_value = paginator
        mock_s3_client.delete_objects.return_value = {"Deleted": [{"Key": "k1"}, {"Key": "k2"}, {"Key": "k3"}]}

        deleted_count = await service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 3

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_returns_correct_count(self, mock_s3_client):
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)

        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": f"app1/user1/session1/file{i}/v"} for i in range(1500)]}
        ]
        mock_s3_client.get_paginator.return_value = paginator
        mock_s3_client.delete_objects.side_effect = [
            {"Deleted": [{"Key": f"k{i}"} for i in range(1000)]},
            {"Deleted": [{"Key": f"k{i}"} for i in range(500)]},
        ]

        deleted_count = await service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 1500
        assert mock_s3_client.delete_objects.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_handles_empty_prefix(self, mock_s3_client):
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)

        paginator = MagicMock()
        paginator.paginate.return_value = [{}]
        mock_s3_client.get_paginator.return_value = paginator

        deleted_count = await service.delete_session_artifacts(user_id="user1", session_id="missing")

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_handles_client_error(self, mock_s3_client, caplog):
        service = S3ArtifactService("test-bucket", s3_client=mock_s3_client)

        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": [{"Key": "app1/user1/session1/file/0"}]}]
        mock_s3_client.get_paginator.return_value = paginator
        mock_s3_client.delete_objects.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObjects")

        with caplog.at_level("ERROR"):
            deleted_count = await service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 0
        assert "Error listing or deleting objects" in caplog.text


class TestAzureArtifactServiceDeleteSession:
    @pytest.fixture
    def mock_container_client(self):
        return MagicMock()

    @pytest.fixture
    def mock_blob_service_client(self, mock_container_client):
        mock_service = MagicMock()
        mock_service.account_name = "test"
        mock_service.get_container_client.return_value = mock_container_client
        return mock_service

    @pytest.fixture
    def azure_service(self, mock_blob_service_client, mock_container_client):
        with patch(
            "src.solace_agent_mesh.agent.adk.artifacts.azure_artifact_service.BlobServiceClient.from_connection_string",
            return_value=mock_blob_service_client,
        ):
            mock_container_client.get_container_properties.return_value = {}
            return AzureArtifactService(
                "test-container",
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==",
            )

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_lists_and_deletes_blobs(self, azure_service, mock_container_client):
        mock_blob1 = MagicMock()
        mock_blob1.name = "app1/user1/session1/file1.txt/0"
        mock_blob2 = MagicMock()
        mock_blob2.name = "app1/user1/session1/file1.txt/1"
        mock_blob3 = MagicMock()
        mock_blob3.name = "app2/user1/session1/file2.txt/0"
        mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

        mock_blob_client = MagicMock()
        mock_container_client.get_blob_client.return_value = mock_blob_client

        deleted_count = await azure_service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 3
        assert mock_blob_client.delete_blob.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_returns_correct_count(self, azure_service, mock_container_client):
        mock_container_client.list_blobs.return_value = [
            type("B", (), {"name": f"app1/user1/session1/file{i}/v"})() for i in range(25)
        ]
        mock_container_client.get_blob_client.return_value = MagicMock()

        deleted_count = await azure_service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 25

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_handles_empty_prefix(self, azure_service, mock_container_client):
        mock_container_client.list_blobs.return_value = []

        deleted_count = await azure_service.delete_session_artifacts(user_id="user1", session_id="none")

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_handles_not_found_error(self, azure_service, mock_container_client, caplog):
        mock_blob = MagicMock()
        mock_blob.name = "app1/user1/session1/file/0"
        mock_container_client.list_blobs.return_value = [mock_blob]

        mock_blob_client = MagicMock()
        mock_blob_client.delete_blob.side_effect = HttpResponseError(message="Not found", status_code=404)
        mock_container_client.get_blob_client.return_value = mock_blob_client

        with caplog.at_level("WARNING"):
            deleted_count = await azure_service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_delete_session_artifacts_handles_http_error(self, azure_service, mock_container_client, caplog):
        mock_blob = MagicMock()
        mock_blob.name = "app1/user1/session1/file/0"
        mock_container_client.list_blobs.return_value = [mock_blob]

        mock_blob_client = MagicMock()
        mock_blob_client.delete_blob.side_effect = HttpResponseError(message="Forbidden", status_code=403)
        mock_container_client.get_blob_client.return_value = mock_blob_client

        with caplog.at_level("WARNING"):
            deleted_count = await azure_service.delete_session_artifacts(user_id="user1", session_id="session1")

        assert deleted_count == 0
        assert "Failed to delete blob" in caplog.text
