"""
Business service for project-related operations.
"""

from typing import List, Optional, TYPE_CHECKING
import logging
from fastapi import UploadFile
from datetime import datetime, timezone

from ....agent.utils.artifact_helpers import get_artifact_info_list, save_artifact_with_metadata

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


from ....common.a2a.types import ArtifactInfo
from ..repository.interfaces import IProjectRepository
from ..repository.entities.project import Project

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent


class ProjectService:
    """Service layer for project business logic."""

    def __init__(
        self,
        component: "WebUIBackendComponent" = None,
    ):
        self.component = component
        self.artifact_service = component.get_shared_artifact_service() if component else None
        self.app_name = component.get_config("name", "WebUIBackendApp") if component else "WebUIBackendApp"
        self.logger = logging.getLogger(__name__)

    def _get_repositories(self, db):
        """Create project repository for the given database session."""
        from ..repository.project_repository import ProjectRepository
        return ProjectRepository(db)

    def is_persistence_enabled(self) -> bool:
        """Checks if the service is configured with a persistent backend."""
        return self.component and self.component.database_url is not None

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
            ValueError: If project name is invalid or user_id is missing
        """
        self.logger.info(f"Creating new project '{name}' for user {user_id}")

        # Business validation
        if not name or not name.strip():
            raise ValueError("Project name cannot be empty")

        if not user_id:
            raise ValueError("User ID is required to create a project")

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

        if files and self.artifact_service:
            self.logger.info(
                f"Project {project_domain.id} created, now saving {len(files)} artifacts."
            )
            project_session_id = f"project-{project_domain.id}"
            for file in files:
                content_bytes = await file.read()
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
            self.logger.info(f"Saved {len(files)} artifacts for project {project_domain.id}")

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
        project_repository = self._get_repositories(db)
        return project_repository.get_by_id(project_id, user_id)

    def get_user_projects(self, db, user_id: str) -> List[Project]:
        """
        Get all projects owned by a specific user.

        Args:
            db: Database session
            user_id: The user ID
            
        Returns:
            List[DomainProject]: List of user's projects
        """
        self.logger.debug(f"Retrieving projects for user {user_id}")
        project_repository = self._get_repositories(db)
        db_projects = project_repository.get_user_projects(user_id)
        return db_projects

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
            ValueError: If project not found or access denied
        """
        project = self.get_project(db, project_id, user_id)
        if not project:
            raise ValueError("Project not found or access denied")

        if not self.artifact_service:
            self.logger.warning(f"Attempted to add artifacts to project {project_id} but no artifact service is configured.")
            raise ValueError("Artifact service is not configured")
        
        if not files:
            return []

        self.logger.info(f"Adding {len(files)} artifacts to project {project_id} for user {user_id}")
        storage_session_id = f"project-{project.id}"
        results = []

        for file in files:
            content_bytes = await file.read()
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
        
        self.logger.info(f"Finished adding {len(files)} artifacts to project {project_id}")
        return results

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

        project_repository = self._get_repositories(db)
        self.logger.info(f"Updating project {project_id} for user {user_id}")
        updated_project = project_repository.update(project_id, user_id, update_data)

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
        # First verify the project exists and user has access
        existing_project = self.get_project(db, project_id, user_id)
        if not existing_project:
            return False

        project_repository = self._get_repositories(db)
        self.logger.info(f"Deleting project {project_id} for user {user_id}")
        success = project_repository.delete(project_id, user_id)

        if success:
            self.logger.info(f"Successfully deleted project {project_id}")

        return success

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

        self.logger.info(f"Soft deleting project {project_id} and its associated sessions for user {user_id}")

        project_repository = self._get_repositories(db)
        # Soft delete the project
        success = project_repository.soft_delete(project_id, user_id)

        if success:
            from ..repository.session_repository import SessionRepository
            session_repo = SessionRepository()
            deleted_count = session_repo.soft_delete_by_project(db, project_id, user_id)
            self.logger.info(f"Successfully soft deleted project {project_id} and {deleted_count} associated sessions")

        return success
