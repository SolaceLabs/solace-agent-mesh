"""
Business service for project-related operations.
"""

from typing import List, Optional
import logging
from fastapi import UploadFile
from datetime import datetime, timezone

from ....agent.utils.artifact_helpers import save_artifact_with_metadata

try:
    from google.adk.artifacts import BaseArtifactService
except ImportError:

    class BaseArtifactService:
        pass


from ..repository.interfaces import IProjectRepository
from ..domain.entities.project_domain import ProjectDomain, ProjectFilter, ProjectCopyRequest

GLOBAL_PROJECT_USER_ID = "_global_"


class ProjectService:
    """Service layer for project business logic."""

    def __init__(
        self,
        project_repository: IProjectRepository,
        artifact_service: BaseArtifactService,
        app_name: str,
    ):
        self.project_repository = project_repository
        self.artifact_service = artifact_service
        self.app_name = app_name
        self.logger = logging.getLogger(__name__)

    async def create_project(
        self,
        name: str,
        user_id: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        files: Optional[List[UploadFile]] = None,
    ) -> ProjectDomain:
        """
        Create a new project for a user.
        
        Args:
            name: Project name
            user_id: ID of the user creating the project
            description: Optional project description
            system_prompt: Optional system prompt
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

        # Create the project
        project_domain = self.project_repository.create_project(
            name=name.strip(),
            user_id=user_id,
            description=description.strip() if description else None,
            system_prompt=system_prompt.strip() if system_prompt else None,
            created_by_user_id=user_id,
        )

        if files and self.artifact_service:
            self.logger.info(
                f"Project {project_domain.id} created, now saving {len(files)} artifacts."
            )
            project_session_id = f"project-{project_domain.id}"
            for file in files:
                content_bytes = await file.read()
                await save_artifact_with_metadata(
                    artifact_service=self.artifact_service,
                    app_name=self.app_name,
                    user_id=project_domain.user_id,
                    session_id=project_session_id,
                    filename=file.filename,
                    content_bytes=content_bytes,
                    mime_type=file.content_type,
                    metadata_dict={},
                    timestamp=datetime.now(timezone.utc),
                )
            self.logger.info(f"Saved {len(files)} artifacts for project {project_domain.id}")

        self.logger.info(
            f"Successfully created project {project_domain.id} for user {user_id}"
        )
        return project_domain

    def get_project(self, project_id: str, user_id: str) -> Optional[ProjectDomain]:
        """
        Get a project by ID, ensuring the user has access to it.
        
        Args:
            project_id: The project ID
            user_id: The requesting user ID
            
        Returns:
            Optional[DomainProject]: The project if found and accessible, None otherwise
        """
        db_project = self.project_repository.get_by_id(project_id)
        if not db_project:
            return None
        
        # Check access permissions
        if not self._user_can_access_project(db_project, user_id):
            self.logger.warning(f"User {user_id} attempted to access unauthorized project {project_id}")
            return None
        
        return self._model_to_domain(db_project)

    def get_user_projects(self, user_id: str) -> List[ProjectDomain]:
        """
        Get all projects owned by a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[DomainProject]: List of user's projects
        """
        self.logger.debug(f"Retrieving projects for user {user_id}")
        db_projects = self.project_repository.get_user_projects(user_id)
        return self._models_to_domain_list(db_projects)

    def get_global_projects(self) -> List[ProjectDomain]:
        """
        Get all available global project templates.
        
        Returns:
            List[DomainProject]: List of global project templates
        """
        self.logger.debug("Retrieving global project templates")
        db_projects = self.project_repository.get_global_projects()
        return self._models_to_domain_list(db_projects)

    def update_project(self, project_id: str, user_id: str,
                           name: Optional[str] = None, description: Optional[str] = None, system_prompt: Optional[str] = None) -> Optional[ProjectDomain]:
        """
        Update a project's details.
        
        Args:
            project_id: The project ID
            user_id: The requesting user ID
            name: New project name (optional)
            description: New project description (optional)
            system_prompt: New system prompt (optional)
            
        Returns:
            Optional[DomainProject]: The updated project if successful, None otherwise
        """
        # First verify the project exists and user has access
        existing_project = self.get_project(project_id, user_id)
        if not existing_project:
            return None
        
        # Validate business rules
        if name is not None and not name.strip():
            raise ValueError("Project name cannot be empty")
        
        # Build update data
        update_data = {}
        if name is not None:
            update_data["name"] = name.strip()
        if description is not None:
            update_data["description"] = description.strip() if description else None
        if system_prompt is not None:
            update_data["system_prompt"] = system_prompt.strip() if system_prompt else None
        
        if not update_data:
            # Nothing to update
            return existing_project
        
        self.logger.info(f"Updating project {project_id} for user {user_id}")
        db_project = self.project_repository.update(project_id, update_data)
        
        if db_project:
            self.logger.info(f"Successfully updated project {project_id}")
            return self._model_to_domain(db_project)
        
        return None

    def delete_project(self, project_id: str, user_id: str) -> bool:
        """
        Delete a project.
        
        Args:
            project_id: The project ID
            user_id: The requesting user ID
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        # First verify the project exists and user has access
        existing_project = self.get_project(project_id, user_id)
        if not existing_project:
            return False
        
        # Additional business rule: Users can only delete their own non-global projects
        if existing_project.is_global:
            raise ValueError("Cannot delete global project templates")
        
        if existing_project.user_id != user_id:
            raise ValueError("Users can only delete their own projects")
        
        self.logger.info(f"Deleting project {project_id} for user {user_id}")
        success = self.project_repository.delete(project_id)
        
        if success:
            self.logger.info(f"Successfully deleted project {project_id}")
        
        return success

    def copy_project_from_template(self, copy_request: ProjectCopyRequest) -> Optional[ProjectDomain]:
        """
        Copy a project from a global template.
        
        Args:
            copy_request: The copy request details
            
        Returns:
            Optional[DomainProject]: The copied project if successful, None otherwise
        """
        self.logger.info(f"Copying project from template {copy_request.template_id} for user {copy_request.user_id}")
        
        # Validate business rules
        if not copy_request.new_name or not copy_request.new_name.strip():
            raise ValueError("Project name cannot be empty")
        
        # Verify template exists and is global
        template = self.project_repository.get_by_id(copy_request.template_id)
        if not template or not template.is_global:
            raise ValueError("Template not found or is not a global project")
        
        # Create the copy
        db_project = self.project_repository.copy_from_template(
            template_id=copy_request.template_id,
            name=copy_request.new_name.strip(),
            user_id=copy_request.user_id,
            description=copy_request.new_description
        )
        
        if db_project:
            self.logger.info(f"Successfully copied project {db_project.id} from template {copy_request.template_id}")
            return self._model_to_domain(db_project)
        
        return None

    def get_template_usage_count(self, template_id: str) -> int:
        """
        Get the number of times a template has been copied.
        
        Args:
            template_id: The template project ID
            
        Returns:
            int: Number of copies made from this template
        """
        return self.project_repository.count_template_usage(template_id)

    def _user_can_access_project(self, project, user_id: str) -> bool:
        """
        Check if a user can access a specific project.
        
        Args:
            project: The database project model
            user_id: The requesting user ID
            
        Returns:
            bool: True if user can access the project
        """
        # Global projects are accessible by everyone
        if project.is_global:
            return True
        
        # User projects are only accessible by their owner
        return project.user_id == user_id

    def _model_to_domain(self, project) -> ProjectDomain:
        """Convert database model to domain model."""
        return ProjectDomain(
            id=project.id,
            name=project.name,
            user_id=project.user_id,
            description=project.description,
            system_prompt=project.system_prompt,
            is_global=project.is_global,
            template_id=project.template_id,
            created_by_user_id=project.created_by_user_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _models_to_domain_list(self, projects) -> List[ProjectDomain]:
        """Convert list of database models to domain models."""
        return [self._model_to_domain(project) for project in projects]
