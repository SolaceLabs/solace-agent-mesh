"""
S3 implementation of App Storage Service.

Used for production deployments where files are stored in S3.
"""

import asyncio
import json
import logging
import mimetypes
from pathlib import Path
from typing import Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError, NoCredentialsError

from .base import AppStorageService

logger = logging.getLogger(__name__)


class S3AppStorageService(AppStorageService):
    """
    S3 implementation for app storage.

    Directory structure in S3:
    s3://{bucket}/{prefix}/{user_id}/{app_id}/
    ├── latest/           # Current workspace build (preview)
    │   ├── dist/         # Built files from workspace
    │   └── VERSION       # Version metadata
    └── versions/         # Deployed version snapshots
        ├── 0.0.1/
        ├── 0.0.2/
        └── ...

    Supports any S3-compatible storage (AWS S3, MinIO, etc.)
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "apps",
        s3_client: Optional[BaseClient] = None,
        **kwargs,
    ):
        """
        Initialize S3 app storage.

        Args:
            bucket: S3 bucket name
            prefix: Key prefix for all app files (default: "apps")
            s3_client: Optional pre-configured S3 client
            **kwargs: Additional arguments for boto3 client
        """
        if not bucket:
            raise ValueError("bucket cannot be empty for S3AppStorageService")

        self.bucket = bucket
        self.prefix = prefix.strip("/")

        if s3_client is None:
            try:
                self.s3 = boto3.client("s3", **kwargs)
            except NoCredentialsError as e:
                logger.error("AWS credentials not found")
                raise ValueError(
                    "AWS credentials not found. Please configure credentials."
                ) from e
        else:
            self.s3 = s3_client

        # Verify bucket access
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            logger.info(f"S3AppStorageService initialized. Bucket: {self.bucket}, Prefix: {self.prefix}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise ValueError(f"S3 bucket '{self.bucket}' does not exist") from e
            elif error_code == "403":
                raise ValueError(f"Access denied to S3 bucket '{self.bucket}'") from e
            else:
                raise ValueError(f"Failed to access S3 bucket '{self.bucket}': {e}") from e

    def _get_latest_prefix(self, user_id: str, app_id: str) -> str:
        """Get the S3 key prefix for an app's latest (preview) directory."""
        return f"{self.prefix}/{user_id}/{app_id}/latest"

    def _get_key_prefix(self, user_id: str, app_id: str) -> str:
        """Get the S3 key prefix for an app's latest dist files."""
        return f"{self._get_latest_prefix(user_id, app_id)}/dist"

    def _get_file_key(self, user_id: str, app_id: str, path: str) -> str:
        """Get the full S3 key for a file in latest/dist/."""
        return f"{self._get_key_prefix(user_id, app_id)}/{path}"

    async def sync_dist(
        self,
        user_id: str,
        app_id: str,
        dist_path: Path,
    ) -> None:
        """
        Sync dist/ directory to S3.

        Uploads all files from dist/, replacing existing files.
        """
        log_prefix = f"[S3AppStorage:Sync:{app_id}] "

        if not dist_path.exists():
            logger.warning(f"{log_prefix}Source dist path does not exist: {dist_path}")
            return

        key_prefix = self._get_key_prefix(user_id, app_id)

        # Delete existing files first
        await self._delete_prefix(key_prefix, log_prefix)

        # Upload all files
        file_count = 0
        for file_path in dist_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(dist_path)
            s3_key = f"{key_prefix}/{rel_path}"

            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

            # Determine cache control based on file type
            # Hashed assets can be cached forever, HTML should not be cached
            if "assets/" in str(rel_path) or str(rel_path).endswith((".js", ".css")):
                cache_control = "public, max-age=31536000, immutable"
            else:
                cache_control = "no-cache, no-store, must-revalidate"

            def _upload(fp=file_path, key=s3_key, ct=content_type, cc=cache_control):
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=fp.read_bytes(),
                    ContentType=ct,
                    CacheControl=cc,
                )

            try:
                await asyncio.to_thread(_upload)
                file_count += 1
            except ClientError as e:
                logger.error(f"{log_prefix}Failed to upload {rel_path}: {e}")
                raise

        logger.info(f"{log_prefix}Synced {file_count} files to s3://{self.bucket}/{key_prefix}")

    async def _delete_prefix(self, prefix: str, log_prefix: str) -> None:
        """Delete all objects with the given prefix."""
        def _delete():
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                for obj in page.get("Contents", []):
                    objects_to_delete.append({"Key": obj["Key"]})

            if objects_to_delete:
                # Delete in batches of 1000 (S3 limit)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i + 1000]
                    self.s3.delete_objects(
                        Bucket=self.bucket,
                        Delete={"Objects": batch}
                    )

            return len(objects_to_delete)

        try:
            count = await asyncio.to_thread(_delete)
            if count > 0:
                logger.debug(f"{log_prefix}Deleted {count} existing files")
        except ClientError as e:
            logger.warning(f"{log_prefix}Error deleting existing files: {e}")

    async def get_file(
        self,
        user_id: str,
        app_id: str,
        path: str,
    ) -> Optional[bytes]:
        """Get a file from S3."""
        log_prefix = f"[S3AppStorage:Get:{app_id}] "

        s3_key = self._get_file_key(user_id, app_id, path)

        def _get():
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            return response["Body"].read()

        try:
            content = await asyncio.to_thread(_get)
            logger.debug(f"{log_prefix}Read {len(content)} bytes from {path}")
            return content
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"{log_prefix}File not found: {path}")
                return None
            logger.error(f"{log_prefix}Failed to read {path}: {e}")
            return None

    async def list_files(
        self,
        user_id: str,
        app_id: str,
        prefix: str = "",
    ) -> list[str]:
        """List files in the app's dist/."""
        key_prefix = self._get_key_prefix(user_id, app_id)
        if prefix:
            key_prefix = f"{key_prefix}/{prefix}"

        def _list():
            files = []
            paginator = self.s3.get_paginator("list_objects_v2")
            base_prefix = self._get_key_prefix(user_id, app_id)

            pages = paginator.paginate(Bucket=self.bucket, Prefix=key_prefix)
            for page in pages:
                for obj in page.get("Contents", []):
                    # Get relative path from dist/
                    rel_path = obj["Key"][len(base_prefix) + 1:]  # +1 for trailing /
                    files.append(rel_path)

            return sorted(files)

        try:
            return await asyncio.to_thread(_list)
        except ClientError as e:
            logger.error(f"[S3AppStorage:List:{app_id}] Error listing files: {e}")
            return []

    async def delete_app(
        self,
        user_id: str,
        app_id: str,
    ) -> None:
        """Delete all files for an app."""
        log_prefix = f"[S3AppStorage:Delete:{app_id}] "

        # Delete everything under the app prefix (including dist/)
        app_prefix = f"{self.prefix}/{user_id}/{app_id}"
        await self._delete_prefix(app_prefix, log_prefix)
        logger.info(f"{log_prefix}Deleted app storage")

    async def app_exists(
        self,
        user_id: str,
        app_id: str,
    ) -> bool:
        """Check if an app has stored files."""
        key_prefix = self._get_key_prefix(user_id, app_id)

        def _check():
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=key_prefix,
                MaxKeys=1,
            )
            return response.get("KeyCount", 0) > 0

        try:
            return await asyncio.to_thread(_check)
        except ClientError:
            return False

    def _get_version_key_prefix(self, user_id: str, app_id: str, version: str) -> str:
        """Get the S3 key prefix for a specific version."""
        return f"{self.prefix}/{user_id}/{app_id}/versions/{version}"

    async def deploy_version(
        self,
        user_id: str,
        app_id: str,
        version: str,
        source_path: Path,
    ) -> None:
        """Deploy a specific version from local dist/ to versioned storage."""
        log_prefix = f"[S3AppStorage:Deploy:{app_id}:{version}] "

        if not source_path.exists():
            logger.warning(f"{log_prefix}Source path does not exist: {source_path}")
            return

        version_prefix = self._get_version_key_prefix(user_id, app_id, version)

        # Delete existing version first
        await self._delete_prefix(version_prefix, log_prefix)

        # Upload all files
        file_count = 0
        for file_path in source_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(source_path)
            s3_key = f"{version_prefix}/{rel_path}"

            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

            # Cache control for deployed versions (can be cached longer)
            if "assets/" in str(rel_path) or str(rel_path).endswith((".js", ".css")):
                cache_control = "public, max-age=31536000, immutable"
            else:
                cache_control = "public, max-age=3600"

            def _upload(fp=file_path, key=s3_key, ct=content_type, cc=cache_control):
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=fp.read_bytes(),
                    ContentType=ct,
                    CacheControl=cc,
                )

            try:
                await asyncio.to_thread(_upload)
                file_count += 1
            except ClientError as e:
                logger.error(f"{log_prefix}Failed to upload {rel_path}: {e}")
                raise

        logger.info(f"{log_prefix}Deployed {file_count} files to s3://{self.bucket}/{version_prefix}")

    async def get_version_file(
        self,
        user_id: str,
        app_id: str,
        version: str,
        path: str,
    ) -> Optional[bytes]:
        """Get a file from a specific deployed version."""
        log_prefix = f"[S3AppStorage:GetVersion:{app_id}:{version}] "

        s3_key = f"{self._get_version_key_prefix(user_id, app_id, version)}/{path}"

        def _get():
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            return response["Body"].read()

        try:
            content = await asyncio.to_thread(_get)
            logger.debug(f"{log_prefix}Read {len(content)} bytes from {path}")
            return content
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"{log_prefix}File not found: {path}")
                return None
            logger.error(f"{log_prefix}Failed to read {path}: {e}")
            return None

    async def version_exists(
        self,
        user_id: str,
        app_id: str,
        version: str,
    ) -> bool:
        """Check if a specific version exists in storage."""
        version_prefix = self._get_version_key_prefix(user_id, app_id, version)

        def _check():
            response = self.s3.list_objects_v2(
                Bucket=self.bucket,
                Prefix=version_prefix,
                MaxKeys=1,
            )
            return response.get("KeyCount", 0) > 0

        try:
            return await asyncio.to_thread(_check)
        except ClientError:
            return False

    async def list_versions(
        self,
        user_id: str,
        app_id: str,
    ) -> list[str]:
        """List all deployed versions for an app."""
        versions_prefix = f"{self.prefix}/{user_id}/{app_id}/versions/"

        def _list():
            versions = set()
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=versions_prefix, Delimiter="/")

            for page in pages:
                for prefix_obj in page.get("CommonPrefixes", []):
                    # Extract version from prefix like "apps/user/app/versions/1.2.3/"
                    version = prefix_obj["Prefix"].rstrip("/").split("/")[-1]
                    versions.add(version)

            # Sort by semver (newest first)
            versions_list = list(versions)
            try:
                versions_list.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
            except (ValueError, AttributeError):
                versions_list.sort(reverse=True)
            return versions_list

        try:
            return await asyncio.to_thread(_list)
        except ClientError as e:
            logger.error(f"[S3AppStorage:ListVersions:{app_id}] Error listing versions: {e}")
            return []

    def _get_preview_version_key(self, user_id: str, app_id: str) -> str:
        """Get the S3 key for an app's preview VERSION file."""
        return f"{self._get_latest_prefix(user_id, app_id)}/VERSION"

    async def sync_preview_metadata(
        self,
        user_id: str,
        app_id: str,
        version_file_path: Path,
    ) -> None:
        """
        Sync the VERSION file to S3 preview storage.

        Copies the VERSION file from workspace to S3 so that
        preview version info is available even without workspace.
        """
        log_prefix = f"[S3AppStorage:SyncMeta:{app_id}] "

        if not version_file_path.exists():
            logger.debug(f"{log_prefix}VERSION file does not exist: {version_file_path}")
            return

        s3_key = self._get_preview_version_key(user_id, app_id)

        def _upload():
            self.s3.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=version_file_path.read_bytes(),
                ContentType="application/json",
                CacheControl="no-cache, no-store, must-revalidate",
            )

        try:
            await asyncio.to_thread(_upload)
            logger.info(f"{log_prefix}Synced VERSION file to s3://{self.bucket}/{s3_key}")
        except ClientError as e:
            logger.error(f"{log_prefix}Failed to upload VERSION: {e}")
            raise

    async def get_preview_version(
        self,
        user_id: str,
        app_id: str,
    ) -> Optional[dict]:
        """
        Get the preview VERSION file contents from S3.

        Returns:
            Parsed VERSION file contents as dict, or None if not found
        """
        log_prefix = f"[S3AppStorage:GetVersion:{app_id}] "

        s3_key = self._get_preview_version_key(user_id, app_id)

        def _get():
            response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            return json.loads(response["Body"].read().decode("utf-8"))

        try:
            version_data = await asyncio.to_thread(_get)
            logger.debug(f"{log_prefix}Read VERSION: {version_data.get('version')}")
            return version_data
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"{log_prefix}VERSION file not found in storage")
                return None
            logger.warning(f"{log_prefix}Failed to read VERSION: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"{log_prefix}Failed to parse VERSION JSON: {e}")
            return None
