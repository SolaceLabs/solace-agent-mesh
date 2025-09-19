"""
Business service for project-related operations.
"""

from typing import List, Optional, TYPE_CHECKING
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
from ..repository.entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter, ProjectCopyRequest

if TYPE_CHECKING:
    from ..component import WebUIBackendComponent

GLOBAL_PROJECT_USER_ID = "_global_"


class ProjectService:
    """Service layer for project business logic."""

    def __init__(
        self,
        project_repository: IProjectRepository,
        component: "WebUIBackendComponent" = None,
    ):
        self.project_repository = project_repository
        self.component = component
        self.artifact_service = component.get_shared_artifact_service() if component else None
        self.app_name = component.get_config("name", "WebUIBackendApp") if component else "WebUIBackendApp"
        self.logger = logging.getLogger(__name__)

    async def create_project(
        self,
        name: str,
        user_id: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        files: Optional[List[UploadFile]] = None,
    ) -> Project:
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

    def get_project(self, project_id: str, user_id: str) -> Optional[Project]:
        """
        Get a project by ID, ensuring the user has access to it.
        
        Args:
            project_id: The project ID
            user_id: The requesting user ID
            
        Returns:
            Optional[Project]: The project if found and accessible, None otherwise
        """
        # Repository now handles user access validation
        return self.project_repository.get_by_id(project_id, user_id)

    def get_user_projects(self, user_id: str) -> List[Project]:
        """
        Get all projects owned by a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[DomainProject]: List of user's projects
        """
        self.logger.debug(f"Retrieving projects for user {user_id}")
        db_projects = self.project_repository.get_user_projects(user_id)
        return db_projects

    def get_global_projects(self) -> List[Project]:
        """
        Get all available global project templates.
        
        Returns:
            List[DomainProject]: List of global project templates
        """
        self.logger.debug("Retrieving global project templates")
        db_projects = self.project_repository.get_global_projects()
        return db_projects

    def update_project(self, project_id: str, user_id: str,
                           name: Optional[str] = None, description: Optional[str] = None, system_prompt: Optional[str] = None) -> Optional[Project]:
        """
        Update a project's details.
        
        Args:
            project_id: The project ID
            user_id: The requesting user ID
            name: New project name (optional)
            description: New project description (optional)
            system_prompt: New system prompt (optional)
            
        Returns:
            Optional[Project]: The updated project if successful, None otherwise
        """
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
            # Nothing to update - get existing project
            return self.get_project(project_id, user_id)
        
        self.logger.info(f"Updating project {project_id} for user {user_id}")
        updated_project = self.project_repository.update(project_id, user_id, update_data)
        
        if updated_project:
            self.logger.info(f"Successfully updated project {project_id}")
        
        return updated_project

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
        
        self.logger.info(f"Deleting project {project_id} for user {user_id}")
        success = self.project_repository.delete(project_id, user_id)
        
        if success:
            self.logger.info(f"Successfully deleted project {project_id}")
        
        return success

    def copy_project_from_template(self, copy_request: ProjectCopyRequest) -> Optional[Project]:
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
        
        return db_project

    def get_template_usage_count(self, template_id: str) -> int:
        """
        Get the number of times a template has been copied.
        
        Args:
            template_id: The template project ID
            
        Returns:
            int: Number of copies made from this template
        """
        return self.project_repository.count_template_usage(template_id)

