"""
Repository implementation for project data access operations.
"""
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

from .interfaces import IProjectRepository
from .models import ProjectModel, ProjectUserModel
from .entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from solace_agent_mesh.shared.api.pagination import PaginationParams


class ProjectRepository(IProjectRepository):
    """SQLAlchemy implementation of project repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def create_project(self, name: str, user_id: str, description: Optional[str] = None,
                      system_prompt: Optional[str] = None, default_agent_id: Optional[str] = None) -> Project:
        """Create a new user project."""
        model = ProjectModel(
            id=str(uuid.uuid4()),
            name=name,
            user_id=user_id,
            description=description,
            system_prompt=system_prompt,
            default_agent_id=default_agent_id,
            created_at=now_epoch_ms(),
        )
        self.db.add(model)
        self.db.flush()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects owned by a specific user."""
        models = self.db.query(ProjectModel).filter(
            ProjectModel.user_id == user_id,
            ProjectModel.deleted_at.is_(None)
        ).all()
        return [self._model_to_entity(model) for model in models]

    def get_accessible_projects(self, user_id: str) -> List[Project]:
        """
        Get all accessible projects for a user (owned + shared).
        Uses a single query with LEFT JOIN for optimal performance.
        """
        # Query for projects where user is owner OR has shared access
        models = self.db.query(ProjectModel).outerjoin(
            ProjectUserModel,
            ProjectModel.id == ProjectUserModel.project_id
        ).filter(
            or_(
                ProjectModel.user_id == user_id,  # Projects owned by user
                ProjectUserModel.user_id == user_id  # Projects shared with user
            ),
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        ).distinct().all()

        return [self._model_to_entity(model) for model in models]

    def get_all_projects(self) -> List[Project]:
        """
        Get all projects.
        
        Returns:
            List[Project]: List of all non-deleted projects.
        """
        models = self.db.query(ProjectModel).filter(
            ProjectModel.deleted_at.is_(None)
        ).all()
        
        return [self._model_to_entity(model) for model in models]

    def get_filtered_projects(self, project_filter: ProjectFilter) -> List[Project]:
        """Get projects based on filter criteria."""
        query = self.db.query(ProjectModel).filter(
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        )
        
        if project_filter.user_id is not None:
            query = query.filter(ProjectModel.user_id == project_filter.user_id)

        models = query.all()
        return [self._model_to_entity(model) for model in models]

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get a project by its ID.
        """
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        ).first()
        return self._model_to_entity(model) if model else None

    def get_owned_or_shared(self, user_id: str, shared_ids: List[str]) -> List[Project]:
        """
        Get projects owned by user OR in the shared IDs list.
        Single query using OR condition for optimal performance.
        """
        query = self.db.query(ProjectModel).filter(
            ProjectModel.deleted_at.is_(None)
        )

        if shared_ids:
            query = query.filter(
                or_(
                    ProjectModel.user_id == user_id,
                    ProjectModel.id.in_(shared_ids)
                )
            )
        else:
            query = query.filter(ProjectModel.user_id == user_id)

        return [self._model_to_entity(model) for model in query.all()]

    def update(self, project_id: str, update_data: dict) -> Optional[Project]:
        """Update a project with the given data."""
        # First, find the project
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        ).first()

        if not model:
            return None  # Project doesn't exist
        
        for field, value in update_data.items():
            if hasattr(model, field):
                setattr(model, field, value)
        
        model.updated_at = now_epoch_ms()
        self.db.flush()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def delete(self, project_id: str) -> bool:
        """Delete a project by its ID."""
        result = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id
        ).delete()
        self.db.flush()
        return result > 0

    def soft_delete(self, project_id: str, deleted_by_user_id: str) -> bool:
        """Soft delete a project by its ID."""
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None)  # Only delete if not already deleted
        ).first()
        
        if not model:
            return False
        
        model.deleted_at = now_epoch_ms()
        model.deleted_by = deleted_by_user_id
        model.updated_at = now_epoch_ms()
        self.db.flush()
        return True

    def _model_to_entity(self, model: ProjectModel) -> Project:
        """Convert SQLAlchemy model to domain entity."""
        return Project(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            description=model.description,
            system_prompt=model.system_prompt,
            default_agent_id=model.default_agent_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )
