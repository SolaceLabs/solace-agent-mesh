"""
Repository implementation for project data access operations.
"""
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session as DBSession

from .interfaces import IProjectRepository
from .models import ProjectModel
from ..domain.entities.project_domain import ProjectDomain, ProjectFilter
from ..shared import now_epoch_ms


class ProjectRepository(IProjectRepository):
    """SQLAlchemy implementation of project repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      system_prompt: Optional[str] = None,
                      created_by_user_id: Optional[str] = None) -> ProjectDomain:
        """Create a new user project."""
        model = ProjectModel(
            id=str(uuid.uuid4()),
            name=name,
            user_id=user_id,
            description=description,
            system_prompt=system_prompt,
            is_global=False,
            template_id=None,
            created_by_user_id=created_by_user_id or user_id,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def create_global_project(self, name: str, description: Optional[str] = None,
                             created_by_user_id: str = None) -> ProjectDomain:
        """Create a new global project template."""
        model = ProjectModel(
            id=str(uuid.uuid4()),
            name=name,
            user_id=None,  # Global projects have no owner
            description=description,
            system_prompt=None,
            is_global=True,
            template_id=None,
            created_by_user_id=created_by_user_id,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def copy_from_template(self, template_id: str, name: str, user_id: str,
                          description: Optional[str] = None) -> Optional[ProjectDomain]:
        """Create a new project by copying from a template."""
        # First verify template exists and is global
        template = self.get_by_id(template_id)
        if not template or not template.is_global:
            return None

        model = ProjectModel(
            id=str(uuid.uuid4()),
            name=name,
            user_id=user_id,
            description=description or template.description,
            system_prompt=template.system_prompt,
            is_global=False,
            template_id=template_id,
            created_by_user_id=user_id,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def get_user_projects(self, user_id: str) -> List[ProjectDomain]:
        """Get all projects owned by a specific user."""
        models = self.db.query(ProjectModel).filter(ProjectModel.user_id == user_id).all()
        return [self._model_to_entity(model) for model in models]

    def get_global_projects(self) -> List[ProjectDomain]:
        """Get all global project templates."""
        models = self.db.query(ProjectModel).filter(ProjectModel.is_global == True).all()
        return [self._model_to_entity(model) for model in models]

    def get_projects_by_template(self, template_id: str) -> List[ProjectDomain]:
        """Get all projects copied from a specific template."""
        models = self.db.query(ProjectModel).filter(ProjectModel.template_id == template_id).all()
        return [self._model_to_entity(model) for model in models]

    def count_template_usage(self, template_id: str) -> int:
        """Count how many times a template has been copied."""
        count = self.db.query(ProjectModel).filter(ProjectModel.template_id == template_id).count()
        return count

    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[ProjectDomain]:
        """Get projects based on filter criteria."""
        query = self.db.query(ProjectModel)
        
        if project_filter.user_id is not None:
            query = query.filter(ProjectModel.user_id == project_filter.user_id)
        
        if project_filter.is_global is not None:
            query = query.filter(ProjectModel.is_global == project_filter.is_global)
        
        if project_filter.template_id is not None:
            query = query.filter(ProjectModel.template_id == project_filter.template_id)
        
        if project_filter.created_by_user_id is not None:
            query = query.filter(ProjectModel.created_by_user_id == project_filter.created_by_user_id)

        models = query.all()
        return [self._model_to_entity(model) for model in models]

    def get_by_id(self, project_id: str) -> Optional[ProjectDomain]:
        """Get a project by its ID."""
        model = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        return self._model_to_entity(model) if model else None

    def update(self, project_id: str, update_data: dict) -> Optional[ProjectDomain]:
        """Update a project with the given data."""
        model = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not model:
            return None
        
        for field, value in update_data.items():
            if hasattr(model, field):
                setattr(model, field, value)
        
        model.updated_at = now_epoch_ms()
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete(self, project_id: str) -> bool:
        """Delete a project by its ID."""
        result = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).delete()
        self.db.commit()
        return result > 0

    def _model_to_entity(self, model: ProjectModel) -> ProjectDomain:
        """Convert SQLAlchemy model to domain entity."""
        return ProjectDomain(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            description=model.description,
            system_prompt=model.system_prompt,
            is_global=model.is_global,
            template_id=model.template_id,
            created_by_user_id=model.created_by_user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )