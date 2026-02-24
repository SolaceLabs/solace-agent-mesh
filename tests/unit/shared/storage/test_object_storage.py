"""Unit tests for object storage clients and factory."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from solace_agent_mesh.services.platform.storage.base import StorageObject
from solace_agent_mesh.services.platform.storage.exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
)
from solace_agent_mesh.services.platform.storage.factory import create_storage_client
from solace_agent_mesh.services.platform.storage.s3_client import S3StorageClient


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in [
        "OBJECT_STORAGE_TYPE",
        "S3_ENDPOINT_URL",
        "S3_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GCS_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_STORAGE_ACCOUNT_NAME",
        "AZURE_STORAGE_ACCOUNT_KEY",
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def mock_boto3():
    with patch("solace_agent_mesh.services.platform.storage.s3_client.boto3") as mock:
        mock_client = MagicMock()
        mock.client.return_value = mock_client
        yield mock_client


@pytest.fixture()
def s3_client(mock_boto3):
    return S3StorageClient(bucket_name="test-bucket", region="us-west-2")


@pytest.fixture()
def s3_custom_endpoint(mock_boto3):
    return S3StorageClient(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:8333",
    )


def _make_client_error(code: str, message: str = "error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "TestOp")


def _make_get_object_response(
    content: bytes = b"data",
    content_type: str | None = None,
    metadata: dict | None = None,
) -> dict:
    body = MagicMock()
    body.read.return_value = content
    resp: dict = {"Body": body}
    if content_type is not None:
        resp["ContentType"] = content_type
    if metadata is not None:
        resp["Metadata"] = metadata
    return resp


class TestStorageObject:
    def test_stores_content_and_content_type(self):
        obj = StorageObject(content=b"hello", content_type="text/plain")
        assert obj.content == b"hello"
        assert obj.content_type == "text/plain"

    def test_default_content_type_is_octet_stream(self):
        obj = StorageObject(content=b"")
        assert obj.content_type == "application/octet-stream"

    def test_default_metadata_is_empty_dict(self):
        obj = StorageObject(content=b"")
        assert obj.metadata == {}

    def test_metadata_stores_values(self):
        obj = StorageObject(content=b"", metadata={"author": "test"})
        assert obj.metadata == {"author": "test"}


class TestS3ErrorTranslation:
    @pytest.mark.parametrize(
        ("error_code", "expected_type"),
        [
            ("NoSuchKey", StorageNotFoundError),
            ("404", StorageNotFoundError),
            ("AccessDenied", StoragePermissionError),
            ("403", StoragePermissionError),
            ("InvalidAccessKeyId", StoragePermissionError),
            ("SignatureDoesNotMatch", StoragePermissionError),
            ("EndpointConnectionError", StorageConnectionError),
        ],
    )
    def test_error_code_maps_to_correct_exception(self, s3_client, mock_boto3, error_code, expected_type):
        mock_boto3.get_object.side_effect = _make_client_error(error_code)

        with pytest.raises(expected_type):
            s3_client.get_object("some-key")

    def test_unknown_error_code_raises_base_storage_error(self, s3_client, mock_boto3):
        mock_boto3.put_object.side_effect = _make_client_error("InternalError")

        with pytest.raises(StorageError) as exc_info:
            s3_client.put_object("key", b"data", "text/plain")

        assert type(exc_info.value) is StorageError

    def test_error_preserves_key_and_cause(self, s3_client, mock_boto3):
        original = _make_client_error("NoSuchKey")
        mock_boto3.get_object.side_effect = original

        with pytest.raises(StorageNotFoundError) as exc_info:
            s3_client.get_object("missing/file.txt")

        assert exc_info.value.key == "missing/file.txt"
        assert exc_info.value.cause is original


class TestS3PutObject:
    def test_returns_key(self, s3_client, mock_boto3):
        result = s3_client.put_object("ns/file.zip", b"data", "application/zip")
        assert result == "ns/file.zip"

    def test_with_metadata_includes_metadata_in_request(self, s3_client, mock_boto3):
        s3_client.put_object("k", b"d", "text/plain", metadata={"env": "prod"})

        call_kwargs = mock_boto3.put_object.call_args.kwargs
        assert call_kwargs["Metadata"] == {"env": "prod"}

    def test_without_metadata_omits_metadata_param(self, s3_client, mock_boto3):
        s3_client.put_object("k", b"d", "text/plain")

        call_kwargs = mock_boto3.put_object.call_args.kwargs
        assert "Metadata" not in call_kwargs


class TestS3GetObject:
    def test_returns_storage_object_with_content(self, s3_client, mock_boto3):
        mock_boto3.get_object.return_value = _make_get_object_response(
            content=b"file-bytes", content_type="image/png"
        )

        result = s3_client.get_object("img.png")

        assert isinstance(result, StorageObject)
        assert result.content == b"file-bytes"

    def test_returns_content_type_from_response(self, s3_client, mock_boto3):
        mock_boto3.get_object.return_value = _make_get_object_response(content_type="application/json")

        result = s3_client.get_object("data.json")
        assert result.content_type == "application/json"

    def test_returns_metadata_from_response(self, s3_client, mock_boto3):
        mock_boto3.get_object.return_value = _make_get_object_response(metadata={"version": "2"})

        result = s3_client.get_object("file.txt")
        assert result.metadata == {"version": "2"}

    def test_defaults_content_type_when_missing(self, s3_client, mock_boto3):
        mock_boto3.get_object.return_value = _make_get_object_response()

        result = s3_client.get_object("file.bin")
        assert result.content_type == "application/octet-stream"

    def test_defaults_metadata_when_missing(self, s3_client, mock_boto3):
        mock_boto3.get_object.return_value = _make_get_object_response()

        result = s3_client.get_object("file.bin")
        assert result.metadata == {}

    def test_missing_key_raises_storage_not_found(self, s3_client, mock_boto3):
        mock_boto3.get_object.side_effect = _make_client_error("NoSuchKey")

        with pytest.raises(StorageNotFoundError):
            s3_client.get_object("no-such-key")


class TestS3DeleteObject:
    def test_delete_succeeds(self, s3_client, mock_boto3):
        s3_client.delete_object("ns/file.zip")
        mock_boto3.delete_object.assert_called_once()

    def test_delete_translates_errors(self, s3_client, mock_boto3):
        mock_boto3.delete_object.side_effect = _make_client_error("AccessDenied")

        with pytest.raises(StoragePermissionError):
            s3_client.delete_object("forbidden")


class TestS3DeletePrefix:
    def _setup_paginator(self, mock_boto3, pages: list[dict]):
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        mock_boto3.get_paginator.return_value = paginator

    def test_returns_count_of_deleted_objects(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [
            {"Contents": [{"Key": "ns/a.zip"}, {"Key": "ns/b.yaml"}]},
        ])

        assert s3_client.delete_prefix("ns/") == 2

    def test_empty_prefix_returns_zero(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [{"Contents": []}])

        assert s3_client.delete_prefix("empty/") == 0
        mock_boto3.delete_objects.assert_not_called()

    def test_multiple_pages_returns_total_count(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [
            {"Contents": [{"Key": "p/1"}, {"Key": "p/2"}]},
            {"Contents": [{"Key": "p/3"}]},
        ])

        assert s3_client.delete_prefix("p/") == 3
        assert mock_boto3.delete_objects.call_count == 2

    def test_no_contents_key_returns_zero(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [{}])

        assert s3_client.delete_prefix("x/") == 0
        mock_boto3.delete_objects.assert_not_called()


class TestS3PublicUrl:
    def test_aws_url_format(self, s3_client):
        url = s3_client.get_public_url("ns/file.zip")
        assert url == "https://test-bucket.s3.us-west-2.amazonaws.com/ns/file.zip"

    def test_custom_endpoint_url_format(self, s3_custom_endpoint):
        url = s3_custom_endpoint.get_public_url("ns/file.zip")
        assert url == "http://localhost:8333/test-bucket/ns/file.zip"

    def test_custom_endpoint_strips_trailing_slash(self, mock_boto3):
        client = S3StorageClient(bucket_name="b", endpoint_url="http://localhost:8333/")
        url = client.get_public_url("key")
        assert url == "http://localhost:8333/b/key"


class TestFactory:
    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_defaults_to_s3_backend(self, _mock_boto3):
        client = create_storage_client(bucket_name="b")
        assert isinstance(client, S3StorageClient)

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_explicit_s3_type(self, _mock_boto3):
        client = create_storage_client(bucket_name="b", storage_type="s3")
        assert isinstance(client, S3StorageClient)

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_param_overrides_env_var(self, _mock_boto3, monkeypatch):
        monkeypatch.setenv("OBJECT_STORAGE_TYPE", "gcs")
        client = create_storage_client(bucket_name="b", storage_type="s3")
        assert isinstance(client, S3StorageClient)

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_case_insensitive(self, _mock_boto3):
        client = create_storage_client(bucket_name="b", storage_type="S3")
        assert isinstance(client, S3StorageClient)

    def test_unsupported_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported storage type"):
            create_storage_client(bucket_name="b", storage_type="dropbox")

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_reads_region_from_env(self, _mock_boto3, monkeypatch):
        monkeypatch.setenv("S3_REGION", "eu-west-1")
        client = create_storage_client(bucket_name="b")
        assert client._region == "eu-west-1"

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_defaults_region_to_us_east_1(self, _mock_boto3):
        client = create_storage_client(bucket_name="b")
        assert client._region == "us-east-1"

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_reads_endpoint_from_env(self, _mock_boto3, monkeypatch):
        monkeypatch.setenv("S3_ENDPOINT_URL", "http://minio:9000")
        client = create_storage_client(bucket_name="b")
        assert client._endpoint_url == "http://minio:9000"

    @patch("solace_agent_mesh.services.platform.storage.s3_client.boto3")
    def test_reads_credentials_from_env(self, mock_boto3, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKID")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "SECRET")
        create_storage_client(bucket_name="b")

        call_kwargs = mock_boto3.client.call_args.kwargs
        assert call_kwargs["aws_access_key_id"] == "AKID"
        assert call_kwargs["aws_secret_access_key"] == "SECRET"

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    def test_gcs_type_creates_gcs_client(self, _mock_gcs):
        from solace_agent_mesh.services.platform.storage.gcs_client import (
            GcsStorageClient,
        )

        client = create_storage_client(bucket_name="gcs-bucket", storage_type="gcs")
        assert isinstance(client, GcsStorageClient)

    @patch("solace_agent_mesh.services.platform.storage.azure_client.BlobServiceClient")
    def test_azure_type_creates_azure_client(self, _mock_blob, monkeypatch):
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        from solace_agent_mesh.services.platform.storage.azure_client import (
            AzureBlobStorageClient,
        )

        client = create_storage_client(bucket_name="container", storage_type="azure")
        assert isinstance(client, AzureBlobStorageClient)
