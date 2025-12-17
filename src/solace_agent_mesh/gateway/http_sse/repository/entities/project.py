"""
Project domain entity.
"""

from typing import Optional
from pydantic import BaseModel, Field

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


class Project(BaseModel):
    """Project domain entity with business logic."""
    
    id: str
    name: str = Field(..., min_length=1, max_length=255)
    user_id: str
    description: Optional[str] = Field(None, max_length=1000)
    system_prompt: Optional[str] = Field(None, max_length=4000)
    default_agent_id: Optional[str] = None
    created_at: int
    updated_at: Optional[int] = None
    deleted_at: Optional[int] = None
    deleted_by: Optional[str] = None
    
    def update_name(self, new_name: str) -> None:
        """Update project name with validation."""
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("Project name cannot be empty")
        if len(new_name) > 255:
            raise ValueError("Project name cannot exceed 255 characters")
        
        self.name = new_name.strip()
        self.updated_at = now_epoch_ms()
    
    def update_description(self, new_description: Optional[str]) -> None:
        """Update project description with validation."""
        if new_description is not None:
            if len(new_description) > 1000:
                raise ValueError("Project description cannot exceed 1000 characters")
            self.description = new_description.strip() if new_description else None
        else:
            self.description = None
        
        self.updated_at = now_epoch_ms()
    
    def update_default_agent(self, agent_id: Optional[str]) -> None:
        """Update project default agent."""
        self.default_agent_id = agent_id
        self.updated_at = now_epoch_ms()
    
    def soft_delete(self, user_id: str) -> None:
        """Soft delete the project."""
        if not self.can_be_deleted_by_user(user_id):
            raise ValueError("User does not have permission to delete this project")
        
        self.deleted_at = now_epoch_ms()
        self.deleted_by = user_id
        self.updated_at = now_epoch_ms()
    
    def is_deleted(self) -> bool:
        """Check if project is soft deleted."""
        return self.deleted_at is not None
    
    def can_be_accessed_by_user(self, user_id: str) -> bool:
        """Check if project can be accessed by the given user."""
        # User projects are only accessible by their owner and not deleted
        return self.user_id == user_id and not self.is_deleted()
    
    def can_be_edited_by_user(self, user_id: str) -> bool:
        """Check if project can be edited by the given user."""
        # Users can only edit their own projects that are not deleted
        return self.user_id == user_id and not self.is_deleted()
    
    def can_be_deleted_by_user(self, user_id: str) -> bool:
        """Check if project can be deleted by the given user."""
        # Users can only delete their own projects that are not already deleted
        return self.user_id == user_id and not self.is_deleted()
    
    def mark_as_updated(self) -> None:
        """Mark project as updated."""
        self.updated_at = now_epoch_ms()