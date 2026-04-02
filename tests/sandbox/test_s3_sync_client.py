"""Tests for S3SyncClient."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.sandbox.storage.s3_sync_client import S3SyncClient
from solace_agent_mesh.sandbox.storage.base import SyncObjectMeta


@pytest.fixture
def mock_boto3():
    with patch("solace_agent_mesh.sandbox.storage.s3_sync_client.boto3") as m:
        yield m


@pytest.fixture
def client(mock_boto3) -> S3SyncClient:
    mock_boto3.client.return_value = MagicMock()
    return S3SyncClient(bucket_name="test-bucket", region="us-east-1")


class TestListObjectsPaginates:
    def test_single_page(self, client: S3SyncClient):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "prefix/a.py", "ETag": '"aaa"', "Size": 100},
                    {"Key": "prefix/b.py", "ETag": '"bbb"', "Size": 200},
                ]
            }
        ]
        client._client.get_paginator.return_value = paginator

        result = client.list_objects("prefix/")
        assert len(result) == 2
        assert result[0] == SyncObjectMeta(key="prefix/a.py", etag="aaa", size=100)
        assert result[1] == SyncObjectMeta(key="prefix/b.py", etag="bbb", size=200)

    def test_multiple_pages(self, client: S3SyncClient):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "p/a.py", "ETag": '"aaa"', "Size": 10}]},
            {"Contents": [{"Key": "p/b.py", "ETag": '"bbb"', "Size": 20}]},
        ]
        client._client.get_paginator.return_value = paginator

        result = client.list_objects("p/")
        assert len(result) == 2

    def test_empty_bucket(self, client: S3SyncClient):
        paginator = MagicMock()
        paginator.paginate.return_value = [{}]
        client._client.get_paginator.return_value = paginator

        result = client.list_objects("prefix/")
        assert result == []


class TestDownloadObjectReturnsBytes:
    def test_returns_content(self, client: S3SyncClient):
        body = MagicMock()
        body.read.return_value = b"file-content"
        client._client.get_object.return_value = {"Body": body}

        result = client.download_object("prefix/a.py")
        assert result == b"file-content"
        client._client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="prefix/a.py"
        )
