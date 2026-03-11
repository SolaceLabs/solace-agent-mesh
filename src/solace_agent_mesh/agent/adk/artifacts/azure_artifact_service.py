"""
An ADK ArtifactService implementation using Azure Blob Storage.
"""

import asyncio
import logging
import unicodedata

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings
from google.adk.artifacts import BaseArtifactService
from google.adk.artifacts.base_artifact_service import ArtifactVersion
from google.genai import types as adk_types
from typing_extensions import override

logger = logging.getLogger(__name__)


class AzureArtifactService(BaseArtifactService):
    """
    An artifact service implementation using Azure Blob Storage.

    Stores artifacts in an Azure Blob container with a structured key format:
    {app_name}/{user_id}/{session_id_or_user}/{filename}/{version}

    Required Azure Permissions:
    The identity must have the following minimum permissions on the container:
    - Storage Blob Data Reader: Read artifacts
    - Storage Blob Data Contributor: Write and delete artifacts

    Authentication is supported via:
    - Connection string (AZURE_STORAGE_CONNECTION_STRING)
    - Account name + account key (AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY)
    - Workload identity / managed identity (account_name only, no key)
    """

    def __init__(
        self,
        container_name: str,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
    ):
        if not container_name:
            raise ValueError("container_name cannot be empty for AzureArtifactService")

        self.container_name = container_name

        if connection_string:
            self._service_client = BlobServiceClient.from_connection_string(connection_string)
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self._service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        elif account_name:
            from azure.identity import DefaultAzureCredential

            account_url = f"https://{account_name}.blob.core.windows.net"
            self._service_client = BlobServiceClient(
                account_url=account_url, credential=DefaultAzureCredential()
            )
        else:
            raise ValueError(
                "Azure Blob Storage requires either connection_string, "
                "account_name + account_key, or account_name (for workload identity)"
            )

        self._container_client = self._service_client.get_container_client(container_name)

        try:
            self._container_client.get_container_properties()
            logger.info(
                "AzureArtifactService initialized successfully. Container: %s",
                self.container_name,
            )
        except ResourceNotFoundError as e:
            logger.error("Azure container '%s' does not exist", self.container_name)
            raise ValueError(
                f"Azure container '{self.container_name}' does not exist"
            ) from e
        except HttpResponseError as e:
            if e.status_code == 403:
                logger.error("Access denied to Azure container '%s'", self.container_name)
                raise ValueError(
                    f"Access denied to Azure container '{self.container_name}'"
                ) from e
            logger.error("Failed to access Azure container '%s': %s", self.container_name, e)
            raise ValueError(
                f"Failed to access Azure container '{self.container_name}': {e}"
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
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        if self._file_has_user_namespace(filename):
            filename_clean = filename.split(":", 1)[1]
            return f"{app_name}/{user_id}/user/{filename_clean}/{version}"
        return f"{app_name}/{user_id}/{session_id}/{filename}/{version}"

    def _normalize_filename_unicode(self, filename: str) -> str:
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
        log_prefix = f"[AzureArtifact:Save:{filename}] "

        if not artifact.inline_data or artifact.inline_data.data is None:
            raise ValueError("Artifact Part has no inline_data to save.")

        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

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

            def _upload():
                blob_client = self._container_client.get_blob_client(object_key)
                blob_client.upload_blob(
                    artifact.inline_data.data,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type=artifact.inline_data.mime_type
                    ),
                    metadata={
                        "original_filename": filename,
                        "user_id": user_id,
                        "session_id": session_id,
                        "version": str(version),
                    },
                )

            await asyncio.to_thread(_upload)

            logger.info(
                "%sSaved artifact '%s' version %d successfully to key: %s",
                log_prefix,
                filename,
                version,
                object_key,
            )
            return version

        except HttpResponseError as e:
            logger.error(
                "%sFailed to save artifact '%s' version %d: %s",
                log_prefix,
                filename,
                version,
                e,
            )
            raise OSError(
                f"Failed to save artifact version {version} to Azure: {e}"
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
        log_prefix = f"[AzureArtifact:Load:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

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

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _download():
                blob_client = self._container_client.get_blob_client(object_key)
                download = blob_client.download_blob()
                data = download.readall()
                mime_type = (
                    download.properties.content_settings.content_type
                    or "application/octet-stream"
                )
                return data, mime_type

            data, mime_type = await asyncio.to_thread(_download)
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

        except ResourceNotFoundError:
            logger.debug("%sArtifact not found: %s", log_prefix, object_key)
            return None
        except HttpResponseError as e:
            logger.error(
                "%sFailed to load artifact '%s' version %d: %s",
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
        log_prefix = "[AzureArtifact:ListKeys] "
        filenames = set()
        app_name = app_name.strip("/")

        session_prefix = f"{app_name}/{user_id}/{session_id}/"
        try:

            def _list_session():
                return list(
                    self._container_client.list_blobs(name_starts_with=session_prefix)
                )

            blobs = await asyncio.to_thread(_list_session)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    filenames.add(parts[3])
        except HttpResponseError as e:
            logger.warning(
                "%sError listing session objects with prefix '%s': %s",
                log_prefix,
                session_prefix,
                e,
            )

        user_prefix = f"{app_name}/{user_id}/user/"
        try:

            def _list_user():
                return list(
                    self._container_client.list_blobs(name_starts_with=user_prefix)
                )

            blobs = await asyncio.to_thread(_list_user)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    filenames.add(f"user:{parts[3]}")
        except HttpResponseError as e:
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
        log_prefix = f"[AzureArtifact:Delete:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        versions = await self.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )

        if not versions:
            logger.debug("%sNo versions found to delete for artifact.", log_prefix)
            return

        for version in versions:
            object_key = self._get_object_key(
                app_name, user_id, session_id, filename, version
            )
            try:

                def _delete():
                    blob_client = self._container_client.get_blob_client(object_key)
                    blob_client.delete_blob()

                await asyncio.to_thread(_delete)
                logger.debug(
                    "%sDeleted version %d: %s", log_prefix, version, object_key
                )
            except HttpResponseError as e:
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
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        versions = []

        try:

            def _list():
                return list(
                    self._container_client.list_blobs(name_starts_with=prefix)
                )

            blobs = await asyncio.to_thread(_list)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    try:
                        versions.append(int(parts[4]))
                    except ValueError:
                        continue

        except HttpResponseError as e:
            logger.error(
                "[AzureArtifact:ListVersions:%s] Error listing with prefix '%s': %s",
                filename,
                prefix,
                e,
            )
            return []

        return sorted(versions)

    @override
    async def list_artifact_versions(
        self,
        *,
        app_name: str,
        user_id: str,
        filename: str,
        session_id: str,
    ) -> list[ArtifactVersion]:
        log_prefix = f"[AzureArtifact:ListArtifactVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        artifact_versions = []

        try:

            def _list():
                return list(
                    self._container_client.list_blobs(
                        name_starts_with=prefix, include=["metadata"]
                    )
                )

            blobs = await asyncio.to_thread(_list)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    try:
                        version_num = int(parts[4])
                        mime_type = (
                            blob.content_settings.content_type
                            if blob.content_settings
                            else "application/octet-stream"
                        ) or "application/octet-stream"
                        create_time = (
                            blob.last_modified.timestamp()
                            if blob.last_modified
                            else 0.0
                        )

                        artifact_versions.append(
                            ArtifactVersion(
                                version=version_num,
                                canonical_uri=f"azure://{self.container_name}/{blob.name}",
                                mime_type=mime_type,
                                create_time=create_time,
                                custom_metadata={},
                            )
                        )
                    except (ValueError, HttpResponseError) as e:
                        logger.warning(
                            "%sFailed to process version from blob '%s': %s",
                            log_prefix,
                            blob.name,
                            e,
                        )
                        continue

        except HttpResponseError as e:
            logger.error(
                "%sError listing versions with prefix '%s': %s",
                log_prefix,
                prefix,
                e,
            )
            return []

        artifact_versions.sort(key=lambda av: av.version)
        logger.debug(
            "%sFound %d artifact versions", log_prefix, len(artifact_versions)
        )
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
        log_prefix = f"[AzureArtifact:GetArtifactVersion:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

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

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _get_properties():
                blob_client = self._container_client.get_blob_client(object_key)
                return blob_client.get_blob_properties()

            properties = await asyncio.to_thread(_get_properties)

            mime_type = (
                properties.content_settings.content_type
                if properties.content_settings
                else "application/octet-stream"
            ) or "application/octet-stream"
            create_time = (
                properties.last_modified.timestamp()
                if properties.last_modified
                else 0.0
            )

            artifact_version = ArtifactVersion(
                version=load_version,
                canonical_uri=f"azure://{self.container_name}/{object_key}",
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

        except ResourceNotFoundError:
            logger.debug(
                "%sArtifact version not found: %s", log_prefix, object_key
            )
            return None
        except HttpResponseError as e:
            logger.error(
                "%sFailed to get metadata for artifact '%s' version %d: %s",
                log_prefix,
                filename,
                load_version,
                e,
            )
            return None
