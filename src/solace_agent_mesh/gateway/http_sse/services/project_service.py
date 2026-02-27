"""
Business service for project-related operations.
"""

from typing import List, Optional, TYPE_CHECKING, Tuple
import logging
import json
import zipfile
import os
from io import BytesIO
from fastapi import UploadFile
from datetime import datetime, timezone

from ....agent.utils.artifact_helpers import (
    get_artifact_counts_batch,
    get_artifact_info_list,
    is_internal_artifact,
    save_artifact_with_metadata,
)
from ...constants import (
    DEFAULT_MAX_PER_FILE_UPLOAD_SIZE_BYTES,
    DEFAULT_MAX_BATCH_UPLOAD_SIZE_BYTES,
    DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES,
    DEFAULT_MAX_PROJECT_SIZE_BYTES,
    DEFAULT_MAX_PROJECT_FILE_DESCRIPTION_LENGTH,
    ARTIFACTS_PREFIX
)

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


from ....common.a2a.types import ArtifactInfo
from ....common.middleware.registry import MiddlewareRegistry
from ....services.resource_sharing_service import ResourceSharingService, ResourceType
from ..repository.interfaces import IProjectRepository
from ..repository.entities.project import Project

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


def bytes_to_mb(size_bytes: int) -> float:
    """Convert bytes to megabytes."""
    return size_bytes / (1024 * 1024)


