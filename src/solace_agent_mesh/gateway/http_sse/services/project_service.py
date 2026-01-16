"""
Business service for project-related operations.
"""

from typing import List, Optional, TYPE_CHECKING, Dict
import logging
import json
import zipfile
from io import BytesIO
from fastapi import UploadFile
from datetime import datetime, timezone

from ....agent.utils.artifact_helpers import get_artifact_info_list, save_artifact_with_metadata, get_artifact_counts_batch

# Default max upload size (50MB) - matches gateway_max_upload_size_bytes default
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 52428800
# Default max ZIP upload size (100MB) - for project import ZIP files
DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 104857600

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


from ....common.a2a.types import ArtifactInfo
from ....common.middleware.registry import MiddlewareRegistry
from ....services.resource_sharing_service import ResourceSharingService, ResourceType, SharingRole
from ..repository.interfaces import IProjectRepository
from ..repository.entities.project import Project

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


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
        
        # Get max upload size from component config, with fallback to default
        # Ensure values are integers for proper formatting
        max_upload_config = (
            component.get_config("gateway_max_upload_size_bytes", DEFAULT_MAX_UPLOAD_SIZE_BYTES)
            if component else DEFAULT_MAX_UPLOAD_SIZE_BYTES
        )
        self.max_upload_size_bytes = int(max_upload_config) if isinstance(max_upload_config, (int, float)) else DEFAULT_MAX_UPLOAD_SIZE_BYTES
        
        # Get max ZIP upload size from component config, with fallback to default (100MB)
        max_zip_config = (
            component.get_config("gateway_max_zip_upload_size_bytes", DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES)
            if component else DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES
        )
        self.max_zip_upload_size_bytes = int(max_zip_config) if isinstance(max_zip_config, (int, float)) else DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES
        
        self.logger.info(
            "[ProjectService] Initialized with max_upload_size_bytes=%d (%.2f MB), "
            "max_zip_upload_size_bytes=%d (%.2f MB)",
            self.max_upload_size_bytes,
            self.max_upload_size_bytes / (1024*1024),
            self.max_zip_upload_size_bytes,
            self.max_zip_upload_size_bytes / (1024*1024)
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
            if total_bytes_read > self.max_upload_size_bytes:
                error_msg = (
                    f"File '{file.filename}' rejected: size exceeds maximum "
                    f"{self.max_upload_size_bytes:,} bytes "
                    f"({self.max_upload_size_bytes / (1024*1024):.2f} MB). "
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

        project_repository = self._get_repositories(db)

        # Check for duplicate project name for this user
        existing_projects = project_repository.get_user_projects(user_id)
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

        if validated_files and self.artifact_service:
            self.logger.info(
                f"Project {project_domain.id} created, now saving {len(validated_files)} artifacts."
            )
            project_session_id = f"project-{project_domain.id}"
            for file, content_bytes in validated_files:
                metadata = {"source": "project"}
                if file_metadata and file.filename in file_metadata:
                    desc = file_metadata[file.filename]
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
        if not self._can_view_project(db, project_id, user_id):
            return None

        # Convert to domain entity
        project_repository = self._get_repositories(db)
        return project_repository._model_to_entity(project_model)

    def get_user_projects(self, db, user_id: str) -> List[Project]:
        """
        Get all projects accessible by a specific user (owned + shared).

        Args:
            db: Database session
            user_id: The user ID

        Returns:
            List[DomainProject]: List of user's accessible projects (owned + shared)
        """
        self.logger.debug(f"Retrieving accessible projects for user {user_id}")
        project_repository = self._get_repositories(db)
        db_projects = project_repository.get_accessible_projects(user_id)
        return db_projects

    async def get_user_projects_with_counts(self, db, user_id: str) -> List[tuple[Project, int]]:
        """
        Get all projects owned by a specific user with artifact counts.
        Uses batch counting for efficiency.

        Args:
            db: Database session
            user_id: The user ID
            
        Returns:
            List[tuple[Project, int]]: List of tuples (project, artifact_count)
        """
        self.logger.debug(f"Retrieving projects with artifact counts for user {user_id}")
        projects = self.get_user_projects(db, user_id)
        
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
                user_id=user_id,
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
            self.logger.warning(f"Attempted to get artifacts for project {project_id} but no artifact service is configured.")
            return []

        storage_user_id = project.user_id
        storage_session_id = f"project-{project.id}"

        self.logger.info(f"Fetching artifacts for project {project.id} with storage session {storage_session_id} and user {storage_user_id}")

        artifacts = await get_artifact_info_list(
            artifact_service=self.artifact_service,
            app_name=self.app_name,
            user_id=storage_user_id,
            session_id=storage_session_id,
        )
        return artifacts

    async def add_artifacts_to_project(
        self,
        db,
        project_id: str,
        user_id: str,
        files: List[UploadFile],
        file_metadata: Optional[dict] = None
    ) -> List[dict]:
        """
        Add one or more artifacts to a project.
        
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

        # Check edit artifacts permission (Owner + Administrator + Editor)
        if not self._can_edit_artifacts(db, project_id, user_id):
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

        self.logger.info(f"Adding {len(validated_files)} artifacts to project {project_id} for user {user_id}")
        storage_session_id = f"project-{project.id}"
        results = []

        for file, content_bytes in validated_files:
            metadata = {"source": "project"}
            if file_metadata and file.filename in file_metadata:
                desc = file_metadata[file.filename]
                if desc:
                    metadata["description"] = desc
            
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

        # Check edit artifacts permission (Owner + Administrator + Editor)
        if not self._can_edit_artifacts(db, project_id, user_id):
            return False

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

    async def delete_artifact_from_project(self, db, project_id: str, user_id: str, filename: str) -> bool:
        """
        Deletes an artifact from a project.
        
        Args:
            db: The database session
            project_id: The project ID
            user_id: The requesting user ID
            filename: The filename of the artifact to delete
            
        Returns:
            bool: True if deletion was attempted, False if project not found
            
        Raises:
            ValueError: If user cannot modify the project or artifact service is missing
        """
        project = self.get_project(db, project_id, user_id)
        if not project:
            return False

        # Check delete artifacts permission (Owner + Administrator only)
        if not self._can_delete_artifacts(db, project_id, user_id):
            return False

        if not self.artifact_service:
            self.logger.warning(f"Attempted to delete artifact from project {project_id} but no artifact service is configured.")
            raise ValueError("Artifact service is not configured")

        storage_session_id = f"project-{project.id}"
        
        self.logger.info(f"Deleting artifact '{filename}' from project {project_id} for user {user_id}")
        
        await self.artifact_service.delete_artifact(
            app_name=self.app_name,
            user_id=project.user_id, # Always use project owner's ID for storage
            session_id=storage_session_id,
            filename=filename,
        )
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

        # Check edit permission (Owner + Administrator + Editor)
        if not self._can_edit_project(db, project_id, user_id):
            return None

        from ..repository.models import ProjectModel
        from ....shared.utils.timestamp_utils import now_epoch_ms

        # Get project without access check
        model = db.query(ProjectModel).filter_by(
            id=project_id, deleted_at=None
        ).first()

        if not model:
            return None

        # Update fields
        for field, value in update_data.items():
            if hasattr(model, field):
                setattr(model, field, value)

        model.updated_at = now_epoch_ms()
        db.flush()
        db.refresh(model)

        self.logger.info(f"Successfully updated project {project_id}")

        project_repository = self._get_repositories(db)
        return project_repository._model_to_entity(model)

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
        # First verify the project exists and user has access
        existing_project = self.get_project(db, project_id, user_id)
        if not existing_project:
            return False

        # Check delete permission (Owner + Administrator only)
        if not self._can_delete_project(db, project_id, user_id):
            return False

        from ..repository.models import ProjectModel

        # Delete directly without repository access check
        result = db.query(ProjectModel).filter_by(
            id=project_id, deleted_at=None
        ).delete(synchronize_session=False)

        if result > 0:
            self.logger.info(f"Successfully deleted project {project_id}")
            return True

        return False

    def soft_delete_project(self, db, project_id: str, user_id: str) -> bool:
        """
        Soft delete a project (mark as deleted without removing from database).
        Also cascades soft delete to all sessions associated with this project.

        Args:
            db: Database session
            project_id: The project ID
            user_id: The requesting user ID

        Returns:
            bool: True if soft deleted successfully, False otherwise
        """
        # First verify the project exists and user has access
        existing_project = self.get_project(db, project_id, user_id)
        if not existing_project:
            self.logger.warning(f"Attempted to soft delete non-existent project {project_id} by user {user_id}")
            return False

        # Check delete permission (Owner + Administrator only)
        if not self._can_delete_project(db, project_id, user_id):
            return False

        self.logger.info(f"Soft deleting project {project_id} and its associated sessions for user {user_id}")

        from ..repository.models import ProjectModel
        from ....shared.utils.timestamp_utils import now_epoch_ms

        # Soft delete directly
        model = db.query(ProjectModel).filter_by(
            id=project_id, deleted_at=None
        ).first()

        if not model:
            return False

        model.deleted_at = now_epoch_ms()
        db.flush()

        # Cascade to sessions
        from ..repository.session_repository import SessionRepository
        session_repo = SessionRepository()
        deleted_count = session_repo.soft_delete_by_project(db, project_id, user_id)
        self.logger.info(f"Successfully soft deleted project {project_id} and {deleted_count} associated sessions")

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
                                f'artifacts/{artifact.filename}',
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
        preserve_name: bool = False, custom_name: Optional[str] = None
    ) -> tuple[Project, int, List[str]]:
        """
        Import project from ZIP file.
        
        Args:
            db: Database session
            zip_file: Uploaded ZIP file
            user_id: The importing user ID
            preserve_name: Whether to preserve original name
            custom_name: Custom name to use (overrides preserve_name)
            
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
            max_size_mb = self.max_zip_upload_size_bytes / (1024 * 1024)
            file_size_mb = zip_size / (1024 * 1024)
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
                    artifact_files = [
                        name for name in zip_ref.namelist()
                        if name.startswith('artifacts/') and name != 'artifacts/'
                    ]
                    
                    for artifact_path in artifact_files:
                        try:
                            filename = artifact_path.replace('artifacts/', '')
                            content_bytes = zip_ref.read(artifact_path)
                            
                            # Skip oversized artifacts with a warning (don't fail the entire import)
                            if len(content_bytes) > self.max_upload_size_bytes:
                                max_size_mb = self.max_upload_size_bytes / (1024 * 1024)
                                file_size_mb = len(content_bytes) / (1024 * 1024)
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
        existing_projects = project_repository.get_user_projects(user_id)
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
            user_id: The user ID

        Returns:
            bool: True if user is the project owner, False otherwise
        """
        from ..repository.models import ProjectModel

        # Check if user is the owner
        project = db.query(ProjectModel).filter_by(
            id=project_id, user_id=user_id, deleted_at=None
        ).first()
        return project is not None

    def _get_shared_access_role(self, db, project_id: str, user_id: str) -> Optional[str]:
        """
        Get user's shared access role for the project.
        
        Args:
            db: Database session
            project_id: The project ID
            user_id: The user ID to check
            
        Returns:
            Optional[str]: "administrator", "editor", "viewer", or None if no shared access
        """
        shared_resources = self._resource_sharing_service.get_shared_resources(
            session=db, user_id=user_id, resource_type=ResourceType.PROJECT
        )
        for resource in shared_resources:
            if resource['resource_id'] == project_id:
                return resource['role']
        return None

    def _get_user_role(self, db, project_id: str, user_id: str) -> Optional[str]:
        """
        Get user's role on a project (for backward compatibility).

        Args:
            db: Database session
            project_id: The project ID
            user_id: The user ID

        Returns:
            Optional[str]: "owner", "administrator", "editor", "viewer", or None if no access
        """
        # Check if user is the owner first
        if self._is_project_owner(db, project_id, user_id):
            return "owner"

        # Check shared access role
        return self._get_shared_access_role(db, project_id, user_id)

    def _can_view_project(self, db, project_id: str, user_id: str) -> bool:
        return (
            self._is_project_owner(db, project_id, user_id) or
            self._get_shared_access_role(db, project_id, user_id) is not None
        )

    def _can_edit_project(self, db, project_id: str, user_id: str) -> bool:
        if self._is_project_owner(db, project_id, user_id):
            return True
        role = self._get_shared_access_role(db, project_id, user_id)
        return role in ["administrator", "editor"]

    def _can_delete_project(self, db, project_id: str, user_id: str) -> bool:
        if self._is_project_owner(db, project_id, user_id):
            return True
        role = self._get_shared_access_role(db, project_id, user_id)
        return role == "administrator"

    def _can_share_project(self, db, project_id: str, user_id: str) -> bool:
        if self._is_project_owner(db, project_id, user_id):
            return True
        role = self._get_shared_access_role(db, project_id, user_id)
        return role == "administrator"

    def _can_edit_artifacts(self, db, project_id: str, user_id: str) -> bool:
        if self._is_project_owner(db, project_id, user_id):
            return True
        role = self._get_shared_access_role(db, project_id, user_id)
        return role in ["administrator", "editor"]

    def _can_delete_artifacts(self, db, project_id: str, user_id: str) -> bool:
        if self._is_project_owner(db, project_id, user_id):
            return True
        role = self._get_shared_access_role(db, project_id, user_id)
        return role == "administrator"

    async def share_project(
        self, db, project_id: str, target_email: str, role: str, sharing_user_id: str
    ) -> dict:
        """
        Share a project with another user by email.

        Args:
            db: Database session
            project_id: The project ID to share
            target_email: Email of user to share with
            role: Role to assign ("editor" or "viewer")
            sharing_user_id: User ID of person sharing the project

        Returns:
            dict: Success message with user_id

        Raises:
            ValueError: If user is not owner, role is invalid, user not found, or already has access
            HTTPException: If identity service not configured (501)
        """
        from fastapi import HTTPException

        # Verify the sharing user can share (Owner + Administrator)
        if not self._can_share_project(db, project_id, sharing_user_id):
            raise ValueError("Only project owner or administrator can share")

        # Validate role - allow administrator role as well
        if role not in ["administrator", "editor", "viewer"]:
            raise ValueError(f"Invalid role: {role}")

        # Look up user by email using identity service
        identity_service = self.component.identity_service
        if not identity_service:
            raise HTTPException(501, "Identity service not configured")

        results = await identity_service.search_users(target_email, limit=1)
        if not results or results[0].get("email", "").lower() != target_email.lower():
            raise ValueError(f"User not found: {target_email}")

        target_user_id = results[0]["id"]

        # Check if user already has access via ResourceSharingService
        if self._resource_sharing_service.can_access_resource(
            session=db, resource_id=project_id, resource_type=ResourceType.PROJECT, user_id=target_user_id
        ):
            raise ValueError("User already has access to this project")

        # Add the collaborator via ResourceSharingService
        success = self._resource_sharing_service.share_resource(
            session=db, resource_id=project_id, resource_type=ResourceType.PROJECT, 
            shared_with_user_id=target_user_id, role=SharingRole(role), shared_by_user_id=sharing_user_id
        )
        if not success:
            raise ValueError("Failed to share project")

        self.logger.info(
            f"Shared project {project_id} with {target_email} as {role} by user {sharing_user_id}"
        )
        return {"message": "Project shared successfully", "user_id": target_user_id}

    def get_collaborators(self, db, project_id: str, requesting_user_id: str) -> dict:
        """
        Get all collaborators for a project.

        Args:
            db: Database session
            project_id: The project ID
            requesting_user_id: User ID of person requesting the list

        Returns:
            dict: Contains project_id, owner info, and list of collaborators

        Raises:
            ValueError: If user doesn't have access or project doesn't exist
        """
        from ..repository.models import ProjectModel

        # Verify user has access to this project
        if not self._can_view_project(db, project_id, requesting_user_id):
            raise ValueError("Access denied")

        # Get the project to find the owner
        project = db.query(ProjectModel).filter_by(
            id=project_id, deleted_at=None
        ).first()
        if not project:
            raise ValueError("Project not found")

        # Get all collaborators from ResourceSharingService
        shared_resources = self._resource_sharing_service.get_shared_resources(
            session=db, user_id=None, resource_type=ResourceType.PROJECT  # Get all shared resources for this project type
        )
        # Filter for this specific project
        collaborators = []
        for resource in shared_resources:
            if resource['resource_id'] == project_id:
                collaborators.append({
                    "user_id": resource['shared_with_user_id'],
                    "role": resource['role'],
                    "added_at": resource['created_at'],
                    "added_by_user_id": resource['shared_by_user_id'],
                })

        return {
            "project_id": project_id,
            "owner": {
                "user_id": project.user_id,
                "role": "owner",
                "added_at": project.created_at,
                "added_by_user_id": project.user_id,
            },
            "collaborators": collaborators,
        }

    def update_collaborator_role(
        self, db, project_id: str, target_user_id: str, new_role: str, requesting_user_id: str
    ) -> bool:
        """
        Update a collaborator's role (owner only).

        Args:
            db: Database session
            project_id: The project ID
            target_user_id: User ID of collaborator to update
            new_role: New role to assign ("editor" or "viewer")
            requesting_user_id: User ID of person making the change

        Returns:
            bool: True if successful

        Raises:
            ValueError: If user is not owner, role is invalid, or collaborator not found
        """

        # Verify requesting user can manage collaborators (Owner + Administrator)
        if not self._can_share_project(db, project_id, requesting_user_id):
            raise ValueError("Only owner or administrator can update roles")

        # Validate new role - allow administrator as well
        if new_role not in ["administrator", "editor", "viewer"]:
            raise ValueError(f"Invalid role: {new_role}")

        # Check if target user currently has access
        if not self._resource_sharing_service.can_access_resource(
            session=db, resource_id=project_id, resource_type=ResourceType.PROJECT, user_id=target_user_id
        ):
            raise ValueError("Collaborator not found")

        # Update the role by re-sharing with new role
        success = self._resource_sharing_service.share_resource(
            session=db, resource_id=project_id, resource_type=ResourceType.PROJECT, shared_with_user_id=target_user_id,
            role=SharingRole(new_role), shared_by_user_id=requesting_user_id
        )
        if not success:
            raise ValueError("Failed to update collaborator role")

        self.logger.info(
            f"Updated user {target_user_id} to {new_role} on project {project_id}"
        )
        return True

    def remove_collaborator(
        self, db, project_id: str, target_user_id: str, requesting_user_id: str
    ) -> bool:
        """
        Remove a collaborator from a project (owner only).

        Args:
            db: Database session
            project_id: The project ID
            target_user_id: User ID of collaborator to remove
            requesting_user_id: User ID of person removing access

        Returns:
            bool: True if successful

        Raises:
            ValueError: If user is not owner or collaborator not found
        """

        # Verify requesting user can manage collaborators (Owner + Administrator)
        if not self._can_share_project(db, project_id, requesting_user_id):
            raise ValueError("Only owner or administrator can remove collaborators")

        # Remove the collaborator via ResourceSharingService
        success = self._resource_sharing_service.unshare_resource(
            session=db, resource_id=project_id, resource_type=ResourceType.PROJECT, shared_with_user_id=target_user_id
        )
        if not success:
            raise ValueError("Collaborator not found")

        self.logger.info(
            f"Removed user {target_user_id} from project {project_id}"
        )
        return True
