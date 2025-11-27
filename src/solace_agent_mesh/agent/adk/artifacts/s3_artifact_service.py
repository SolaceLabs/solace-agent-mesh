"""
An ADK ArtifactService implementation using Amazon S3 compatible storage.
"""

import asyncio
import logging
import unicodedata

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from google.adk.artifacts import BaseArtifactService
from google.adk.artifacts.base_artifact_service import ArtifactVersion
from google.genai import types as adk_types
from typing_extensions import override

logger = logging.getLogger(__name__)


class S3ArtifactService(BaseArtifactService):
    """
    An artifact service implementation using Amazon S3 compatible storage.

    Stores artifacts in an S3-compatible bucket with a structured key format:
    {app_name}/{user_id}/{session_id_or_user}/{filename}/{version}

    Supports AWS S3 and S3-compatible APIs like MinIO.

    Required S3 Permissions:
    The IAM user or role must have the following minimum permissions for the specific bucket:
    - s3:GetObject: Read artifacts from the bucket
    - s3:PutObject: Store new artifacts to the bucket
    - s3:DeleteObject: Delete artifacts from the bucket

    Example IAM Policy (replace 'your-bucket-name' with actual bucket):
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": "arn:aws:s3:::your-bucket-name/*"
            },
            {
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": "arn:aws:s3:::your-bucket-name"
            }
        ]
    }
    """

    def __init__(
        self,
        bucket_name: str,
        s3_client: BaseClient | None = None,
        **kwargs,
    ):
        """
        Args:
            bucket_name: The name of the S3 bucket to use.
            s3_client: Optional pre-configured S3 client. If None, creates a new client.
            **kwargs: Optional parameters for boto3 client configuration.

        Raises:
            ValueError: If bucket_name is not provided.
            NoCredentialsError: If AWS credentials are not available.
        """
        if not bucket_name:
            raise ValueError("bucket_name cannot be empty for S3ArtifactService")

        self.bucket_name = bucket_name

        if s3_client is None:
            try:
                self.s3 = boto3.client("s3", **kwargs)
            except NoCredentialsError as e:
                logger.error("AWS credentials not found. Please configure credentials.")
                raise ValueError(
                    "AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables or configure AWS credentials."
                ) from e
        else:
            self.s3 = s3_client

        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(
                "S3ArtifactService initialized successfully. Bucket: %s",
                self.bucket_name,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                logger.error("S3 bucket '%s' does not exist", self.bucket_name)
                raise ValueError(
                    f"S3 bucket '{self.bucket_name}' does not exist"
                ) from e
            elif error_code == "403":
                logger.error("Access denied to S3 bucket '%s'", self.bucket_name)
                raise ValueError(
                    f"Access denied to S3 bucket '{self.bucket_name}'"
                ) from e
            else:
                logger.error("Failed to access S3 bucket '%s': %s", self.bucket_name, e)
                raise ValueError(
                    f"Failed to access S3 bucket '{self.bucket_name}': {e}"
                ) from e

    def _file_has_user_namespace(self, filename: str) -> bool:
        return filename.startswith("user:")

    def _get_object_key(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        version: int | str,
    ) -> str:
        """Constructs the S3 object key for an artifact."""
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        if self._file_has_user_namespace(filename):
            filename_clean = filename.split(":", 1)[1]
            return f"{app_name}/{user_id}/user/{filename_clean}/{version}"
        return f"{app_name}/{user_id}/{session_id}/{filename}/{version}"

    def _normalize_filename_unicode(self, filename: str) -> str:
        """Normalizes Unicode characters in a filename to their standard form."""
        return unicodedata.normalize("NFKC", filename)

    @override
    async def save_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: adk_types.Part,
    ) -> int:
        log_prefix = f"[S3Artifact:Save:{filename}] "

        if not artifact.inline_data or artifact.inline_data.data is None:
            raise ValueError("Artifact Part has no inline_data to save.")

        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        # Get existing versions to determine next version number
        versions = await self.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        version = 0 if not versions else max(versions) + 1

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, version
        )

        try:

            def _put_object():
                return self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=artifact.inline_data.data,
                    ContentType=artifact.inline_data.mime_type,
                    Metadata={
                        "original_filename": filename,
                        "user_id": user_id,
                        "session_id": session_id,
                        "version": str(version),
                    },
                )

            await asyncio.to_thread(_put_object)

            logger.info(
                "%sSaved artifact '%s' version %d successfully to S3 key: %s",
                log_prefix,
                filename,
                version,
                object_key,
            )
            return version

        except ClientError as e:
            logger.error(
                "%sFailed to save artifact '%s' version %d to S3: %s",
                log_prefix,
                filename,
                version,
                e,
            )
            raise OSError(
                f"Failed to save artifact version {version} to S3: {e}"
            ) from e
        except BotoCoreError as e:
            logger.error(
                "%sBotoCore error saving artifact '%s' version %d: %s",
                log_prefix,
                filename,
                version,
                e,
            )
            raise OSError(
                f"BotoCore error saving artifact version {version}: {e}"
            ) from e

    @override
    async def load_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        version: int | None = None,
    ) -> adk_types.Part | None:
        log_prefix = f"[S3Artifact:Load:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        load_version = version
        if load_version is None:
            versions = await self.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
            )
            if not versions:
                logger.debug("%sNo versions found for artifact.", log_prefix)
                return None
            load_version = max(versions)
            logger.debug("%sLoading latest version: %d", log_prefix, load_version)
        else:
            logger.debug("%sLoading specified version: %d", log_prefix, load_version)

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _get_object():
                return self.s3.get_object(Bucket=self.bucket_name, Key=object_key)

            response = await asyncio.to_thread(_get_object)
            data = response["Body"].read()
            mime_type = response.get("ContentType", "application/octet-stream")

            artifact_part = adk_types.Part.from_bytes(data=data, mime_type=mime_type)

            logger.info(
                "%sLoaded artifact '%s' version %d successfully (%d bytes, %s)",
                log_prefix,
                filename,
                load_version,
                len(data),
                mime_type,
            )
            return artifact_part

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug("%sArtifact not found: %s", log_prefix, object_key)
                return None
            else:
                logger.error(
                    "%sFailed to load artifact '%s' version %d from S3: %s",
                    log_prefix,
                    filename,
                    load_version,
                    e,
                )
                return None
        except BotoCoreError as e:
            logger.error(
                "%sBotoCore error loading artifact '%s' version %d: %s",
                log_prefix,
                filename,
                load_version,
                e,
            )
            return None

    @override
    async def list_artifact_keys(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> list[str]:
        log_prefix = "[S3Artifact:ListKeys] "
        filenames = set()
        app_name = app_name.strip('/')

        session_prefix = f"{app_name}/{user_id}/{session_id}/"
        try:

            def _list_session_objects():
                paginator = self.s3.get_paginator("list_objects_v2")
                return paginator.paginate(
                    Bucket=self.bucket_name, Prefix=session_prefix
                )

            session_pages = await asyncio.to_thread(_list_session_objects)
            for page in session_pages:
                for obj in page.get("Contents", []):
                    parts = obj["Key"].split("/")
                    if len(parts) >= 5:  # scope/user/session/filename/version
                        filename = parts[3]
                        filenames.add(filename)
        except ClientError as e:
            logger.warning(
                "%sError listing session objects with prefix '%s': %s",
                log_prefix,
                session_prefix,
                e,
            )

        user_prefix = f"{app_name}/{user_id}/user/"
        try:

            def _list_user_objects():
                paginator = self.s3.get_paginator("list_objects_v2")
                return paginator.paginate(Bucket=self.bucket_name, Prefix=user_prefix)

            user_pages = await asyncio.to_thread(_list_user_objects)
            for page in user_pages:
                for obj in page.get("Contents", []):
                    parts = obj["Key"].split("/")
                    if len(parts) >= 5:  # scope/user/user/filename/version
                        filename = parts[3]
                        filenames.add(f"user:{filename}")
        except ClientError as e:
            logger.warning(
                "%sError listing user objects with prefix '%s': %s",
                log_prefix,
                user_prefix,
                e,
            )

        sorted_filenames = sorted(list(filenames))
        logger.debug("%sFound %d artifact keys.", log_prefix, len(sorted_filenames))
        return sorted_filenames

    @override
    async def delete_artifact(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> None:
        log_prefix = f"[S3Artifact:Delete:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        # Get all versions to delete
        versions = await self.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

        if not versions:
            logger.debug("%sNo versions found to delete for artifact.", log_prefix)
            return

        # Delete all versions
        for version in versions:
            object_key = self._get_object_key(
                app_name, user_id, session_id, filename, version
            )
            try:

                def _delete_object():
                    return self.s3.delete_object(
                        Bucket=self.bucket_name, Key=object_key
                    )

                await asyncio.to_thread(_delete_object)
                logger.debug(
                    "%sDeleted version %d: %s", log_prefix, version, object_key
                )
            except ClientError as e:
                logger.warning(
                    "%sFailed to delete version %d (%s): %s",
                    log_prefix,
                    version,
                    object_key,
                    e,
                )

        logger.info(
            "%sDeleted artifact '%s' (%d versions)",
            log_prefix,
            filename,
            len(versions),
        )

    @override
    async def list_versions(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> list[int]:
        log_prefix = f"[S3Artifact:ListVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        # Get the prefix for this specific artifact (without version)
        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        versions = []

        try:

            def _list_objects():
                paginator = self.s3.get_paginator("list_objects_v2")
                return paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            pages = await asyncio.to_thread(_list_objects)
            for page in pages:
                for obj in page.get("Contents", []):
                    parts = obj["Key"].split("/")
                    if len(parts) >= 5:  # scope/user/session_or_user/filename/version
                        try:
                            version = int(parts[4])
                            versions.append(version)
                        except ValueError:
                            continue  # Skip non-integer versions

        except ClientError as e:
            logger.error(
                "%sError listing versions with prefix '%s': %s",
                log_prefix,
                prefix,
                e,
            )
            return []

        sorted_versions = sorted(versions)
        logger.debug("%sFound versions: %s", log_prefix, sorted_versions)
        return sorted_versions

    @override
    async def list_artifact_versions(
        self,
        *,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: str,
    ) -> list[ArtifactVersion]:
        """Lists all versions and their metadata for a specific artifact."""
        log_prefix = f"[S3Artifact:ListArtifactVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        # Get the prefix for this specific artifact (without version)
        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        artifact_versions = []

        try:

            def _list_objects():
                paginator = self.s3.get_paginator("list_objects_v2")
                return paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            pages = await asyncio.to_thread(_list_objects)
            for page in pages:
                for obj in page.get("Contents", []):
                    parts = obj["Key"].split("/")
                    if len(parts) >= 5:  # scope/user/session_or_user/filename/version
                        try:
                            version_num = int(parts[4])

                            # Get object metadata
                            def _head_object():
                                return self.s3.head_object(
                                    Bucket=self.bucket_name, Key=obj["Key"]
                                )

                            metadata_response = await asyncio.to_thread(_head_object)

                            # Extract information
                            mime_type = metadata_response.get(
                                "ContentType", "application/octet-stream"
                            )
                            # S3 LastModified is a datetime object, convert to timestamp
                            create_time = obj.get("LastModified").timestamp()

                            # Create ArtifactVersion object
                            artifact_version = ArtifactVersion(
                                version=version_num,
                                canonical_uri=f"s3://{self.bucket_name}/{obj['Key']}",
                                mime_type=mime_type,
                                create_time=create_time,
                                custom_metadata={},
                            )
                            artifact_versions.append(artifact_version)

                        except (ValueError, ClientError) as e:
                            logger.warning(
                                "%sFailed to process version from key '%s': %s",
                                log_prefix,
                                obj["Key"],
                                e,
                            )
                            continue

        except ClientError as e:
            logger.error(
                "%sError listing versions with prefix '%s': %s",
                log_prefix,
                prefix,
                e,
            )
            return []

        # Sort by version number
        artifact_versions.sort(key=lambda av: av.version)
        logger.debug("%sFound %d artifact versions", log_prefix, len(artifact_versions))
        return artifact_versions

    @override
    async def get_artifact_version(
        self,
        *,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: str,
        version: int | None = None,
    ) -> ArtifactVersion | None:
        """Gets the metadata for a specific version of an artifact."""
        log_prefix = f"[S3Artifact:GetArtifactVersion:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip('/')

        # Determine which version to get
        load_version = version
        if load_version is None:
            versions = await self.list_versions(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
            )
            if not versions:
                logger.debug("%sNo versions found for artifact.", log_prefix)
                return None
            load_version = max(versions)
            logger.debug("%sGetting latest version: %d", log_prefix, load_version)
        else:
            logger.debug("%sGetting specified version: %d", log_prefix, load_version)

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _head_object():
                return self.s3.head_object(Bucket=self.bucket_name, Key=object_key)

            response = await asyncio.to_thread(_head_object)

            # Extract information
            mime_type = response.get("ContentType", "application/octet-stream")
            # S3 LastModified is a datetime object, convert to timestamp
            create_time = response.get("LastModified").timestamp()

            # Create and return ArtifactVersion object
            artifact_version = ArtifactVersion(
                version=load_version,
                canonical_uri=f"s3://{self.bucket_name}/{object_key}",
                mime_type=mime_type,
                create_time=create_time,
                custom_metadata={},
            )

            logger.info(
                "%sRetrieved metadata for artifact '%s' version %d",
                log_prefix,
                filename,
                load_version,
            )
            return artifact_version

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey" or error_code == "404":
                logger.debug(
                    "%sArtifact version not found: %s", log_prefix, object_key
                )
                return None
            else:
                logger.error(
                    "%sFailed to get metadata for artifact '%s' version %d: %s",
                    log_prefix,
                    filename,
                    load_version,
                    e,
                )
                return None
