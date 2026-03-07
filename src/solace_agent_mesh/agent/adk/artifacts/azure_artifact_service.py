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

    Stores artifacts in an Azure container with a structured key format:
    {app_name}/{user_id}/{session_id_or_user}/{filename}/{version}

    Required Azure Permissions:
    The identity must have the following minimum permissions on the container:
    - Storage Blob Data Reader: Read artifacts from the container
    - Storage Blob Data Contributor: Store and delete artifacts in the container

    Example Role Assignment (replace values with actual resource IDs):
    az role assignment create \\
        --role "Storage Blob Data Contributor" \\
        --assignee <principal-id> \\
        --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>/blobServices/default/containers/<container>
    """

    def __init__(
        self,
        container_name: str,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
    ):
        """
        Args:
            container_name: The name of the Azure Blob container to use.
            connection_string: Optional Azure Storage connection string.
            account_name: Optional storage account name (used with account_key).
            account_key: Optional storage account key (used with account_name).

        Raises:
            ValueError: If container_name is not provided or container doesn't exist.
        """
        if not container_name:
            raise ValueError("container_name cannot be empty for AzureArtifactService")

        self.container_name = container_name

        if connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
        elif account_name and account_key:
            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key,
            )
        elif account_name:
            from azure.identity import DefaultAzureCredential

            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        else:
            raise ValueError(
                "Either 'connection_string', 'account_name' + 'account_key', or "
                "'account_name' alone (for workload identity) must be provided for AzureArtifactService."
            )

        self.account_name = account_name or self.blob_service_client.account_name
        self.container_client = self.blob_service_client.get_container_client(
            container_name
        )

        try:
            self.container_client.get_container_properties()
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
                logger.error(
                    "Access denied to Azure container '%s'", self.container_name
                )
                raise ValueError(
                    f"Access denied to Azure container '{self.container_name}'"
                ) from e
            else:
                logger.error(
                    "Failed to access Azure container '%s': %s", self.container_name, e
                )
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
        """Constructs the blob key for an artifact."""
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

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

            def _upload_blob():
                blob_client = self.container_client.get_blob_client(object_key)
                blob_client.upload_blob(
                    data=artifact.inline_data.data,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type=artifact.inline_data.mime_type,
                    ),
                    metadata={
                        "original_filename": filename,
                        "user_id": user_id,
                        "session_id": session_id,
                        "version": str(version),
                    },
                )

            await asyncio.to_thread(_upload_blob)

            logger.info(
                "%sSaved artifact '%s' version %d successfully to blob key: %s",
                log_prefix,
                filename,
                version,
                object_key,
            )
            return version

        except HttpResponseError as e:
            logger.error(
                "%sFailed to save artifact '%s' version %d to Azure: %s",
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
            logger.debug("%sLoading latest version: %d", log_prefix, load_version)
        else:
            logger.debug("%sLoading specified version: %d", log_prefix, load_version)

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _download_blob():
                blob_client = self.container_client.get_blob_client(object_key)
                downloader = blob_client.download_blob()
                data = downloader.readall()
                content_type = downloader.properties.content_settings.content_type
                return data, content_type

            data, content_type = await asyncio.to_thread(_download_blob)
            mime_type = content_type or "application/octet-stream"

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
                "%sFailed to load artifact '%s' version %d from Azure: %s",
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

            def _list_session_blobs():
                return list(
                    self.container_client.list_blobs(name_starts_with=session_prefix)
                )

            session_blobs = await asyncio.to_thread(_list_session_blobs)
            for blob in session_blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    filename = parts[3]
                    filenames.add(filename)
        except HttpResponseError as e:
            logger.warning(
                "%sError listing session blobs with prefix '%s': %s",
                log_prefix,
                session_prefix,
                e,
            )

        user_prefix = f"{app_name}/{user_id}/user/"
        try:

            def _list_user_blobs():
                return list(
                    self.container_client.list_blobs(name_starts_with=user_prefix)
                )

            user_blobs = await asyncio.to_thread(_list_user_blobs)
            for blob in user_blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    filename = parts[3]
                    filenames.add(f"user:{filename}")
        except HttpResponseError as e:
            logger.warning(
                "%sError listing user blobs with prefix '%s': %s",
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

                def _delete_blob():
                    blob_client = self.container_client.get_blob_client(object_key)
                    blob_client.delete_blob()

                await asyncio.to_thread(_delete_blob)
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
        log_prefix = f"[AzureArtifact:ListVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        versions = []

        try:

            def _list_blobs():
                return list(self.container_client.list_blobs(name_starts_with=prefix))

            blobs = await asyncio.to_thread(_list_blobs)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    try:
                        version = int(parts[4])
                        versions.append(version)
                    except ValueError:
                        continue

        except HttpResponseError as e:
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
        log_prefix = f"[AzureArtifact:ListArtifactVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        app_name = app_name.strip("/")

        prefix = self._get_object_key(app_name, user_id, session_id, filename, "")
        artifact_versions = []

        try:

            def _list_blobs():
                return list(self.container_client.list_blobs(name_starts_with=prefix))

            blobs = await asyncio.to_thread(_list_blobs)
            for blob in blobs:
                parts = blob.name.split("/")
                if len(parts) >= 5:
                    try:
                        version_num = int(parts[4])

                        def _get_blob_properties():
                            blob_client = self.container_client.get_blob_client(
                                blob.name
                            )
                            return blob_client.get_blob_properties()

                        properties = await asyncio.to_thread(_get_blob_properties)

                        mime_type = (
                            properties.content_settings.content_type
                            or "application/octet-stream"
                        )
                        create_time = properties.last_modified.timestamp()

                        artifact_version = ArtifactVersion(
                            version=version_num,
                            canonical_uri=f"azure://{self.account_name}/{self.container_name}/{blob.name}",
                            mime_type=mime_type,
                            create_time=create_time,
                            custom_metadata={},
                        )
                        artifact_versions.append(artifact_version)

                    except (ValueError, HttpResponseError) as e:
                        logger.warning(
                            "%sFailed to process version from key '%s': %s",
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
            logger.debug("%sGetting latest version: %d", log_prefix, load_version)
        else:
            logger.debug("%sGetting specified version: %d", log_prefix, load_version)

        object_key = self._get_object_key(
            app_name, user_id, session_id, filename, load_version
        )

        try:

            def _get_blob_properties():
                blob_client = self.container_client.get_blob_client(object_key)
                return blob_client.get_blob_properties()

            properties = await asyncio.to_thread(_get_blob_properties)

            mime_type = (
                properties.content_settings.content_type or "application/octet-stream"
            )
            create_time = properties.last_modified.timestamp()

            artifact_version = ArtifactVersion(
                version=load_version,
                canonical_uri=f"azure://{self.account_name}/{self.container_name}/{object_key}",
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
            logger.debug("%sArtifact version not found: %s", log_prefix, object_key)
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