class ProjectService:
    """Service layer for project business logic."""

    def __init__(
        self,
        component: "WebUIBackendComponent" = None,
        resource_sharing_service: ResourceSharingService = None,
    ):
        self.component = component
        self.artifact_service = component.get_shared_artifact_service() if component else None
        self.app_name = component.get_config("name", "WebUIBackendApp") if component else "WebUIBackendApp"
        self.logger = logging.getLogger(__name__)

        # Initialize resource sharing service
        if resource_sharing_service:
            self._resource_sharing_service = resource_sharing_service
        else:
            # Get from registry (returns class, need to instantiate)
            service_class = MiddlewareRegistry.get_resource_sharing_service()
            self._resource_sharing_service = service_class()

        # Get config values, with fallback to default (ensure values are integers for proper formatting)
        max_per_file_upload_config = (
            component.get_config("gateway_max_upload_size_bytes", DEFAULT_MAX_PER_FILE_UPLOAD_SIZE_BYTES)
            if component else DEFAULT_MAX_PER_FILE_UPLOAD_SIZE_BYTES
        )
        self.max_per_file_upload_size_bytes = int(max_per_file_upload_config) if isinstance(max_per_file_upload_config, (int, float)) else DEFAULT_MAX_PER_FILE_UPLOAD_SIZE_BYTES

        max_batch_upload_config = (
            component.get_config("gateway_max_batch_upload_size_bytes", DEFAULT_MAX_BATCH_UPLOAD_SIZE_BYTES)
            if component else DEFAULT_MAX_BATCH_UPLOAD_SIZE_BYTES
        )
        self.max_batch_upload_size_bytes = int(max_batch_upload_config) if isinstance(max_batch_upload_config, (int, float)) else DEFAULT_MAX_BATCH_UPLOAD_SIZE_BYTES

        max_zip_config = (
            component.get_config("gateway_max_zip_upload_size_bytes", DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES)
            if component else DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES
        )
        self.max_zip_upload_size_bytes = int(max_zip_config) if isinstance(max_zip_config, (int, float)) else DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES

        max_project_size_config = (
            component.get_config("gateway_max_project_size_bytes", DEFAULT_MAX_PROJECT_SIZE_BYTES)
            if component else DEFAULT_MAX_PROJECT_SIZE_BYTES
        )
        self.max_project_size_bytes = int(max_project_size_config) if isinstance(max_project_size_config, (int, float)) else DEFAULT_MAX_PROJECT_SIZE_BYTES

        self.logger.debug(
            "[ProjectService] Initialized with "
            "max_per_file_upload_size_bytes=%d (%.2f MB), "
            "max_batch_upload_size_bytes=%d (%.2f MB), "
            "max_zip_upload_size_bytes=%d (%.2f MB), "
            "max_project_size_bytes=%d (%.2f MB)",
            self.max_per_file_upload_size_bytes,
            bytes_to_mb(self.max_per_file_upload_size_bytes),
            self.max_batch_upload_size_bytes,
            bytes_to_mb(self.max_batch_upload_size_bytes),
            self.max_zip_upload_size_bytes,
            bytes_to_mb(self.max_zip_upload_size_bytes),
            self.max_project_size_bytes,
            bytes_to_mb(self.max_project_size_bytes)
        )

    def _get_repositories(self, db):
        """Create project repository for the given database session."""
        from ..repository.project_repository import ProjectRepository
        return ProjectRepository(db)

    def is_persistence_enabled(self) -> bool:
        """Checks if the service is configured with a persistent backend."""
        return self.component and self.component.database_url is not None

    async def _validate_file_size(self, file: UploadFile, log_prefix: str = "") -> bytes:
        """
        Validate file size and read content with size checking.
        
        Args:
            file: The uploaded file to validate
            log_prefix: Prefix for log messages
            
        Returns:
            bytes: The file content if validation passes
            
        Raises:
            ValueError: If file exceeds maximum allowed size
        """
        # Read file content in chunks to validate size
        chunk_size = 1024 * 1024  # 1MB chunks
        content_bytes = bytearray()
        total_bytes_read = 0
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            
            chunk_len = len(chunk)
            total_bytes_read += chunk_len
            
            # Validate size during reading (fail fast)
            if total_bytes_read > self.max_per_file_upload_size_bytes:
                error_msg = (
                    f"File '{file.filename}' rejected: size exceeds maximum "
                    f"{self.max_per_file_upload_size_bytes:,} bytes "
                    f"({bytes_to_mb(self.max_per_file_upload_size_bytes):.2f} MB). "
                    f"Read {total_bytes_read:,} bytes so far."
                )
                self.logger.warning(f"{log_prefix} {error_msg}")
                raise ValueError(error_msg)
            
            content_bytes.extend(chunk)
        
        return bytes(content_bytes)

    async def _validate_files(
        self,
        files: List[UploadFile],
        log_prefix: str = ""
    ) -> List[tuple]:
        """
        Validate multiple files and return their content.
        
        Args:
            files: List of uploaded files to validate
            log_prefix: Prefix for log messages
            
        Returns:
            List of tuples: [(file, content_bytes), ...]
            
        Raises:
            ValueError: If any file exceeds maximum allowed size
        """
        validated_files = []
        for file in files:
            content_bytes = await self._validate_file_size(file, log_prefix)
            validated_files.append((file, content_bytes))
            self.logger.debug(
                f"{log_prefix} Validated file '{file.filename}': {len(content_bytes):,} bytes"
            )
        return validated_files

    def _validate_file_descriptions(self, file_metadata: dict) -> None:
        """Validate that all file descriptions are within the max length."""
        limit = DEFAULT_MAX_PROJECT_FILE_DESCRIPTION_LENGTH
        for filename, desc in file_metadata.items():
            if isinstance(desc, str) and len(desc) > limit:
                raise ValueError(
                    f"Description for '{filename}' exceeds maximum length of {limit} characters ({len(desc)} provided)"
                )

    def _validate_batch_upload_size(
        self,
        files_size: int,
        log_prefix: str = ""
    ) -> None:
        """
        Validate that the total size of files in a single upload batch doesn't exceed limit.
        This is independent of the total project size.

        Args:
            files_size: Total size of all files being uploaded in this batch (bytes)
            log_prefix: Logging prefix

        Raises:
            ValueError: If batch size exceeds limit
        """

        files_mb = bytes_to_mb(files_size)
        limit_mb = bytes_to_mb(self.max_batch_upload_size_bytes)

        if files_size > self.max_batch_upload_size_bytes:
            error_msg = (
                f"Batch upload size limit exceeded. "
                f"Total files in this upload: {files_mb:.2f} MB exceeds limit of {limit_mb:.2f} MB."
            )
            self.logger.warning(f"{log_prefix} {error_msg}")
            raise ValueError(error_msg)

        self.logger.debug(
            f"{log_prefix} Batch upload size check passed: "
            f"{files_mb:.2f} MB / {limit_mb:.2f} MB "
            f"({(files_size / self.max_batch_upload_size_bytes * 100):.1f}% of batch limit)"
        )

    def _validate_project_size_limit(
        self,
        current_project_size: int,
        new_files_size: int,
        log_prefix: str = ""
    ) -> None:
        """
        Validate that adding new files won't exceed project total size limit.

        Only counts user-uploaded files (source="project") toward the limit.
        LLM-generated artifacts and system files are excluded.

        Args:
            current_project_size: Current total size of user-uploaded files in bytes
            new_files_size: Total size of new files being added in bytes
            log_prefix: Logging prefix

        Raises:
            ValueError: If combined size would exceed limit
        """

        total_size = current_project_size + new_files_size

        current_mb = bytes_to_mb(current_project_size)
        new_mb = bytes_to_mb(new_files_size)
        total_mb = bytes_to_mb(total_size)
        limit_mb = bytes_to_mb(self.max_project_size_bytes)

        if total_size > self.max_project_size_bytes:
            error_msg = (
                f"Project size limit exceeded. "
                f"Current: {current_mb:.2f} MB, "
                f"New files: {new_mb:.2f} MB, "
                f"Total: {total_mb:.2f} MB exceeds limit of {limit_mb:.2f} MB."
            )
            self.logger.warning(f"{log_prefix} {error_msg}")
            raise ValueError(error_msg)

        self.logger.debug(
            f"{log_prefix} Project size check passed: "
            f"{total_mb:.2f} MB / {limit_mb:.2f} MB "
            f"({(total_size / self.max_project_size_bytes * 100):.1f}% used)"
        )

    async def create_project(
        self,
        db,
        name: str,
        user_id: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        default_agent_id: Optional[str] = None,
        files: Optional[List[UploadFile]] = None,
        file_metadata: Optional[dict] = None,
    ) -> Project:
        """
        Create a new project for a user.

        Args:
            db: Database session
            name: Project name
            user_id: ID of the user creating the project
            description: Optional project description
            system_prompt: Optional system prompt
            default_agent_id: Optional default agent ID for new chats
            files: Optional list of files to associate with the project

        Returns:
            DomainProject: The created project

        Raises:
            ValueError: If project name is invalid, user_id is missing, or file size exceeds limit
        """
        log_prefix = f"[ProjectService:create_project] User {user_id}:"
        self.logger.info(f"Creating new project '{name}' for user {user_id}")

        # Business validation
        if not name or not name.strip():
            raise ValueError("Project name cannot be empty")

        if not user_id:
            raise ValueError("User ID is required to create a project")

        # Validate file sizes before creating project
        validated_files = []
        if files:
            self.logger.info(f"{log_prefix} Validating {len(files)} files before project creation")
            validated_files = await self._validate_files(files, log_prefix)
            self.logger.info(f"{log_prefix} All {len(files)} files passed size validation")

            new_files_size = sum(len(content) for _, content in validated_files)

            self._validate_batch_upload_size(
                files_size=new_files_size,
                log_prefix=log_prefix
            )

            self._validate_project_size_limit(
                current_project_size=0,
                new_files_size=new_files_size,
                log_prefix=log_prefix
            )

        project_repository = self._get_repositories(db)

        # Check for duplicate project name for this user (only owned projects)
        existing_projects = project_repository.get_accessible_projects(user_id, shared_project_ids=[])
        if any(p.name.lower() == name.strip().lower() for p in existing_projects):
            raise ValueError(f"A project with the name '{name.strip()}' already exists")

        # Create the project
        project_domain = project_repository.create_project(
            name=name.strip(),
            user_id=user_id,
            description=description.strip() if description else None,
            system_prompt=system_prompt.strip() if system_prompt else None,
            default_agent_id=default_agent_id,
        )

        if file_metadata:
            self._validate_file_descriptions(file_metadata)

        if validated_files and self.artifact_service:
            self.logger.info(
                f"Project {project_domain.id} created, now saving {len(validated_files)} artifacts."
            )
            project_session_id = f"project-{project_domain.id}"
            for file, content_bytes in validated_files:
                metadata = {"source": "project"}
                desc = file_metadata.get(file.filename) if file_metadata else None
                if desc:
                    metadata["description"] = desc

                await save_artifact_with_metadata(
                    artifact_service=self.artifact_service,
                    app_name=self.app_name,
                    user_id=project_domain.user_id,
                    session_id=project_session_id,
                    filename=file.filename,
                    content_bytes=content_bytes,
                    mime_type=file.content_type,
                    metadata_dict=metadata,
                    timestamp=datetime.now(timezone.utc),
                )
            self.logger.info(f"Saved {len(validated_files)} artifacts for project {project_domain.id}")

        self.logger.info(
            f"Successfully created project {project_domain.id} for user {user_id}"
        )
        return project_domain

    def get_project(self, db, project_id: str, user_id: str) -> Optional[Project]:
        """
        Get a project by ID, ensuring the user has access to it.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID

        Returns:
            Optional[Project]: The project if found and accessible, None otherwise
        """
        from ..repository.models import ProjectModel

        # Get project without user filter
        project_model = db.query(ProjectModel).filter_by(
            id=project_id, deleted_at=None
        ).first()

        if not project_model:
            return None

        # Check if user has access (owner OR shared access via resource sharing service)
        if not self._has_view_access(db, project_id, user_id):
            return None

        # Convert to domain entity
        project_repository = self._get_repositories(db)
        return project_repository._model_to_entity(project_model)

    def get_user_projects(self, db, user_email: str) -> List[Project]:
        """
        Get all projects accessible by a specific user (owned + shared).

        Args:
            db: Database session
            user_email: The user's email

        Returns:
            List[Project]: List of user's accessible projects (owned + shared)
        """
        self.logger.debug(f"Retrieving accessible projects for user {user_email}")

        # Get shared project IDs from enterprise service (empty list for community)
        shared_project_ids = self._resource_sharing_service.get_shared_resource_ids(
            session=db,
            user_email=user_email,
            resource_type=ResourceType.PROJECT
        )

        # Get all accessible projects (owned + shared)
        project_repository = self._get_repositories(db)
        return project_repository.get_accessible_projects(user_email, shared_project_ids)

    async def get_user_projects_with_counts(self, db, user_email: str) -> List[tuple[Project, int]]:
        """
        Get all projects accessible by a specific user with artifact counts.
        Uses batch counting for efficiency.

        Args:
            db: Database session
            user_email: The user's email

        Returns:
            List[tuple[Project, int]]: List of tuples (project, artifact_count)
        """
        self.logger.debug(f"Retrieving projects with artifact counts for user {user_email}")
        projects = self.get_user_projects(db, user_email)
        
        if not self.artifact_service or not projects:
            # If no artifact service or no projects, return projects with 0 counts
            return [(project, 0) for project in projects]
        
        # Build list of session IDs for batch counting
        session_ids = [f"project-{project.id}" for project in projects]
        
        try:
            # Get all counts in a single batch operation
            counts_by_session = await get_artifact_counts_batch(
                artifact_service=self.artifact_service,
                app_name=self.app_name,
                user_id=user_email,
                session_ids=session_ids,
            )
            
            # Map counts back to projects
            projects_with_counts = []
            for project in projects:
                storage_session_id = f"project-{project.id}"
                artifact_count = counts_by_session.get(storage_session_id, 0)
                projects_with_counts.append((project, artifact_count))
            
            self.logger.debug(f"Retrieved artifact counts for {len(projects)} projects in batch")
            return projects_with_counts
            
        except Exception as e:
            self.logger.error(f"Failed to get artifact counts in batch: {e}")
            # Fallback to 0 counts on error
            return [(project, 0) for project in projects]

    async def get_project_artifacts(self, db, project_id: str, user_id: str) -> List[ArtifactInfo]:
        """
        Get a list of artifacts for a given project.
        
        Args:
            db: The database session
            project_id: The project ID
            user_id: The requesting user ID
            
        Returns:
            List[ArtifactInfo]: A list of artifacts
            
        Raises:
            ValueError: If project not found or access denied
        """
        project = self.get_project(db, project_id, user_id)
        if not project:
            raise ValueError("Project not found or access denied")

        if not self.artifact_service:
            self.logger.warning("Attempted to get artifacts for project but no artifact service is configured.")
            return []

        storage_user_id = project.user_id
        storage_session_id = f"project-{project.id}"

        self.logger.info(f"Fetching artifacts for project {project.id} with storage session {storage_session_id} and user {storage_user_id}")

        all_artifacts = await get_artifact_info_list(
            artifact_service=self.artifact_service,
            app_name=self.app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
        )

        # Filter out generated files (converted files and indices)
        # This filtering is flag-independent - users always see only original files
        original_artifacts = [
            artifact for artifact in all_artifacts
            if self._is_original_artifact(artifact.filename)
        ]

        self.logger.debug(
            f"Filtered artifacts for project {project_id}: "
            f"{len(original_artifacts)} original files "
            f"(excluded {len(all_artifacts) - len(original_artifacts)} generated files)"
        )

        return original_artifacts

    async def add_artifacts_to_project(
        self,
        db,
        project_id: str,
        user_id: str,
        files: List[UploadFile],
        file_metadata: Optional[dict] = None,
        indexing_enabled: bool = True
    ) -> List[dict]:
        """
        Add one or more artifacts to a project with optional conversion and indexing.

        Args:
            indexing_enabled: If True, convert PDF/DOCX/PPTX to text and build BM25 index
        
        Args:
            db: The database session
            project_id: The project ID
            user_id: The requesting user ID
            files: List of files to add
            file_metadata: Optional dictionary of metadata (e.g., descriptions)
            
        Returns:
            List[dict]: A list of results from the save operations
            
        Raises:
            ValueError: If project not found, access denied, or file size exceeds limit
        """
        log_prefix = f"[ProjectService:add_artifacts] Project {project_id}, User {user_id}:"
        
        project = self.get_project(db, project_id, user_id)
        if not project:
            raise ValueError("Project not found or access denied")

        # Only owners can modify artifacts (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to modify artifacts")

        if not self.artifact_service:
            self.logger.warning(f"Attempted to add artifacts to project {project_id} but no artifact service is configured.")
            raise ValueError("Artifact service is not configured")
        
        if not files:
            return []

        # Validate file sizes before saving any artifacts
        self.logger.info(f"{log_prefix} Validating {len(files)} files before adding to project")
        validated_files = await self._validate_files(files, log_prefix)
        self.logger.info(f"{log_prefix} All {len(files)} files passed size validation")

        new_files_size = sum(len(content) for _, content in validated_files)

        self._validate_batch_upload_size(
            files_size=new_files_size,
            log_prefix=log_prefix
        )

        existing_artifacts = await self.get_project_artifacts(db, project_id, user_id)
        # Only count user-uploaded artifacts, which have the "source" metadata set to "project"
        current_project_size = sum(artifact.size for artifact in existing_artifacts if artifact.source == "project")

        self._validate_project_size_limit(
            current_project_size=current_project_size,
            new_files_size=new_files_size,
            log_prefix=log_prefix
        )

        self.logger.info(f"Adding {len(validated_files)} artifacts to project {project_id} for user {user_id}")
        storage_session_id = f"project-{project.id}"

        if file_metadata:
            self._validate_file_descriptions(file_metadata)

        results = []

        for file, content_bytes in validated_files:
            metadata = {"source": "project"}
            desc = file_metadata.get(file.filename) if file_metadata else None
            if desc:
                metadata["description"] = desc

            # Add line-range citations for text-based files
            # This provides granular location info similar to page numbers for PDFs
            # Generate citations regardless of indexing_enabled (they're just metadata)
            if self._is_text_file(file.content_type, file.filename):
                try:
                    # Decode text content
                    text_content = content_bytes.decode('utf-8', errors='ignore')

                    # Generate line-range citations
                    from .file_converter_service import create_line_range_citations
                    citation_metadata = create_line_range_citations(text_content)

                    # Add to metadata
                    metadata["text_citations"] = citation_metadata

                    self.logger.debug(
                        f"Generated {len(citation_metadata.get('citation_map', []))} line-range citations "
                        f"for {file.filename}"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to generate citations for {file.filename}: {e}")

            result = await save_artifact_with_metadata(
                artifact_service=self.artifact_service,
                app_name=self.app_name,
                user_id=project.user_id, # Always use project owner's ID for storage
                session_id=storage_session_id,
                filename=file.filename,
                content_bytes=content_bytes,
                mime_type=file.content_type,
                metadata_dict=metadata,
                timestamp=datetime.now(timezone.utc),
            )
            results.append(result)

        self.logger.info(f"Finished adding {len(validated_files)} artifacts to project {project_id}")

        # Post-processing: conversion and indexing (only if feature enabled)
        if not indexing_enabled:
            self.logger.debug("Indexing disabled for this project, skipping post-processing")
            return results

        self.logger.info(f"Indexing enabled - post-processing {len(validated_files)} files")

        # Classify uploaded files by type
        needs_conversion = []  # PDF, DOCX, PPTX
        is_text_based = []     # .txt, .md, .json, .py, etc.

        for idx, (file, content_bytes) in enumerate(validated_files):
            filename = file.filename
            mime_type = file.content_type
            file_version = results[idx]["data_version"]

            if self._should_convert_file(mime_type, filename):
                needs_conversion.append((filename, file_version, mime_type))
                self.logger.debug(f"File {filename} v{file_version} marked for conversion")
            elif self._is_text_file(mime_type, filename):
                is_text_based.append((filename, file_version))
                self.logger.debug(f"File {filename} v{file_version} is text-based")

        # Convert binary files to text
        conversion_happened = False
        if needs_conversion:
            try:
                conversion_results = await self._convert_project_artifacts(
                    project, needs_conversion, indexing_enabled
                )
                conversion_happened = len(conversion_results) > 0
                self.logger.info(f"Converted {len(conversion_results)}/{len(needs_conversion)} files")
            except Exception as e:
                self.logger.error(f"Conversion failed (non-critical): {e}")

        # Rebuild index if text files were added or conversions happened
        if is_text_based or conversion_happened:
            try:
                await self._rebuild_project_index(project, indexing_enabled)
                self.logger.info("Rebuilt index for project")
            except Exception as e:
                self.logger.error(f"Index rebuild failed (non-critical): {e}")

        return results

    async def update_artifact_metadata(
        self,
        db,
        project_id: str,
        user_id: str,
        filename: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Update metadata (description) for a project artifact.

        IMPORTANT: This creates a new version of the file with updated metadata,
        but does NOT trigger conversion or indexing. This is intentional.

        Example:
        - Original file: report.pdf v0, v1, v2
        - Update metadata for report.pdf → creates v3 (metadata only)
        - Converted file: report.pdf.converted.txt v0 (unchanged - no re-conversion)
        - Index: stays at current version (no rebuild)

        Versions being out of sync is expected and acceptable for metadata-only updates.

        Args:
            db: The database session
            project_id: The project ID
            user_id: The requesting user ID
            filename: The filename of the artifact to update
            description: New description for the artifact

        Returns:
            bool: True if update was successful, False if project not found

        Raises:
            ValueError: If user cannot modify the project or artifact service is missing
        """
        project = self.get_project(db, project_id, user_id)
        if not project:
            return False

        # Only owners can edit artifacts (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to edit artifacts")

        if not self.artifact_service:
            self.logger.warning(f"Attempted to update artifact metadata in project {project_id} but no artifact service is configured.")
            raise ValueError("Artifact service is not configured")

        storage_session_id = f"project-{project.id}"
        
        self.logger.info(f"Updating metadata for artifact '{filename}' in project {project_id} for user {user_id}")
        
        # Load the current artifact to get its content and existing metadata
        try:
            artifact_part = await self.artifact_service.load_artifact(
                app_name=self.app_name,
                user_id=project.user_id,
                session_id=storage_session_id,
                filename=filename,
            )

            if not artifact_part or not artifact_part.inline_data:
                self.logger.warning(f"Artifact '{filename}' not found in project {project_id}")
                return False

            # Prepare updated metadata
            metadata = {"source": "project"}
            if description is not None:
                self._validate_file_descriptions({filename: description})
                metadata["description"] = description

            # Save the artifact with updated metadata
            await save_artifact_with_metadata(
                artifact_service=self.artifact_service,
                app_name=self.app_name,
                user_id=project.user_id,
                session_id=storage_session_id,
                filename=filename,
                content_bytes=artifact_part.inline_data.data,
                mime_type=artifact_part.inline_data.mime_type,
                metadata_dict=metadata,
                timestamp=datetime.now(timezone.utc),
            )
            
            self.logger.info(f"Successfully updated metadata for artifact '{filename}' in project {project_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating artifact metadata: {e}")
            raise

    async def delete_artifact_from_project(
        self, db, project_id: str, user_id: str, filename: str,
        indexing_enabled: bool = True
    ) -> bool:
        """
        Deletes an artifact from a project with optional cleanup and index rebuild.

        Args:
            db: The database session
            project_id: The project ID
            user_id: The requesting user ID
            filename: The filename of the artifact to delete
            indexing_enabled: If True, delete converted files and rebuild index

        Returns:
            bool: True if deletion was attempted, False if project not found

        Raises:
            ValueError: If user cannot modify the project or artifact service is missing
        """
        project = self.get_project(db, project_id, user_id)
        if not project:
            return False

        # Only owners can delete artifacts (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to delete artifacts")

        if not self.artifact_service:
            self.logger.warning(f"Attempted to delete artifact from project {project_id} but no artifact service is configured.")
            raise ValueError("Artifact service is not configured")

        storage_session_id = f"project-{project.id}"

        # Determine file type before deletion (only if indexing enabled - optimization)
        mime_type = ""
        if indexing_enabled:
            try:
                from ....agent.utils.artifact_helpers import load_artifact_content_or_metadata
                metadata_result = await load_artifact_content_or_metadata(
                    artifact_service=self.artifact_service,
                    app_name=self.app_name,
                    user_id=project.user_id,
                    session_id=storage_session_id,
                    filename=filename,
                    version="latest",
                    load_metadata_only=True
                )
                mime_type = metadata_result.get("metadata", {}).get("mime_type", "")
            except Exception as e:
                self.logger.warning(f"Could not load metadata for {filename}: {e}")
                mime_type = ""

        self.logger.info(f"Deleting artifact '{filename}' from project {project_id} for user {user_id}")

        # Delete original file (all versions) - ALWAYS happens
        await self.artifact_service.delete_artifact(
            app_name=self.app_name,
            user_id=project.user_id, # Always use project owner's ID for storage
            session_id=storage_session_id,
            filename=filename,
        )
        self.logger.info(f"Deleted all versions of {filename}")

        # Post-deletion cleanup and indexing (only if feature enabled)
        if not indexing_enabled:
            self.logger.debug(f"Indexing disabled for project {project_id}")
            return True

        # Delete converted file if this was a convertible binary
        deleted_converted = False
        if self._should_convert_file(mime_type, filename):
            converted_filename = f"{filename}.converted.txt"
            try:
                await self.artifact_service.delete_artifact(
                    app_name=self.app_name,
                    user_id=project.user_id,
                    session_id=storage_session_id,
                    filename=converted_filename,
                )
                deleted_converted = True
                self.logger.info(f"Deleted all versions of converted file: {converted_filename}")
            except Exception as e:
                self.logger.debug(f"No converted file to delete: {e}")

        # Rebuild index if text file or converted file was deleted
        if self._is_text_file(mime_type, filename) or deleted_converted:
            try:
                await self._rebuild_project_index(project, indexing_enabled)
                self.logger.info(f"Rebuilt index after deleting {filename}")
            except Exception as e:
                self.logger.error(f"Index rebuild failed (non-critical): {e}")

        return True

    def update_project(self, db, project_id: str, user_id: str,
                           name: Optional[str] = None, description: Optional[str] = None,
                           system_prompt: Optional[str] = None, default_agent_id: Optional[str] = ...) -> Optional[Project]:
        """
        Update a project's details.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID
            name: New project name (optional)
            description: New project description (optional)
            system_prompt: New system prompt (optional)
            default_agent_id: New default agent ID (optional, use ... sentinel to indicate not provided)

        Returns:
            Optional[Project]: The updated project if successful, None otherwise
        """
        # Validate business rules
        if name is not None and name is not ... and not name.strip():
            raise ValueError("Project name cannot be empty")

        # Build update data
        update_data = {}
        if name is not None and name is not ...:
            update_data["name"] = name.strip()
        if description is not None and description is not ...:
            update_data["description"] = description.strip() if description else None
        if system_prompt is not None and system_prompt is not ...:
            update_data["system_prompt"] = system_prompt.strip() if system_prompt else None
        if default_agent_id is not ...:
            update_data["default_agent_id"] = default_agent_id

        if not update_data:
            # Nothing to update - get existing project
            return self.get_project(db, project_id, user_id)

        # First check if user can view the project (404 if not)
        if not self._has_view_access(db, project_id, user_id):
            return None

        # Only owners can edit projects (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to edit project")

        project_repository = self._get_repositories(db)
        updated_project = project_repository.update(project_id, update_data)

        if updated_project:
            self.logger.info(f"Successfully updated project {project_id}")

        return updated_project

    def delete_project(self, db, project_id: str, user_id: str) -> bool:
        """
        Delete a project.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        # Only owners can delete projects
        if not self._is_project_owner(db, project_id, user_id):
            return False

        # Delete all shares for this project (cascade)
        self._resource_sharing_service.delete_resource_shares(
            session=db,
            resource_id=project_id,
            resource_type=ResourceType.PROJECT
        )

        project_repository = self._get_repositories(db)
        deleted = project_repository.delete(project_id)

        if deleted:
            self.logger.info(f"Successfully deleted project {project_id}")

        return deleted

    def soft_delete_project(self, db, project_id: str, user_id: str) -> bool:
        """
        Soft delete a project (mark as deleted without removing from database).
        Also cascades soft delete to all sessions associated with this project.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID

        Returns:
            bool: True if soft deleted successfully, False if not found

        Raises:
            ValueError: If user lacks permission to delete
        """
        # First check if user can view the project (404 if not)
        if not self._has_view_access(db, project_id, user_id):
            return False

        # Only owners can delete projects (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to delete project")

        self.logger.info(f"Soft deleting project {project_id} and its associated sessions for user {user_id}")

        project_repository = self._get_repositories(db)
        soft_deleted = project_repository.soft_delete(project_id, user_id)

        if not soft_deleted:
            return False

        from ..repository.session_repository import SessionRepository
        session_repo = SessionRepository()

        owner_deleted_count = session_repo.soft_delete_by_project(db, project_id, user_id)

        self._resource_sharing_service.delete_resource_shares(
            session=db,
            resource_id=project_id,
            resource_type=ResourceType.PROJECT
        )

        self.logger.info(
            f"Successfully soft deleted project {project_id} and {owner_deleted_count} owner sessions "
            f"(shared users handled by sharing service)"
        )

        return True

    async def export_project_as_zip(
        self, db, project_id: str, user_id: str
    ) -> BytesIO:
        """
        Create ZIP file with project data and artifacts.
        Returns in-memory ZIP file.
        
        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID
            
        Returns:
            BytesIO: In-memory ZIP file
            
        Raises:
            ValueError: If project not found or access denied
        """
        # Get project
        project = self.get_project(db, project_id, user_id)
        if not project:
            raise ValueError("Project not found or access denied")

        # Only owners can export projects (viewers have read-only access)
        if not self._is_project_owner(db, project_id, user_id):
            raise ValueError("Permission denied: insufficient access to export project")
        
        # Get artifacts
        artifacts = await self.get_project_artifacts(db, project_id, user_id)
        
        # Calculate total size
        total_size = sum(artifact.size for artifact in artifacts)
        
        # Create export metadata
        from ..routers.dto.project_dto import (
            ProjectExportFormat,
            ProjectExportData,
            ProjectExportMetadata,
            ArtifactMetadata,
        )
        
        export_data = ProjectExportFormat(
            version="1.0",
            exported_at=int(datetime.now(timezone.utc).timestamp() * 1000),
            project=ProjectExportData(
                name=project.name,
                description=project.description,
                system_prompt=project.system_prompt,
                default_agent_id=project.default_agent_id,
                metadata=ProjectExportMetadata(
                    original_created_at=project.created_at,
                    artifact_count=len(artifacts),
                    total_size_bytes=total_size,
                ),
            ),
            artifacts=[
                ArtifactMetadata(
                    filename=artifact.filename,
                    mime_type=artifact.mime_type or "application/octet-stream",
                    size=artifact.size,
                    metadata={
                        "description": artifact.description,
                        "source": artifact.source,
                    } if artifact.description or artifact.source else {},
                )
                for artifact in artifacts
            ],
        )
        
        # Create ZIP in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add project.json
            project_json = export_data.model_dump(by_alias=True, mode='json')
            zip_file.writestr('project.json', json.dumps(project_json, indent=2))
            
            # Add artifacts
            if self.artifact_service and artifacts:
                storage_session_id = f"project-{project.id}"
                for artifact in artifacts:
                    try:
                        # Load artifact content
                        artifact_part = await self.artifact_service.load_artifact(
                            app_name=self.app_name,
                            user_id=project.user_id,
                            session_id=storage_session_id,
                            filename=artifact.filename,
                        )
                        
                        if artifact_part and artifact_part.inline_data:
                            # Add to ZIP under artifacts/ directory
                            zip_file.writestr(
                                f'{ARTIFACTS_PREFIX}{artifact.filename}',
                                artifact_part.inline_data.data
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to add artifact {artifact.filename} to export: {e}"
                        )
        
        zip_buffer.seek(0)
        return zip_buffer

    async def import_project_from_zip(
        self, db, zip_file: UploadFile, user_id: str,
        preserve_name: bool = False, custom_name: Optional[str] = None,
        indexing_enabled: bool = True
    ) -> tuple[Project, int, List[str]]:
        """
        Import project from ZIP file with optional conversion and indexing.

        Args:
            db: Database session
            zip_file: Uploaded ZIP file
            user_id: The importing user ID
            preserve_name: Whether to preserve original name
            custom_name: Custom name to use (overrides preserve_name)
            indexing_enabled: If True, convert binaries and build index

        Returns:
            tuple: (created_project, artifacts_count, warnings)
            
        Raises:
            ValueError: If ZIP is invalid, import fails, or file size exceeds limit
        """
        log_prefix = f"[ProjectService:import_project] User {user_id}:"
        warnings = []
        
        # Read ZIP file content with size validation
        self.logger.info(f"{log_prefix} Reading ZIP file")
        zip_content = await zip_file.read()
        zip_size = len(zip_content)
        self.logger.info(f"{log_prefix} ZIP file read: {zip_size:,} bytes")
        
        # Validate ZIP file size (separate, larger limit than individual artifacts)
        if zip_size > self.max_zip_upload_size_bytes:
            max_size_mb = bytes_to_mb(self.max_zip_upload_size_bytes)
            file_size_mb = bytes_to_mb(zip_size)
            error_msg = (
                f"ZIP file '{zip_file.filename}' rejected: size ({file_size_mb:.2f} MB) "
                f"exceeds maximum allowed ({max_size_mb:.2f} MB)"
            )
            self.logger.warning(f"{log_prefix} {error_msg}")
            raise ValueError(error_msg)
        
        zip_buffer = BytesIO(zip_content)
        
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                # Validate ZIP structure
                if 'project.json' not in zip_ref.namelist():
                    raise ValueError("Invalid project export: missing project.json")
                
                # Parse project.json
                project_json_content = zip_ref.read('project.json').decode('utf-8')
                project_data = json.loads(project_json_content)
                
                # Validate version
                if project_data.get('version') != '1.0':
                    raise ValueError(
                        f"Unsupported export version: {project_data.get('version')}"
                    )
                
                # Determine project name
                original_name = project_data['project']['name']
                if custom_name:
                    desired_name = custom_name
                elif preserve_name:
                    desired_name = original_name
                else:
                    desired_name = original_name
                
                # Resolve name conflicts
                final_name = self._resolve_project_name_conflict(db, desired_name, user_id)
                if final_name != desired_name:
                    warnings.append(
                        f"Name conflict resolved: '{desired_name}' → '{final_name}'"
                    )
                
                # Get default agent ID, but set to None if not provided
                # The agent may not exist in the target environment
                imported_agent_id = project_data['project'].get('defaultAgentId')

                # Pre-calculate total artifacts size for limit validation
                artifact_files = [
                    name for name in zip_ref.namelist()
                    if name.startswith(ARTIFACTS_PREFIX) and name != ARTIFACTS_PREFIX
                ]

                total_artifacts_size = 0
                oversized_artifacts = []

                for artifact_path in artifact_files:
                    file_info = zip_ref.getinfo(artifact_path)
                    uncompressed_size = file_info.file_size

                    # Track oversized files (will be skipped during import)
                    if uncompressed_size > self.max_per_file_upload_size_bytes:
                        safe_filename = os.path.basename(artifact_path)
                        oversized_artifacts.append(
                            (safe_filename, uncompressed_size)
                        )
                        continue

                    total_artifacts_size += uncompressed_size

                self._validate_project_size_limit(
                    current_project_size=0,
                    new_files_size=total_artifacts_size,
                    log_prefix=log_prefix
                )

                # Create project (agent validation happens in create_project if needed)
                project = await self.create_project(
                    db=db,
                    name=final_name,
                    user_id=user_id,
                    description=project_data['project'].get('description'),
                    system_prompt=project_data['project'].get('systemPrompt'),
                    default_agent_id=imported_agent_id,
                )
                
                # Add warning if agent was specified but may not exist
                if imported_agent_id:
                    warnings.append(
                        f"Default agent '{imported_agent_id}' was imported. "
                        "Verify it exists in your environment."
                    )
                
                # Import artifacts
                artifacts_imported = 0
                if self.artifact_service:
                    storage_session_id = f"project-{project.id}"
                    
                    for artifact_path in artifact_files:
                        try:
                            filename = os.path.basename(artifact_path)

                            # Validate filename is safe
                            if not filename or filename in ('.', '..'):
                                self.logger.warning(f"{log_prefix} Skipping invalid filename in ZIP: {artifact_path}")
                                warnings.append(f"Skipped invalid filename: {artifact_path}")
                                continue

                            content_bytes = zip_ref.read(artifact_path)
                            
                            # Skip oversized artifacts with a warning (don't fail the entire import)
                            if len(content_bytes) > self.max_per_file_upload_size_bytes:
                                max_size_mb = bytes_to_mb(self.max_per_file_upload_size_bytes)
                                file_size_mb = bytes_to_mb(len(content_bytes))
                                skip_msg = (
                                    f"Skipped '{filename}': size ({file_size_mb:.2f} MB) "
                                    f"exceeds maximum allowed ({max_size_mb:.2f} MB)"
                                )
                                self.logger.warning(f"{log_prefix} {skip_msg}")
                                warnings.append(skip_msg)
                                continue  # Skip this artifact, continue with others
                            
                            # Find metadata from project.json
                            artifact_meta = next(
                                (a for a in project_data.get('artifacts', [])
                                 if a['filename'] == filename),
                                None
                            )
                            
                            metadata = artifact_meta.get('metadata', {}) if artifact_meta else {}
                            mime_type = artifact_meta.get('mimeType', 'application/octet-stream') if artifact_meta else 'application/octet-stream'
                            
                            # Save artifact
                            from ....agent.utils.artifact_helpers import save_artifact_with_metadata
                            await save_artifact_with_metadata(
                                artifact_service=self.artifact_service,
                                app_name=self.app_name,
                                user_id=project.user_id,
                                session_id=storage_session_id,
                                filename=filename,
                                content_bytes=content_bytes,
                                mime_type=mime_type,
                                metadata_dict=metadata,
                                timestamp=datetime.now(timezone.utc),
                            )
                            artifacts_imported += 1
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to import artifact {artifact_path}: {e}"
                            )
                            warnings.append(f"Failed to import artifact: {filename}")

                # Post-processing: conversion and indexing (only if feature enabled)
                if not indexing_enabled:
                    self.logger.debug("Indexing disabled for import, skipping post-processing")
                else:
                    self.logger.info(f"Indexing enabled - post-processing imported files")

                    # Classify imported files by type
                    needs_conversion = []  # PDF, DOCX, PPTX
                    is_text_based = []     # .txt, .md, .json, .py, etc.

                    for artifact_path in artifact_files:
                        try:
                            filename = artifact_path.replace('artifacts/', '')
                            artifact_meta = next(
                                (a for a in project_data.get('artifacts', [])
                                 if a['filename'] == filename),
                                None
                            )
                            mime_type = artifact_meta.get('mimeType', '') if artifact_meta else ''

                            if self._should_convert_file(mime_type, filename):
                                needs_conversion.append((filename, 0, mime_type))  # v0 on import
                                self.logger.debug(f"File {filename} marked for conversion")
                            elif self._is_text_file(mime_type, filename):
                                is_text_based.append((filename, 0))
                                self.logger.debug(f"File {filename} is text-based")
                        except Exception as e:
                            self.logger.warning(f"Error classifying {filename}: {e}")

                    # Convert binary files
                    conversion_happened = False
                    if needs_conversion:
                        try:
                            conversion_results = await self._convert_project_artifacts(
                                project, needs_conversion, indexing_enabled
                            )
                            conversion_happened = len(conversion_results) > 0
                            self.logger.info(f"Converted {len(conversion_results)}/{len(needs_conversion)} files")
                        except Exception as e:
                            self.logger.error(f"Conversion failed (non-critical): {e}")

                    # Build index if text files or conversions happened
                    if is_text_based or conversion_happened:
                        try:
                            await self._rebuild_project_index(project, indexing_enabled)
                            self.logger.info(f"Built index for imported project {project.id}")
                        except Exception as e:
                            self.logger.error(f"Index build failed (non-critical): {e}")

                self.logger.info(
                    f"Successfully imported project {project.id} with {artifacts_imported} artifacts"
                )
                return project, artifacts_imported, warnings
                
        except zipfile.BadZipFile:
            raise ValueError("Invalid ZIP file")
        except json.JSONDecodeError:
            raise ValueError("Invalid project.json format")
        except KeyError as e:
            raise ValueError(f"Missing required field in project.json: {e}")

    def _resolve_project_name_conflict(
        self, db, desired_name: str, user_id: str
    ) -> str:
        """
        Resolve project name conflicts by appending (2), (3), etc.
        Similar to prompt import conflict resolution.
        
        Args:
            db: Database session
            desired_name: The desired project name
            user_id: The user ID
            
        Returns:
            str: A unique project name
        """
        project_repository = self._get_repositories(db)
        # Get only owned projects for name conflict checking
        existing_projects = project_repository.get_accessible_projects(user_id, shared_project_ids=[])
        existing_names = {p.name.lower() for p in existing_projects}
        
        if desired_name.lower() not in existing_names:
            return desired_name
        
        # Try appending (2), (3), etc.
        counter = 2
        while True:
            candidate = f"{desired_name} ({counter})"
            if candidate.lower() not in existing_names:
                return candidate
            counter += 1
            if counter > 100:  # Safety limit
                raise ValueError("Unable to resolve name conflict")

    def _is_project_owner(self, db, project_id: str, user_id: str) -> bool:
        """
        Check if user is the owner of the project.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The user ID (email)

        Returns:
            bool: True if user is the project owner, False otherwise
        """
        from ..repository.models import ProjectModel

        project = db.query(ProjectModel).filter_by(
            id=project_id, user_id=user_id, deleted_at=None
        ).first()
        return project is not None

    def _has_view_access(self, db, project_id: str, user_id: str) -> bool:
        """
        Check if user can view the project.

        Returns True if user is owner OR has any shared access level (viewer).
        Since we only support "viewer" access level for sharing:
        - Owner = full access (edit, delete, share, export, artifacts)
        - Shared viewer = view only

        Args:
            db: Database session
            project_id: The project ID
            user_id: The user ID (email)

        Returns:
            bool: True if user can view the project, False otherwise
        """
        if self._is_project_owner(db, project_id, user_id):
            return True

        # Check for shared access (viewer level)
        access_level = self._resource_sharing_service.check_user_access(
            session=db,
            resource_id=project_id,
            resource_type=ResourceType.PROJECT,
            user_email=user_id
        )
        return access_level is not None


    # ==========================================
    # BM25 Indexing Feature - Helper Methods
    # ==========================================

    def _should_convert_file(self, mime_type: str, filename: str) -> bool:
        """
        Check if file is PDF/DOCX/PPTX that needs conversion.

        Args:
            mime_type: The MIME type of the file
            filename: The filename

        Returns:
            bool: True if file should be converted
        """
        if not mime_type:
            return False

        convertible_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"  # PPTX
        ]

        return mime_type in convertible_types

    def _is_text_file(self, mime_type: str, filename: str) -> bool:
        """
        Check if file is text-based (affects index).

        Uses existing SAM helper for comprehensive text file detection.
        Covers all text-based MIME types.

        Args:
            mime_type: The MIME type of the file
            filename: The filename

        Returns:
            bool: True if file is text-based
        """
        from ....common.utils.mime_helpers import is_text_based_file
        return is_text_based_file(mime_type, content_bytes=None)

    def _is_original_artifact(self, filename: str) -> bool:
        """Determine if artifact is an original user file (not generated)."""
        return not is_internal_artifact(filename)

    async def _convert_project_artifacts(
        self,
        project: Project,
        files_to_convert: List[Tuple[str, int, str]],
        indexing_enabled: bool
    ) -> List[dict]:
        """
        Convert list of binary artifacts to text.

        Args:
            project: The project
            files_to_convert: List of (filename, version, mime_type)
            indexing_enabled: Safety parameter (should always be True when called)

        Returns:
            List of conversion results (one per successful conversion)
        """
        # Safety check (defense in depth)
        if not indexing_enabled:
            self.logger.warning("_convert_project_artifacts called with indexing disabled")
            return []

        from .file_converter_service import convert_and_save_artifact

        results = []
        storage_session_id = f"project-{project.id}"

        for filename, version, mime_type in files_to_convert:
            try:
                result = await convert_and_save_artifact(
                    artifact_service=self.artifact_service,
                    app_name=self.app_name,
                    user_id=project.user_id,
                    session_id=storage_session_id,
                    source_filename=filename,
                    source_version=version,
                    mime_type=mime_type
                )
                if result:
                    results.append(result)
                    self.logger.info(
                        f"Converted {filename} v{version} → "
                        f"{filename}.converted.txt v{result.get('data_version')}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to convert {filename} v{version}: {e}")
                # Continue with other conversions

        return results

    async def _rebuild_project_index(
        self,
        project: Project,
        indexing_enabled: bool
    ) -> Optional[dict]:
        """
        Rebuild BM25 search index for project.
        Creates new version of project_bm25_index.zip.

        Args:
            project: The project
            indexing_enabled: Safety parameter (should always be True when called)

        Returns:
            Index save result with version info, or None if skipped
        """
        # Safety check (defense in depth)
        if not indexing_enabled:
            self.logger.warning("_rebuild_project_index called with indexing disabled")
            return None

        from .bm25_indexer_service import (
            collect_project_text_files_stream,
            build_bm25_index,
            save_project_index
        )

        try:
            # Stream text files (memory-efficient batch processing)
            text_files_stream = collect_project_text_files_stream(
                artifact_service=self.artifact_service,
                app_name=self.app_name,
                user_id=project.user_id,
                project_id=project.id
            )

            # Build index with streaming (processes files in batches)
            index_zip_bytes, manifest = await build_bm25_index(text_files_stream, project.id)

            # Check if any files were indexed
            if manifest.get("file_count", 0) == 0:
                self.logger.info(f"No text files to index for project {project.id}")
                return None

            # Save index
            result = await save_project_index(
                artifact_service=self.artifact_service,
                app_name=self.app_name,
                user_id=project.user_id,
                project_id=project.id,
                index_zip_bytes=index_zip_bytes,
                manifest=manifest
            )

            return result

        except ValueError as e:
            # Handle case where no documents/chunks were created
            if "No chunks created" in str(e):
                self.logger.info(f"No text files to index for project {project.id}")
                return None
            self.logger.error(f"Index rebuild failed for project {project.id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Index rebuild failed for project {project.id}: {e}")
            return None
