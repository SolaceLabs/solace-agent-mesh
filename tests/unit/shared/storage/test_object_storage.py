"""Unit tests for object storage clients and factory."""

from unittest.mock import MagicMock, patch

import pytest
from azure.storage.blob import ContentSettings
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
        "GCS_CREDENTIALS_JSON",
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


class TestS3ListObjects:
    def _setup_paginator(self, mock_boto3, pages: list[dict]):
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        mock_boto3.get_paginator.return_value = paginator

    def test_single_page(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [
            {"Contents": [{"Key": "ns/a.txt"}, {"Key": "ns/b.txt"}]},
        ])

        assert s3_client.list_objects("ns/") == ["ns/a.txt", "ns/b.txt"]

    def test_multiple_pages(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [
            {"Contents": [{"Key": "p/1"}]},
            {"Contents": [{"Key": "p/2"}, {"Key": "p/3"}]},
        ])

        assert s3_client.list_objects("p/") == ["p/1", "p/2", "p/3"]

    def test_empty_returns_empty_list(self, s3_client, mock_boto3):
        self._setup_paginator(mock_boto3, [{}])

        assert s3_client.list_objects("empty/") == []

    def test_translates_errors(self, s3_client, mock_boto3):
        paginator = MagicMock()
        paginator.paginate.side_effect = _make_client_error("AccessDenied")
        mock_boto3.get_paginator.return_value = paginator

        with pytest.raises(StoragePermissionError):
            s3_client.list_objects("forbidden/")


class TestS3GeneratePresignedUrl:
    def test_returns_url(self, s3_client, mock_boto3):
        mock_boto3.generate_presigned_url.return_value = "https://signed-url"

        assert s3_client.generate_presigned_url("file.txt") == "https://signed-url"

    def test_passes_correct_params(self, s3_client, mock_boto3):
        mock_boto3.generate_presigned_url.return_value = "https://url"

        s3_client.generate_presigned_url("ns/key.zip")

        mock_boto3.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object",
            Params={"Bucket": "test-bucket", "Key": "ns/key.zip"},
            ExpiresIn=3600,
        )

    def test_custom_expiry(self, s3_client, mock_boto3):
        mock_boto3.generate_presigned_url.return_value = "https://url"

        s3_client.generate_presigned_url("k", expires_in=600)

        call_kwargs = mock_boto3.generate_presigned_url.call_args.kwargs
        assert call_kwargs["ExpiresIn"] == 600

    def test_translates_errors(self, s3_client, mock_boto3):
        mock_boto3.generate_presigned_url.side_effect = _make_client_error("AccessDenied")

        with pytest.raises(StoragePermissionError):
            s3_client.generate_presigned_url("forbidden.txt")


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

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    @patch("solace_agent_mesh.services.platform.storage.gcs_client.service_account")
    def test_gcs_factory_passes_credentials_json(self, mock_sa, _mock_gcs, monkeypatch):
        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_info.return_value = mock_creds
        monkeypatch.setenv("GCS_CREDENTIALS_JSON", '{"type": "service_account"}')

        client = create_storage_client(bucket_name="b", storage_type="gcs")

        mock_sa.Credentials.from_service_account_info.assert_called_once_with({"type": "service_account"})
        assert client._credentials is mock_creds


@pytest.fixture()
def mock_gcs():
    with patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs") as mock:
        mock_bucket = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.bucket.return_value = mock_bucket
        mock.Client.return_value = mock_client_instance
        yield mock_bucket


@pytest.fixture()
def gcs_client(mock_gcs):
    from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

    return GcsStorageClient(bucket_name="test-bucket")


@pytest.fixture()
def gcs_client_with_creds(mock_gcs):
    from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

    with patch("solace_agent_mesh.services.platform.storage.gcs_client.service_account") as mock_sa:
        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_info.return_value = mock_creds
        client = GcsStorageClient(
            bucket_name="test-bucket",
            credentials_json='{"type": "service_account"}',
        )
    return client


class TestGcsInit:
    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    def test_no_credentials_uses_adc(self, mock_gcs_mod):
        from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

        client = GcsStorageClient(bucket_name="b")
        assert client._credentials is None
        mock_gcs_mod.Client.assert_called_once_with()

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    @patch("solace_agent_mesh.services.platform.storage.gcs_client.service_account")
    def test_credentials_json_creates_credentials(self, mock_sa, mock_gcs_mod):
        from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_info.return_value = mock_creds

        client = GcsStorageClient(
            bucket_name="b",
            credentials_json='{"type": "service_account", "project_id": "test"}',
        )

        mock_sa.Credentials.from_service_account_info.assert_called_once()
        assert client._credentials is mock_creds

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    @patch("solace_agent_mesh.services.platform.storage.gcs_client.service_account")
    def test_credentials_path_creates_credentials(self, mock_sa, mock_gcs_mod):
        from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds

        client = GcsStorageClient(bucket_name="b", credentials_path="/path/to/creds.json")

        mock_sa.Credentials.from_service_account_file.assert_called_once_with("/path/to/creds.json")
        assert client._credentials is mock_creds

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    @patch("solace_agent_mesh.services.platform.storage.gcs_client.service_account")
    def test_credentials_json_takes_priority_over_path(self, mock_sa, mock_gcs_mod):
        from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_info.return_value = mock_creds

        client = GcsStorageClient(
            bucket_name="b",
            credentials_json='{"type": "service_account"}',
            credentials_path="/path/to/creds.json",
        )

        mock_sa.Credentials.from_service_account_info.assert_called_once()
        mock_sa.Credentials.from_service_account_file.assert_not_called()
        assert client._credentials is mock_creds

    @patch("solace_agent_mesh.services.platform.storage.gcs_client.gcs")
    def test_project_passed_to_client(self, mock_gcs_mod):
        from solace_agent_mesh.services.platform.storage.gcs_client import GcsStorageClient

        GcsStorageClient(bucket_name="b", project="my-project")
        mock_gcs_mod.Client.assert_called_once_with(project="my-project")


class TestGcsErrorTranslation:
    def test_not_found_maps_to_storage_not_found(self, gcs_client, mock_gcs):
        from google.api_core.exceptions import NotFound

        mock_gcs.blob.return_value.download_as_bytes.side_effect = NotFound("not found")

        with pytest.raises(StorageNotFoundError):
            gcs_client.get_object("missing-key")

    def test_forbidden_maps_to_storage_permission(self, gcs_client, mock_gcs):
        from google.api_core.exceptions import Forbidden

        mock_gcs.blob.return_value.upload_from_string.side_effect = Forbidden("denied")

        with pytest.raises(StoragePermissionError):
            gcs_client.put_object("key", b"data", "text/plain")

    def test_connection_error_maps_to_storage_connection(self, gcs_client, mock_gcs):
        mock_gcs.blob.return_value.download_as_bytes.side_effect = ConnectionError("timeout")

        with pytest.raises(StorageConnectionError):
            gcs_client.get_object("key")

    def test_unknown_error_maps_to_base_storage_error(self, gcs_client, mock_gcs):
        mock_gcs.blob.return_value.upload_from_string.side_effect = RuntimeError("boom")

        with pytest.raises(StorageError) as exc_info:
            gcs_client.put_object("key", b"data", "text/plain")

        assert type(exc_info.value) is StorageError


class TestGcsPutObject:
    def test_returns_key(self, gcs_client, mock_gcs):
        result = gcs_client.put_object("ns/file.zip", b"data", "application/zip")
        assert result == "ns/file.zip"

    def test_with_metadata_sets_blob_metadata(self, gcs_client, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        gcs_client.put_object("k", b"d", "text/plain", metadata={"env": "prod"})
        assert mock_blob.metadata == {"env": "prod"}

    def test_calls_upload_from_string(self, gcs_client, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        gcs_client.put_object("k", b"data", "image/png")
        mock_blob.upload_from_string.assert_called_once_with(b"data", content_type="image/png")


class TestGcsGetObject:
    def test_returns_storage_object(self, gcs_client, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        mock_blob.download_as_bytes.return_value = b"file-bytes"
        mock_blob.content_type = "image/png"
        mock_blob.metadata = {"version": "1"}

        result = gcs_client.get_object("img.png")

        assert isinstance(result, StorageObject)
        assert result.content == b"file-bytes"
        assert result.content_type == "image/png"
        assert result.metadata == {"version": "1"}

    def test_defaults_content_type_when_none(self, gcs_client, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        mock_blob.download_as_bytes.return_value = b"data"
        mock_blob.content_type = None
        mock_blob.metadata = None

        result = gcs_client.get_object("file.bin")
        assert result.content_type == "application/octet-stream"
        assert result.metadata == {}


class TestGcsDeleteObject:
    def test_delete_succeeds(self, gcs_client, mock_gcs):
        gcs_client.delete_object("ns/file.zip")
        mock_gcs.blob.return_value.delete.assert_called_once()

    def test_delete_not_found_is_silent(self, gcs_client, mock_gcs):
        from google.api_core.exceptions import NotFound

        mock_gcs.blob.return_value.delete.side_effect = NotFound("gone")
        gcs_client.delete_object("already-gone")


class TestGcsDeletePrefix:
    def test_returns_count(self, gcs_client, mock_gcs):
        blob1 = MagicMock()
        blob2 = MagicMock()
        mock_gcs.list_blobs.return_value = [blob1, blob2]

        assert gcs_client.delete_prefix("ns/") == 2

    def test_empty_prefix_returns_zero(self, gcs_client, mock_gcs):
        mock_gcs.list_blobs.return_value = []

        assert gcs_client.delete_prefix("empty/") == 0
        mock_gcs.delete_blobs.assert_not_called()


class TestGcsListObjects:
    def test_returns_blob_names(self, gcs_client, mock_gcs):
        blob1, blob2 = MagicMock(), MagicMock()
        blob1.name = "ns/a.txt"
        blob2.name = "ns/b.txt"
        mock_gcs.list_blobs.return_value = [blob1, blob2]

        assert gcs_client.list_objects("ns/") == ["ns/a.txt", "ns/b.txt"]

    def test_empty_returns_empty_list(self, gcs_client, mock_gcs):
        mock_gcs.list_blobs.return_value = []

        assert gcs_client.list_objects("empty/") == []


class TestGcsPresignedUrl:
    def test_no_credentials_raises_permission_error(self, gcs_client):
        with pytest.raises(StoragePermissionError, match="credentials are required"):
            gcs_client.generate_presigned_url("file.txt")

    def test_with_credentials_returns_url(self, gcs_client_with_creds, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        mock_blob.generate_signed_url.return_value = "https://signed-url"

        result = gcs_client_with_creds.generate_presigned_url("file.txt")
        assert result == "https://signed-url"

    def test_passes_correct_params(self, gcs_client_with_creds, mock_gcs):
        mock_blob = mock_gcs.blob.return_value
        mock_blob.generate_signed_url.return_value = "https://url"

        gcs_client_with_creds.generate_presigned_url("key.zip", expires_in=600)

        call_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert call_kwargs["version"] == "v4"
        assert call_kwargs["method"] == "GET"


class TestGcsPublicUrl:
    def test_url_format(self, gcs_client):
        url = gcs_client.get_public_url("ns/file.zip")
        assert url == "https://storage.googleapis.com/test-bucket/ns/file.zip"


@pytest.fixture()
def mock_blob_service():
    with patch("solace_agent_mesh.services.platform.storage.azure_client.BlobServiceClient") as mock_cls:
        mock_service = MagicMock()
        mock_cls.return_value = mock_service
        mock_cls.from_connection_string.return_value = mock_service
        mock_container = MagicMock()
        mock_service.get_container_client.return_value = mock_container
        mock_service.account_name = "testaccount"
        yield {"cls": mock_cls, "service": mock_service, "container": mock_container}


@pytest.fixture()
def azure_client_conn_str(mock_blob_service):
    from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

    return AzureBlobStorageClient(
        container_name="test-container",
        connection_string="DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net",
    )


@pytest.fixture()
def azure_client_key(mock_blob_service):
    from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

    return AzureBlobStorageClient(
        container_name="test-container",
        account_name="testaccount",
        account_key="testkey123",
    )


@pytest.fixture()
def azure_client_workload_identity(mock_blob_service):
    from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

    with patch("azure.identity.DefaultAzureCredential") as mock_dac:
        mock_dac.return_value = MagicMock()
        client = AzureBlobStorageClient(
            container_name="test-container",
            account_name="testaccount",
        )
    return client


class TestAzureInit:
    def test_connection_string_init(self, mock_blob_service):
        from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

        AzureBlobStorageClient(
            container_name="test-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ==",
        )
        mock_blob_service["cls"].from_connection_string.assert_called_once_with(
            "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ=="
        )

    def test_account_name_and_key_init(self, mock_blob_service):
        from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

        AzureBlobStorageClient(
            container_name="test-container",
            account_name="testaccount",
            account_key="testkey123",
        )
        mock_blob_service["cls"].assert_called_once_with(
            account_url="https://testaccount.blob.core.windows.net",
            credential="testkey123",
        )

    def test_account_name_only_uses_default_credential(self, mock_blob_service):
        from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

        with patch("azure.identity.DefaultAzureCredential") as mock_dac:
            mock_cred = MagicMock()
            mock_dac.return_value = mock_cred
            client = AzureBlobStorageClient(
                container_name="test-container",
                account_name="testaccount",
            )
        mock_dac.assert_called_once()
        mock_blob_service["cls"].assert_called_once_with(
            account_url="https://testaccount.blob.core.windows.net",
            credential=mock_cred,
        )
        assert client._account_key is None

    def test_no_args_raises_value_error(self, mock_blob_service):
        from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

        with pytest.raises(ValueError, match="Azure Blob Storage requires"):
            AzureBlobStorageClient(container_name="test-container")

    def test_connection_string_extracts_account_key(self, mock_blob_service):
        from solace_agent_mesh.services.platform.storage.azure_client import AzureBlobStorageClient

        client = AzureBlobStorageClient(
            container_name="test-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net",
        )
        assert client._account_key == "dGVzdGtleQ=="


class TestAzureErrorTranslation:
    def test_resource_not_found_maps_to_storage_not_found(self, azure_client_conn_str, mock_blob_service):
        from azure.core.exceptions import ResourceNotFoundError

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.side_effect = ResourceNotFoundError("not found")
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        with pytest.raises(StorageNotFoundError):
            azure_client_conn_str.get_object("missing-key")

    def test_http_403_maps_to_storage_permission(self, azure_client_conn_str, mock_blob_service):
        from azure.core.exceptions import HttpResponseError

        error = HttpResponseError("forbidden")
        error.status_code = 403
        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob.side_effect = error
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        with pytest.raises(StoragePermissionError):
            azure_client_conn_str.put_object("key", b"data", "text/plain")

    def test_connection_error_maps_to_storage_connection(self, azure_client_conn_str, mock_blob_service):
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.side_effect = ConnectionError("timeout")
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        with pytest.raises(StorageConnectionError):
            azure_client_conn_str.get_object("key")

    def test_unknown_error_maps_to_base_storage_error(self, azure_client_conn_str, mock_blob_service):
        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob.side_effect = RuntimeError("boom")
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        with pytest.raises(StorageError) as exc_info:
            azure_client_conn_str.put_object("key", b"data", "text/plain")

        assert type(exc_info.value) is StorageError


class TestAzurePutObject:
    def test_returns_key(self, azure_client_conn_str, mock_blob_service):
        result = azure_client_conn_str.put_object("ns/file.zip", b"data", "application/zip")
        assert result == "ns/file.zip"

    def test_calls_upload_blob_with_correct_params(self, azure_client_conn_str, mock_blob_service):
        mock_blob_client = MagicMock()
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        azure_client_conn_str.put_object("k", b"d", "text/plain", metadata={"env": "prod"})

        call_kwargs = mock_blob_client.upload_blob.call_args
        assert call_kwargs.kwargs["overwrite"] is True
        assert call_kwargs.kwargs["metadata"] == {"env": "prod"}
        assert isinstance(call_kwargs.kwargs["content_settings"], ContentSettings)


class TestAzureGetObject:
    def test_returns_storage_object(self, azure_client_conn_str, mock_blob_service):
        mock_blob_client = MagicMock()
        mock_download = MagicMock()
        mock_download.readall.return_value = b"file-bytes"
        mock_download.properties.content_settings.content_type = "image/png"
        mock_download.properties.metadata = {"version": "1"}
        mock_blob_client.download_blob.return_value = mock_download
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        result = azure_client_conn_str.get_object("img.png")

        assert isinstance(result, StorageObject)
        assert result.content == b"file-bytes"
        assert result.content_type == "image/png"
        assert result.metadata == {"version": "1"}

    def test_defaults_content_type_when_none(self, azure_client_conn_str, mock_blob_service):
        mock_blob_client = MagicMock()
        mock_download = MagicMock()
        mock_download.readall.return_value = b"data"
        mock_download.properties.content_settings.content_type = None
        mock_download.properties.metadata = None
        mock_blob_client.download_blob.return_value = mock_download
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        result = azure_client_conn_str.get_object("file.bin")
        assert result.content_type == "application/octet-stream"


class TestAzureDeleteObject:
    def test_delete_succeeds(self, azure_client_conn_str, mock_blob_service):
        azure_client_conn_str.delete_object("ns/file.zip")
        mock_blob_service["container"].get_blob_client.return_value.delete_blob.assert_called_once()

    def test_delete_not_found_is_silent(self, azure_client_conn_str, mock_blob_service):
        from azure.core.exceptions import ResourceNotFoundError

        mock_blob_client = MagicMock()
        mock_blob_client.delete_blob.side_effect = ResourceNotFoundError("gone")
        mock_blob_service["container"].get_blob_client.return_value = mock_blob_client

        azure_client_conn_str.delete_object("already-gone")


class TestAzurePresignedUrl:
    @patch("solace_agent_mesh.services.platform.storage.azure_client.generate_blob_sas")
    def test_with_account_key_uses_generate_blob_sas(self, mock_gen_sas, azure_client_key, mock_blob_service):
        mock_gen_sas.return_value = "sas-token-here"
        url = azure_client_key.generate_presigned_url("file.txt")
        assert "sas-token-here" in url
        call_kwargs = mock_gen_sas.call_args.kwargs
        assert call_kwargs["account_key"] == "testkey123"

    @patch("solace_agent_mesh.services.platform.storage.azure_client.generate_blob_sas")
    def test_without_account_key_uses_delegation_key(self, mock_gen_sas, azure_client_workload_identity, mock_blob_service):
        mock_delegation_key = MagicMock()
        mock_blob_service["service"].get_user_delegation_key.return_value = mock_delegation_key
        mock_gen_sas.return_value = "delegation-sas-token"
        url = azure_client_workload_identity.generate_presigned_url("file.txt")
        assert "delegation-sas-token" in url
        call_kwargs = mock_gen_sas.call_args.kwargs
        assert "user_delegation_key" in call_kwargs
        assert call_kwargs["user_delegation_key"] is mock_delegation_key

    @patch("solace_agent_mesh.services.platform.storage.azure_client.generate_blob_sas")
    def test_url_format(self, mock_gen_sas, azure_client_key, mock_blob_service):
        mock_gen_sas.return_value = "sas-token"
        url = azure_client_key.generate_presigned_url("path/file.txt")
        assert "testaccount" in url
        assert "test-container" in url
        assert "path/file.txt" in url


class TestAzurePublicUrl:
    def test_url_format(self, azure_client_conn_str):
        url = azure_client_conn_str.get_public_url("ns/file.zip")
        assert url == "https://testaccount.blob.core.windows.net/test-container/ns/file.zip"
