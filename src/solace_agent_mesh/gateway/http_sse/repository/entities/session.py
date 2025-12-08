"""
Session domain entity.
"""

from pydantic import BaseModel, ConfigDict

from ...shared import now_epoch_ms
from ...shared.types import AgentId, SessionId, UserId


class Session(BaseModel):
    """Session domain entity with business logic."""

    model_config = ConfigDict(from_attributes=True)

    id: SessionId
    user_id: UserId
    name: str | None = None
    agent_id: AgentId | None = None
    project_id: str | None = None
    project_name: str | None = None
    has_running_background_task: bool = False  # Enriched field, not stored in DB
    created_time: int
    updated_time: int | None = None
    deleted_at: int | None = None
    deleted_by: str | None = None

    def update_name(self, new_name: str) -> None:
        """Update session name with validation."""
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("Session name cannot be empty")
        if len(new_name) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        self.name = new_name.strip()
        self.updated_time = now_epoch_ms()

    def mark_activity(self) -> None:
        """Mark session as having recent activity."""
        self.updated_time = now_epoch_ms()

    def soft_delete(self, user_id: UserId) -> None:
        """Soft delete the session."""
        if not self.can_be_deleted_by_user(user_id):
            raise ValueError("User does not have permission to delete this session")
        
        self.deleted_at = now_epoch_ms()
        self.deleted_by = user_id
        self.updated_time = now_epoch_ms()

    def is_deleted(self) -> bool:
        """Check if session is soft deleted."""
        return self.deleted_at is not None

    def move_to_project(self, new_project_id: str | None) -> None:
        """Move session to a different project."""
        self.project_id = new_project_id
        self.updated_time = now_epoch_ms()

    def can_be_deleted_by_user(self, user_id: UserId) -> bool:
        """Check if user can delete this session."""
        return self.user_id == user_id

    def can_be_accessed_by_user(self, user_id: UserId) -> bool:
        """Check if user can access this session."""
        return self.user_id == user_id and not self.is_deleted()
