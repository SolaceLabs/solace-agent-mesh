"""
Repository for project data access operations.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime
from ...infrastructure.persistence.database_service import DatabaseService
from ...infrastructure.persistence.models import Project
from ..entities.project_domain import ProjectDomain, ProjectFilter
from ...shared.types import FilterInfo


class IProjectRepository(ABC):
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



class ProjectRepository(IProjectRepository):
    """Repository for project-related database operations."""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      created_by_user_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        with self.db_service.session_scope() as session:
            project = Project(
                id=str(uuid.uuid4()),
                name=name,
                user_id=user_id,
                description=description,
                is_global=False,
                template_id=None,
                created_by_user_id=created_by_user_id or user_id,
                created_at=datetime.now(),
            )
            session.add(project)
            session.flush()
            session.refresh(project)
            return project

    def create_global_project(self, name: str, description: Optional[str] = None,
                             created_by_user_id: str = None) -> Project:
        """Create a new global project template."""
        with self.db_service.session_scope() as session:
            project = Project(
                id=str(uuid.uuid4()),
                name=name,
                user_id=None,  # Global projects have no owner
                description=description,
                is_global=True,
                template_id=None,
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(),
            )
            session.add(project)
            session.flush()
            session.refresh(project)
            return project

    def copy_from_template(self, template_id: str, name: str, user_id: str,
                          description: Optional[str] = None) -> Optional[Project]:
        """Create a new project by copying from a template."""
        # First verify template exists and is global
        template = self.get_by_id(template_id)
        if not template or not template.is_global:
            return None

        with self.db_service.session_scope() as session:
            project = Project(
                id=str(uuid.uuid4()),
                name=name,
                user_id=user_id,
                description=description or template.description,
                is_global=False,
                template_id=template_id,
                created_by_user_id=user_id,
                created_at=datetime.now(),
            )
            session.add(project)
            session.flush()
            session.refresh(project)
            return project

    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        with self.db_service.read_only_session() as session:
            projects = session.query(Project).filter(Project.user_id == user_id).all()
            return projects

    def get_global_projects(self) -> List[Project]:
        """Get all global project templates."""
        with self.db_service.read_only_session() as session:
            projects = session.query(Project).filter(Project.is_global == True).all()
            return projects

    def get_projects_by_template(self, template_id: str) -> List[Project]:
        """Get all projects copied from a specific template."""
        with self.db_service.read_only_session() as session:
            projects = session.query(Project).filter(Project.template_id == template_id).all()
            return projects

    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
        with self.db_service.read_only_session() as session:
            count = session.query(Project).filter(Project.template_id == template_id).count()
            return count

    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
        """Get projects based on filter criteria."""
        with self.db_service.read_only_session() as session:
            query = session.query(Project)
            
            if project_filter.user_id is not None:
                query = query.filter(Project.user_id == project_filter.user_id)
            
            if project_filter.is_global is not None:
                query = query.filter(Project.is_global == project_filter.is_global)
            
            if project_filter.template_id is not None:
                query = query.filter(Project.template_id == project_filter.template_id)
            
            if project_filter.created_by_user_id is not None:
                query = query.filter(Project.created_by_user_id == project_filter.created_by_user_id)

            return query.all()

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Get a project by its ID."""
        with self.db_service.read_only_session() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            return project

    def update(self, project_id: str, update_data: dict) -> Optional[Project]:
        """Update a project with the given data."""
        with self.db_service.session_scope() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None
            
            for field, value in update_data.items():
                if hasattr(project, field):
                    setattr(project, field, value)
            
            project.updated_at = datetime.now()
            session.flush()
            session.refresh(project)
            return project

    def delete(self, project_id: str) -> bool:
        """Delete a project by its ID."""
        with self.db_service.session_scope() as session:
            project = session.query(Project).filter(Project.id == project_id).first()
            if not project:
                return False
            
            session.delete(project)
            return True
