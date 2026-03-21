"""
Repository implementation for project data access operations.
"""
from typing import List, Optional, Set
import uuid

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

from .interfaces import IProjectRepository
from .models import ProjectModel
from .models.project_user_pin_model import ProjectUserPinModel
from .entities.project import Project
from ..routers.dto.requests.project_requests import ProjectFilter
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


class ProjectRepository(IProjectRepository):
    """SQLAlchemy implementation of project repository."""

    def __init__(self, db: DBSession):
        self.db = db

    # ------------------------------------------------------------------
    # Per-user pin helpers
    # ------------------------------------------------------------------

    def get_pinned_project_ids_for_user(self, user_id: str) -> Set[str]:
        """Return the set of project IDs that *user_id* has pinned."""
        rows = (
            self.db.query(ProjectUserPinModel.project_id)
            .filter(ProjectUserPinModel.user_id == user_id)
            .all()
        )
        return {row[0] for row in rows}

    def toggle_user_pin(self, project_id: str, user_id: str) -> bool:
        """
        Toggle the per-user pin for *project_id* / *user_id*.

        Returns the **new** pinned state (True = now pinned, False = now unpinned).
        """
        existing = (
            self.db.query(ProjectUserPinModel)
            .filter(
                ProjectUserPinModel.project_id == project_id,
                ProjectUserPinModel.user_id == user_id,
            )
            .first()
        )
        if existing:
            self.db.delete(existing)
            self.db.flush()
            return False
        else:
            pin = ProjectUserPinModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                user_id=user_id,
                pinned_at=now_epoch_ms(),
            )
            self.db.add(pin)
            self.db.flush()
            return True

    def is_pinned_by_user(self, project_id: str, user_id: str) -> bool:
        """Return True if *user_id* has pinned *project_id*."""
        return (
            self.db.query(ProjectUserPinModel)
            .filter(
                ProjectUserPinModel.project_id == project_id,
                ProjectUserPinModel.user_id == user_id,
            )
            .first()
        ) is not None

    # ------------------------------------------------------------------
    # Core project CRUD
    # ------------------------------------------------------------------

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

    def get_accessible_projects(
        self,
        user_email: str,
        shared_project_ids: List[str] = None,
        pinned_project_ids: Set[str] = None,
    ) -> List[Project]:
        """
        Get all accessible projects for a user (owned + shared).

        Args:
            user_email: User's email (used for ownership check)
            shared_project_ids: Optional list of project IDs user has shared access to
            pinned_project_ids: Optional set of project IDs the user has pinned.
                                 When provided, ``project.is_pinned`` is resolved
                                 per-user from this set instead of from the DB column.

        Returns:
            List of accessible projects (owned + shared)
        """
        query = self.db.query(ProjectModel).filter(ProjectModel.deleted_at.is_(None))

        # Conservative limits to avoid SQL parameter/query length issues
        # SQLite parameter limit: 999, UUID ~40 chars, keep query under 100KB
        MAX_IN_CLAUSE = 500

        if not shared_project_ids:
            models = query.filter(ProjectModel.user_id == user_email).all()
        elif len(shared_project_ids) <= MAX_IN_CLAUSE:
            # Single query for normal case
            models = query.filter(
                or_(
                    ProjectModel.user_id == user_email,
                    ProjectModel.id.in_(shared_project_ids)
                )
            ).all()
        else:
            # Batch for large share lists
            all_models = []

            owned_models = query.filter(ProjectModel.user_id == user_email).all()
            all_models.extend(owned_models)

            for i in range(0, len(shared_project_ids), MAX_IN_CLAUSE):
                batch = shared_project_ids[i:i + MAX_IN_CLAUSE]
                shared_models = query.filter(ProjectModel.id.in_(batch)).all()
                all_models.extend(shared_models)

            seen = set()
            models = []
            for model in all_models:
                if model.id not in seen:
                    seen.add(model.id)
                    models.append(model)

        return [self._model_to_entity(model, pinned_project_ids) for model in models]

    def get_all_projects(self, pinned_project_ids: Optional[Set[str]] = None) -> List[Project]:
        """
        Get all projects.

        Args:
            pinned_project_ids: When provided, ``is_pinned`` is resolved per-user
                from this set instead of from the legacy DB column.

        Returns:
            List[Project]: List of all non-deleted projects.
        """
        models = self.db.query(ProjectModel).filter(
            ProjectModel.deleted_at.is_(None)
        ).all()

        return [self._model_to_entity(model, pinned_project_ids) for model in models]

    def get_filtered_projects(self, project_filter: ProjectFilter, pinned_project_ids: Optional[Set[str]] = None) -> List[Project]:
        """Get projects based on filter criteria."""
        query = self.db.query(ProjectModel).filter(
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        )

        if project_filter.user_id is not None:
            query = query.filter(ProjectModel.user_id == project_filter.user_id)

        models = query.all()
        return [self._model_to_entity(model, pinned_project_ids) for model in models]

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get a project by its ID.
        """
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None)  # Exclude soft-deleted projects
        ).first()
        return self._model_to_entity(model) if model else None

    def get_by_id_for_user(self, project_id: str, user_id: str) -> Optional[Project]:
        """
        Get a project by its ID and resolve the per-user pin state.
        """
        model = self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id,
            ProjectModel.deleted_at.is_(None),
        ).first()
        if not model:
            return None
        is_pinned = self.is_pinned_by_user(project_id, user_id)
        pinned_ids = {project_id} if is_pinned else set()
        return self._model_to_entity(model, pinned_ids)

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

    def _model_to_entity(
        self,
        model: ProjectModel,
        pinned_project_ids: Optional[Set[str]] = None,
    ) -> Project:
        """
        Convert SQLAlchemy model to domain entity.

        Args:
            model: The SQLAlchemy ProjectModel instance.
            pinned_project_ids: When provided, ``is_pinned`` is resolved from
                this set (per-user semantics).  When None, falls back to the
                legacy ``projects.is_pinned`` column so that callers that don't
                pass a user context still get a sensible value.
        """
        if pinned_project_ids is not None:
            is_pinned = model.id in pinned_project_ids
        else:
            raw_pinned = getattr(model, 'is_pinned', False)
            is_pinned = bool(raw_pinned) if isinstance(raw_pinned, (bool, int)) else False

        return Project(
            id=model.id,
            name=model.name,
            user_id=model.user_id,
            description=model.description,
            system_prompt=model.system_prompt,
            default_agent_id=model.default_agent_id,
            is_pinned=is_pinned,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )
