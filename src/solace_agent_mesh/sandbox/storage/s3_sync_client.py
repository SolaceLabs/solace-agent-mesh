"""S3-compatible sync client (AWS S3, SeaweedFS, MinIO)."""

import logging

import boto3
from botocore.config import Config

from .base import SyncObjectMeta, ToolSyncStorageClient

log = logging.getLogger(__name__)


class S3SyncClient(ToolSyncStorageClient):
    """Read-only S3-compatible storage client for tool sync."""

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ):
        self._bucket = bucket_name

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
        if aws_session_token:
            kwargs["aws_session_token"] = aws_session_token
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        self._client = boto3.client("s3", **kwargs)

    def list_objects(self, prefix: str) -> list[SyncObjectMeta]:
        result: list[SyncObjectMeta] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                result.append(
                    SyncObjectMeta(
                        key=obj["Key"],
                        etag=obj["ETag"].strip('"'),
                        size=obj["Size"],
                    )
                )
        return result

    def download_object(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()
