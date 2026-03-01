"""Tests for the sync storage factory."""

import os
from unittest.mock import patch, MagicMock

import pytest

from solace_agent_mesh.sandbox.storage.factory import create_sync_client
from solace_agent_mesh.sandbox.storage.base import ToolSyncStorageClient


class TestDefaultCreatesS3:
    @patch.dict(os.environ, {"S3_BUCKET_NAME": "test-bucket"}, clear=False)
    @patch("solace_agent_mesh.sandbox.storage.s3_sync_client.boto3")
    def test_default_backend_is_s3(self, mock_boto3):
        mock_boto3.client.return_value = MagicMock()
        client = create_sync_client()
        assert isinstance(client, ToolSyncStorageClient)
        mock_boto3.client.assert_called_once()


class TestExplicitGcs:
    @patch("solace_agent_mesh.sandbox.storage.gcs_sync_client.GcsSyncClient.__init__", return_value=None)
    def test_gcs_dispatch(self, mock_init):
        client = create_sync_client(storage_type="gcs", bucket_name="my-gcs-bucket")
        assert isinstance(client, ToolSyncStorageClient)


class TestMissingBucketRaises:
    @patch.dict(os.environ, {}, clear=True)
    def test_s3_no_bucket(self):
        with pytest.raises(ValueError, match="Bucket name required"):
            create_sync_client(storage_type="s3")

    @patch.dict(os.environ, {}, clear=True)
    def test_gcs_no_bucket(self):
        with pytest.raises(ValueError, match="Bucket name required"):
            create_sync_client(storage_type="gcs")

    @patch.dict(os.environ, {}, clear=True)
    def test_azure_no_bucket(self):
        with pytest.raises(ValueError, match="Container name required"):
            create_sync_client(storage_type="azure")


class TestUnsupportedTypeRaises:
    def test_invalid_type(self):
        with pytest.raises(ValueError, match="Unsupported storage type"):
            create_sync_client(storage_type="ftp", bucket_name="bucket")
