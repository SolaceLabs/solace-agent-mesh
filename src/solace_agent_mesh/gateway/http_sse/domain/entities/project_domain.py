"""
Domain models for project-related business logic.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ProjectDomain(BaseModel):
    """Project domain entity with business rules."""
    
    id: str
    name: str = Field(..., min_length=1, max_length=255)
    user_id: Optional[str] = None  # None for global projects
    description: Optional[str] = Field(None, max_length=1000)
    system_prompt: Optional[str] = Field(None, max_length=4000)
    is_global: bool = False
    template_id: Optional[str] = None  # Links to original template if copied
    created_by_user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @property
    def is_template(self) -> bool:
        """Check if this project is a global template."""
        return self.is_global and self.template_id is None
    
    @property
    def is_copy(self) -> bool:
        """Check if this project was copied from a template."""
        return not self.is_global and self.template_id is not None
    
    @property
    def is_original(self) -> bool:
        """Check if this is an original user-created project."""
        return not self.is_global and self.template_id is None
    
    def update_name(self, new_name: str) -> None:
        """Update project name with validation."""
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("Project name cannot be empty")
        if len(new_name) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        
        self.name = new_name.strip()
        self.updated_at = datetime.now(timezone.utc)
    
    def update_description(self, new_description: Optional[str]) -> None:
        """Update project description with validation."""
        if new_description is not None:
            if len(new_description) > 1000:
                raise ValueError("Project description cannot exceed 1000 characters")
            self.description = new_description.strip() if new_description else None
        else:
            self.description = None
        
        self.updated_at = datetime.now(timezone.utc)
    
    def can_be_accessed_by_user(self, user_id: str) -> bool:
        """Check if project can be accessed by the given user."""
        # Global projects are accessible by everyone
        if self.is_global:
            return True
        # User projects are only accessible by their owner
        return self.user_id == user_id
    
    def can_be_edited_by_user(self, user_id: str) -> bool:
        """Check if project can be edited by the given user."""
        # Global projects cannot be edited by regular users
        if self.is_global:
            return False
        # Users can only edit their own projects
        return self.user_id == user_id
    
    def can_be_deleted_by_user(self, user_id: str) -> bool:
        """Check if project can be deleted by the given user."""
        # Global projects cannot be deleted by regular users
        if self.is_global:
            return False
        # Users can only delete their own projects
        return self.user_id == user_id
    
    def can_be_copied_by_user(self, user_id: str) -> bool:
        """Check if project can be copied by the given user."""
        # Only global templates can be copied
        return self.is_template
    
    def create_copy_for_user(self, user_id: str, new_name: str, new_description: Optional[str] = None) -> 'ProjectDomain':
        """Create a copy of this template for a user."""
        if not self.can_be_copied_by_user(user_id):
            raise ValueError("Only global templates can be copied")
        
        if not new_name or not new_name.strip():
            raise ValueError("Copy name cannot be empty")
        
        import uuid
        return ProjectDomain(
            id=str(uuid.uuid4()),
            name=new_name.strip(),
            user_id=user_id,
            description=new_description or self.description,
            is_global=False,
            template_id=self.id,
            created_by_user_id=user_id,
            created_at=datetime.now(timezone.utc)
        )
    
    def mark_as_updated(self) -> None:
        """Mark project as updated."""
        self.updated_at = datetime.now(timezone.utc)


class ProjectCopyRequest(BaseModel):
    """Domain model for copying a project from a template."""
    
    template_id: str
    new_name: str = Field(..., min_length=1, max_length=255)
    new_description: Optional[str] = Field(None, max_length=1000)
    user_id: str


class ProjectFilter(BaseModel):
    """Domain model for filtering projects."""
    
    user_id: Optional[str] = None
    is_global: Optional[bool] = None
    template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None


# Backward compatibility alias
Project = ProjectDomain
