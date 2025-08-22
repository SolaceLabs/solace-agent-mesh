"""
Repository for project data access operations.
"""

from abc import abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime

from .base_repository import BaseRepository, IBaseRepository
from ..persistence.database_service import DatabaseService
from ...database.models import Project
from ...business.domain.project_domain import ProjectDomain, ProjectFilter
from ...shared.types import FilterInfo


class IProjectRepository(IBaseRepository[Project]):
    """Interface for project repository operations."""

    @abstractmethod
    def create_project(self, name: str, user_id: str, description: Optional[str] = None, 
                      created_by_user_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        pass

    @abstractmethod
    def create_global_project(self, name: str, description: Optional[str] = None, 
                             created_by_user_id: str = None) -> Project:
        """Create a new global project template."""
        pass

    @abstractmethod
    def copy_from_template(self, template_id: str, name: str, user_id: str, 
                          description: Optional[str] = None) -> Optional[Project]:
        """Create a new project by copying from a template."""
        pass

    @abstractmethod
    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        pass

    @abstractmethod
    def get_global_projects(self) -> List[Project]:
        """Get all global project templates."""
        pass

    @abstractmethod
    def get_projects_by_template(self, template_id: str) -> List[Project]:
        """Get all projects copied from a specific template."""
        pass

    @abstractmethod
    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
        pass

    @abstractmethod
    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
        """Get projects based on filter criteria."""
        pass



class ProjectRepository(BaseRepository[Project], IProjectRepository):
    """Repository for project-related database operations."""

    def __init__(self, db_service: DatabaseService):
        super().__init__(db_service, Project)

    def create_project(self, name: str, user_id: str, description: Optional[str] = None, 
                      created_by_user_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        project_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "user_id": user_id,
            "description": description,
            "is_global": False,
            "template_id": None,
            "created_by_user_id": created_by_user_id or user_id,
        }
        return self.create(project_data)

    def create_global_project(self, name: str, description: Optional[str] = None, 
                             created_by_user_id: str = None) -> Project:
        """Create a new global project template."""
        project_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "user_id": None,  # Global projects have no owner
            "description": description,
            "is_global": True,
            "template_id": None,
            "created_by_user_id": created_by_user_id,
        }
        return self.create(project_data)

    def copy_from_template(self, template_id: str, name: str, user_id: str, 
                          description: Optional[str] = None) -> Optional[Project]:
        """Create a new project by copying from a template."""
        # First verify template exists and is global
        template = self.get_by_id(template_id)
        if not template or not template.is_global:
            return None

        project_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "user_id": user_id,
            "description": description or template.description,
            "is_global": False,
            "template_id": template_id,
            "created_by_user_id": user_id,
        }
        return self.create(project_data)

    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        filters = [FilterInfo(field="user_id", operator="eq", value=user_id)]
        return self.get_all(filters=filters)

    def get_global_projects(self) -> List[Project]:
        """Get all global project templates."""
        filters = [FilterInfo(field="is_global", operator="eq", value=True)]
        return self.get_all(filters=filters)

    def get_projects_by_template(self, template_id: str) -> List[Project]:
        """Get all projects copied from a specific template."""
        filters = [FilterInfo(field="template_id", operator="eq", value=template_id)]
        return self.get_all(filters=filters)

    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
        filters = [FilterInfo(field="template_id", operator="eq", value=template_id)]
        return self.count(filters=filters)

    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
        """Get projects based on filter criteria."""
        filters = []
        
        if project_filter.user_id is not None:
            filters.append(FilterInfo(field="user_id", operator="eq", value=project_filter.user_id))
        
        if project_filter.is_global is not None:
            filters.append(FilterInfo(field="is_global", operator="eq", value=project_filter.is_global))
        
        if project_filter.template_id is not None:
            filters.append(FilterInfo(field="template_id", operator="eq", value=project_filter.template_id))
        
        if project_filter.created_by_user_id is not None:
            filters.append(FilterInfo(field="created_by_user_id", operator="eq", value=project_filter.created_by_user_id))

        return self.get_all(filters=filters)

