"""
An ADK ArtifactService implementation using the local filesystem for storage.
"""

import asyncio
import json
import logging
import os
import shutil
import unicodedata

from google.adk.artifacts import BaseArtifactService
from google.adk.artifacts.base_artifact_service import ArtifactVersion
from google.genai import types as adk_types
from typing_extensions import override

logger = logging.getLogger(__name__)

METADATA_FILE_SUFFIX = ".meta"


class FilesystemArtifactService(BaseArtifactService):
    """
    An artifact service implementation using the local filesystem.

    Stores artifacts in a structured directory based on the effective app name
    (which represents the scope), user ID, session ID (or 'user' namespace),
    filename, and version. Metadata (like mime_type) is stored in a companion file.
    """

    def __init__(self, base_path: str):
        """
        Initializes the FilesystemArtifactService.

        Args:
            base_path: The root directory where all artifacts will be stored.

        Raises:
            ValueError: If base_path is not provided or cannot be created.
        """
        if not base_path:
            raise ValueError("base_path cannot be empty for FilesystemArtifactService")

        self.base_path = os.path.abspath(base_path)

        try:
            os.makedirs(self.base_path, exist_ok=True)
            logger.info(
                "Initialized FilesystemArtifactService. Base path: %s",
                self.base_path,
            )
        except OSError as e:
            logger.error(
                "Failed to create base directory '%s': %s",
                self.base_path,
                e,
            )
            raise ValueError(
                f"Could not create or access base_path '{self.base_path}': {e}"
            ) from e

    def _file_has_user_namespace(self, filename: str) -> bool:
        """Checks if the filename has a user namespace."""
        return filename.startswith("user:")

    def _get_artifact_dir(
        self, app_name: str, user_id: str, session_id: str, filename: str
    ) -> str:
        """
        Constructs the directory path for a specific artifact (all versions).
        The `app_name` is now the effective scope identifier, resolved by the caller.
        """
        app_name_sanitized = os.path.basename(app_name)
        user_id_sanitized = os.path.basename(user_id)
        session_id_sanitized = os.path.basename(session_id)
        filename_sanitized = os.path.basename(filename)

        if self._file_has_user_namespace(filename):
            filename_dir = os.path.basename(filename.split(":", 1)[1])
            return os.path.join(
                self.base_path,
                app_name_sanitized,
                user_id_sanitized,
                "user",
                filename_dir,
            )
        else:
            return os.path.join(
                self.base_path,
                app_name_sanitized,
                user_id_sanitized,
                session_id_sanitized,
                filename_sanitized,
            )

    def _get_version_path(self, artifact_dir: str, version: int) -> str:
        """Constructs the file path for a specific artifact version's data."""
        return os.path.join(artifact_dir, str(version))

    def _get_metadata_path(self, artifact_dir: str, version: int) -> str:
        """Constructs the file path for a specific artifact version's metadata."""
        return os.path.join(artifact_dir, f"{version}{METADATA_FILE_SUFFIX}")

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
        log_prefix = "[FSArtifact:Save] "

        filename = self._normalize_filename_unicode(filename)
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)
        try:
            await asyncio.to_thread(os.makedirs, artifact_dir, exist_ok=True)
        except OSError as e:
            logger.error(
                "%sFailed to create artifact directory '%s': %s",
                log_prefix,
                artifact_dir,
                e,
            )
            raise OSError(f"Could not create artifact directory: {e}") from e

        versions = await self.list_versions(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            filename=filename,
        )
        version = 0 if not versions else max(versions) + 1

        version_path = self._get_version_path(artifact_dir, version)
        metadata_path = self._get_metadata_path(artifact_dir, version)

        try:
            if not artifact.inline_data or artifact.inline_data.data is None:
                raise ValueError("Artifact Part has no inline_data to save.")

            metadata = {"mime_type": artifact.inline_data.mime_type}

            def _write_data_file():
                """Write artifact data and fsync to disk."""
                with open(version_path, "wb") as f:
                    f.write(artifact.inline_data.data)
                    f.flush()
                    os.fsync(f.fileno())
                logger.debug("%sWrote data to %s", log_prefix, version_path)

            def _write_metadata_file():
                """Write artifact metadata and fsync to disk."""
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f)
                    f.flush()
                    os.fsync(f.fileno())
                logger.debug("%sWrote metadata to %s", log_prefix, metadata_path)

            # Run file writes concurrently and wait for both to complete
            await asyncio.gather(
                asyncio.to_thread(_write_data_file),
                asyncio.to_thread(_write_metadata_file),
            )

            logger.info(
                "%sSaved artifact '%s' version %d successfully.",
                log_prefix,
                filename,
                version,
            )
            return version
        except (OSError, ValueError, TypeError) as e:
            logger.error(
                "%sFailed to save artifact '%s' version %d: %s",
                log_prefix,
                filename,
                version,
                e,
            )
            if await asyncio.to_thread(os.path.exists, version_path):
                await asyncio.to_thread(os.remove, version_path)
            if await asyncio.to_thread(os.path.exists, metadata_path):
                await asyncio.to_thread(os.remove, metadata_path)
            raise OSError(f"Failed to save artifact version {version}: {e}") from e

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
        log_prefix = f"[FSArtifact:Load:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)

        if not await asyncio.to_thread(os.path.isdir, artifact_dir):
            logger.debug("%sArtifact directory not found: %s", log_prefix, artifact_dir)
            return None

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

        version_path = self._get_version_path(artifact_dir, load_version)
        metadata_path = self._get_metadata_path(artifact_dir, load_version)

        if not await asyncio.to_thread(
            os.path.exists, version_path
        ) or not await asyncio.to_thread(os.path.exists, metadata_path):
            logger.warning(
                "%sData or metadata file missing for version %d.",
                log_prefix,
                load_version,
            )
            return None

        try:

            def _read_metadata_file():
                with open(metadata_path, encoding="utf-8") as f:
                    return json.load(f)

            metadata = await asyncio.to_thread(_read_metadata_file)
            mime_type = metadata.get("mime_type", "application/octet-stream")

            def _read_data_file():
                with open(version_path, "rb") as f:
                    return f.read()

            data_bytes = await asyncio.to_thread(_read_data_file)

            artifact_part = adk_types.Part.from_bytes(
                data=data_bytes, mime_type=mime_type
            )
            logger.info(
                "%sLoaded artifact '%s' version %d successfully (%d bytes, %s).",
                log_prefix,
                filename,
                load_version,
                len(data_bytes),
                mime_type,
            )
            return artifact_part

        except (OSError, json.JSONDecodeError) as e:
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
        log_prefix = "[FSArtifact:ListKeys] "
        filenames = set()
        app_name_sanitized = os.path.basename(app_name)
        user_id_sanitized = os.path.basename(user_id)
        session_id_sanitized = os.path.basename(session_id)

        session_base_dir = os.path.join(
            self.base_path, app_name_sanitized, user_id_sanitized, session_id_sanitized
        )
        if await asyncio.to_thread(os.path.isdir, session_base_dir):
            try:
                for item in await asyncio.to_thread(os.listdir, session_base_dir):
                    item_path = os.path.join(session_base_dir, item)
                    if await asyncio.to_thread(os.path.isdir, item_path):
                        filenames.add(item)
            except OSError as e:
                logger.warning(
                    "%sError listing session directory '%s': %s",
                    log_prefix,
                    session_base_dir,
                    e,
                )

        user_base_dir = os.path.join(
            self.base_path, app_name_sanitized, user_id_sanitized, "user"
        )
        if await asyncio.to_thread(os.path.isdir, user_base_dir):
            try:
                for item in await asyncio.to_thread(os.listdir, user_base_dir):
                    item_path = os.path.join(user_base_dir, item)
                    if await asyncio.to_thread(os.path.isdir, item_path):
                        filenames.add(f"user:{item}")
            except OSError as e:
                logger.warning(
                    "%sError listing user directory '%s': %s",
                    log_prefix,
                    user_base_dir,
                    e,
                )

        sorted_filenames = sorted(list(filenames))
        logger.debug("%sFound %d artifact keys.", log_prefix, len(sorted_filenames))
        return sorted_filenames

    @override
    async def delete_artifact(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> None:
        log_prefix = "[FSArtifact:Delete] "
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)

        if not await asyncio.to_thread(os.path.isdir, artifact_dir):
            logger.debug("%sArtifact directory not found: %s", log_prefix, artifact_dir)
            return

        try:
            await asyncio.to_thread(shutil.rmtree, artifact_dir)
            logger.info(
                "%sRemoved artifact directory and all its contents: %s",
                log_prefix,
                artifact_dir,
            )
        except OSError as e:
            logger.error(
                "%sError deleting artifact directory '%s'",
                log_prefix,
                e,
            )

    @override
    async def list_versions(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> list[int]:
        log_prefix = f"[FSArtifact:ListVersions:{filename}] "
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)
        versions = []

        if not await asyncio.to_thread(os.path.isdir, artifact_dir):
            logger.debug("%sArtifact directory not found: %s", log_prefix, artifact_dir)
            return []

        try:
            for item in await asyncio.to_thread(os.listdir, artifact_dir):
                if (
                    await asyncio.to_thread(
                        os.path.isfile, os.path.join(artifact_dir, item)
                    )
                    and item.isdigit()
                ):
                    versions.append(int(item))
        except OSError as e:
            logger.error("%sError listing versions in directory '%s'", log_prefix, e)
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
        log_prefix = f"[FSArtifact:ListArtifactVersions:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)
        artifact_versions = []

        if not await asyncio.to_thread(os.path.isdir, artifact_dir):
            logger.debug("%sArtifact directory not found: %s", log_prefix, artifact_dir)
            return []

        try:
            for item in await asyncio.to_thread(os.listdir, artifact_dir):
                item_path = os.path.join(artifact_dir, item)
                if await asyncio.to_thread(os.path.isfile, item_path) and item.isdigit():
                    version_num = int(item)
                    version_path = self._get_version_path(artifact_dir, version_num)
                    metadata_path = self._get_metadata_path(artifact_dir, version_num)

                    # Read metadata
                    try:

                        def _read_metadata():
                            with open(metadata_path, encoding="utf-8") as f:
                                return json.load(f)

                        metadata = await asyncio.to_thread(_read_metadata)
                        mime_type = metadata.get("mime_type", "application/octet-stream")

                        # Get file creation time
                        stat_info = await asyncio.to_thread(os.stat, version_path)
                        create_time = stat_info.st_ctime

                        # Create ArtifactVersion object
                        artifact_version = ArtifactVersion(
                            version=version_num,
                            canonical_uri=f"file://{version_path}",
                            mime_type=mime_type,
                            create_time=create_time,
                            custom_metadata={},
                        )
                        artifact_versions.append(artifact_version)

                    except (OSError, json.JSONDecodeError) as e:
                        logger.warning(
                            "%sFailed to read metadata for version %d: %s",
                            log_prefix,
                            version_num,
                            e,
                        )
                        continue

        except OSError as e:
            logger.error(
                "%sError listing versions in directory '%s': %s",
                log_prefix,
                artifact_dir,
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
        log_prefix = f"[FSArtifact:GetArtifactVersion:{filename}] "
        filename = self._normalize_filename_unicode(filename)
        artifact_dir = self._get_artifact_dir(app_name, user_id, session_id, filename)

        if not await asyncio.to_thread(os.path.isdir, artifact_dir):
            logger.debug("%sArtifact directory not found: %s", log_prefix, artifact_dir)
            return None

        # Determine which version to load
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

        version_path = self._get_version_path(artifact_dir, load_version)
        metadata_path = self._get_metadata_path(artifact_dir, load_version)

        if not await asyncio.to_thread(
            os.path.exists, version_path
        ) or not await asyncio.to_thread(os.path.exists, metadata_path):
            logger.warning(
                "%sData or metadata file missing for version %d.",
                log_prefix,
                load_version,
            )
            return None

        try:
            # Read metadata
            def _read_metadata():
                with open(metadata_path, encoding="utf-8") as f:
                    return json.load(f)

            metadata = await asyncio.to_thread(_read_metadata)
            mime_type = metadata.get("mime_type", "application/octet-stream")

            # Get file creation time
            stat_info = await asyncio.to_thread(os.stat, version_path)
            create_time = stat_info.st_ctime

            # Create and return ArtifactVersion object
            artifact_version = ArtifactVersion(
                version=load_version,
                canonical_uri=f"file://{version_path}",
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

        except (OSError, json.JSONDecodeError) as e:
            logger.error(
                "%sFailed to get metadata for artifact '%s' version %d: %s",
                log_prefix,
                filename,
                load_version,
                e,
            )
            return None

    def _normalize_filename_unicode(self, filename: str) -> str:
        """
        Normalizes Unicode characters in a filename to their standard form.
        Specifically targets compatibility characters like non-breaking spaces (\u202f)
        and converts them to their regular ASCII equivalents (a standard space).
        """
        return unicodedata.normalize("NFKC", filename)
