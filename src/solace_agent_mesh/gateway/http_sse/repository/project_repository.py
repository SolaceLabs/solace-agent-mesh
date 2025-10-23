"""
Repository implementation for project data access operations.
"""
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session as DBSession

from .interfaces import IProjectRepository
from .models import ProjectModel
from .entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter
from ..shared import now_epoch_ms


class ProjectRepository(IProjectRepository):
    """SQLAlchemy implementation of project repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      system_prompt: Optional[str] = None,
                      created_by_user_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        model = ProjectModel(
            id=str(uuid.uuid4()),
            name=name,
            user_id=user_id,
            description=description,
            system_prompt=system_prompt,
            created_by_user_id=created_by_user_id or user_id,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        models = self.db.query(ProjectModel).filter(ProjectModel.user_id == user_id).all()
        return [self._model_to_entity(model) for model in models]

    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
        """Get projects based on filter criteria."""
        query = self.db.query(ProjectModel)
        
        if project_filter.user_id is not None:
            query = query.filter(ProjectModel.user_id == project_filter.user_id)
        
        if project_filter.created_by_user_id is not None:
            query = query.filter(ProjectModel.created_by_user_id == project_filter.created_by_user_id)

        models = query.all()
        return [self._model_to_entity(model) for model in models]

    def get_by_id(self, project_id: str, user_id: str) -> Optional[Project]:
        """Get a project by its ID, ensuring user access."""
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.user_id == user_id
        ).first()
        
        return self._model_to_entity(model) if model else None

    def update(self, project_id: str, user_id: str, update_data: dict) -> Optional[Project]:
        """Update a project with the given data, ensuring user access."""
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.user_id == user_id  # Only allow updates to user's own projects
        ).first()
        
        if not model:
            return None
        
        for field, value in update_data.items():
            if hasattr(model, field):
                setattr(model, field, value)
        
        model.updated_at = now_epoch_ms()
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete(self, project_id: str, user_id: str) -> bool:
        """Delete a project by its ID, ensuring user access."""
        result = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.user_id == user_id  # Only allow deletion of user's own projects
        ).delete()
        self.db.commit()
        return result > 0

    def _model_to_entity(self, model: ProjectModel) -> Project:
        """Convert SQLAlchemy model to domain entity."""
        return Project(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            description=model.description,
            system_prompt=model.system_prompt,
            created_by_user_id=model.created_by_user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
