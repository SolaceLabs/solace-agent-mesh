"""S3-compatible storage client (AWS S3, SeaweedFS, MinIO)."""

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .base import ObjectStorageClient, StorageObject
from .exceptions import (
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
)

log = logging.getLogger(__name__)

_ERROR_CODE_MAP = {
    "NoSuchKey": StorageNotFoundError,
    "404": StorageNotFoundError,
    "AccessDenied": StoragePermissionError,
    "403": StoragePermissionError,
    "InvalidAccessKeyId": StoragePermissionError,
    "SignatureDoesNotMatch": StoragePermissionError,
    "EndpointConnectionError": StorageConnectionError,
}


class S3StorageClient(ObjectStorageClient):
    """S3-compatible object storage client."""

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        self._bucket = bucket_name
        self._region = region
        self._endpoint_url = endpoint_url

        kwargs: dict = {
            "config": Config(
                region_name=region,
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if aws_access_key_id and aws_secret_access_key:
            kwargs["aws_access_key_id"] = aws_access_key_id
            kwargs["aws_secret_access_key"] = aws_secret_access_key
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        self._client = boto3.client("s3", **kwargs)

    def put_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            params: dict = {
                "Bucket": self._bucket,
                "Key": key,
                "Body": content,
                "ContentType": content_type,
            }
            if metadata:
                params["Metadata"] = metadata
            self._client.put_object(**params)
            return key
        except ClientError as e:
            raise self._translate_error(e, key) from e

    def get_object(self, key: str) -> StorageObject:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return StorageObject(
                content=response["Body"].read(),
                content_type=response.get("ContentType", "application/octet-stream"),
                metadata=response.get("Metadata", {}),
            )
        except ClientError as e:
            raise self._translate_error(e, key) from e

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            raise self._translate_error(e, key) from e

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    self._client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": delete_keys},
                    )
                    deleted += len(delete_keys)
            return deleted
        except ClientError as e:
            raise self._translate_error(e) from e

    def get_public_url(self, key: str) -> str:
        if self._endpoint_url:
            return f"{self._endpoint_url.rstrip('/')}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"

    def _translate_error(self, error: ClientError, key: str | None = None) -> StorageError:
        code = error.response.get("Error", {}).get("Code", "")
        exc_cls = _ERROR_CODE_MAP.get(code, StorageError)
        return exc_cls(str(error), key=key, cause=error)
