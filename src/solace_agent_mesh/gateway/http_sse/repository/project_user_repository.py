"""
Repository implementation for project user access data operations.
"""
from typing import List, Optional
import uuid

from sqlalchemy.orm import Session as DBSession

from .models import ProjectUserModel
from .entities.project_user import ProjectUser
from ..shared import now_epoch_ms


class ProjectUserRepository:
    """SQLAlchemy implementation of project user repository."""

    def __init__(self, db: DBSession):
        self.db = db

    def add_user_to_project(
        self,
        project_id: str,
        user_id: str,
        role: str,
        added_by_user_id: str
    ) -> ProjectUser:
        """
        Add a user to a project with a specific role.
        
        Args:
            project_id: The project ID
            user_id: The user ID to add
            role: The role to assign (owner, editor, viewer)
            added_by_user_id: The user ID who is granting access
            
        Returns:
            ProjectUser: The created project user access record
        """
        model = ProjectUserModel(
            id=str(uuid.uuid4()),
            project_id=project_id,
            user_id=user_id,
            role=role,
            added_at=now_epoch_ms(),
            added_by_user_id=added_by_user_id,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def get_project_users(self, project_id: str) -> List[ProjectUser]:
        """
        Get all users who have access to a project.
        
        Args:
            project_id: The project ID
            
        Returns:
            List[ProjectUser]: List of users with access to the project
        """
        models = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.project_id == project_id
        ).all()
        return [self._model_to_entity(model) for model in models]

    def get_user_projects_access(self, user_id: str) -> List[ProjectUser]:
        """
        Get all projects a user has access to.
        
        Args:
            user_id: The user ID
            
        Returns:
            List[ProjectUser]: List of project access records for the user
        """
        models = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.user_id == user_id
        ).all()
        return [self._model_to_entity(model) for model in models]

    def get_user_project_access(
        self,
        project_id: str,
        user_id: str
    ) -> Optional[ProjectUser]:
        """
        Get a specific user's access to a project.
        
        Args:
            project_id: The project ID
            user_id: The user ID
            
        Returns:
            Optional[ProjectUser]: The access record if found, None otherwise
        """
        model = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.project_id == project_id,
            ProjectUserModel.user_id == user_id
        ).first()
        
        return self._model_to_entity(model) if model else None

    def update_user_role(
        self,
        project_id: str,
        user_id: str,
        new_role: str
    ) -> Optional[ProjectUser]:
        """
        Update a user's role for a project.
        
        Args:
            project_id: The project ID
            user_id: The user ID
            new_role: The new role to assign
            
        Returns:
            Optional[ProjectUser]: The updated access record if found, None otherwise
        """
        model = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.project_id == project_id,
            ProjectUserModel.user_id == user_id
        ).first()
        
        if not model:
            return None
        
        model.role = new_role
        self.db.commit()
        self.db.refresh(model)
        return self._model_to_entity(model)

    def remove_user_from_project(
        self,
        project_id: str,
        user_id: str
    ) -> bool:
        """
        Remove a user's access to a project.
        
        Args:
            project_id: The project ID
            user_id: The user ID to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        result = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.project_id == project_id,
            ProjectUserModel.user_id == user_id
        ).delete()
        self.db.commit()
        return result > 0

    def user_has_access(
        self,
        project_id: str,
        user_id: str
    ) -> bool:
        """
        Check if a user has access to a project.
        
        Args:
            project_id: The project ID
            user_id: The user ID
            
        Returns:
            bool: True if user has access, False otherwise
        """
        count = self.db.query(ProjectUserModel).filter(
            ProjectUserModel.project_id == project_id,
            ProjectUserModel.user_id == user_id
        ).count()
        return count > 0

    def _model_to_entity(self, model: ProjectUserModel) -> ProjectUser:
        """Convert SQLAlchemy model to domain entity."""
        return ProjectUser(
            id=model.id,
            project_id=model.project_id,
            user_id=model.user_id,
            role=model.role,
            added_at=model.added_at,
            added_by_user_id=model.added_by_user_id,
        )