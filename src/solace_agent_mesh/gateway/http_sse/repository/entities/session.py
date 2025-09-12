"""
Session domain entity.
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from ...shared.types import AgentId, SessionId, UserId


class Session(BaseModel):
    """Session domain entity with business logic."""
    
    id: SessionId
    user_id: UserId
    name: str | None = None
    agent_id: AgentId | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_activity: datetime | None = None

    def update_name(self, new_name: str) -> None:
        """Update session name with validation."""
        if not new_name or len(new_name.strip()) == 0:
            raise ValueError("Session name cannot be empty")
        if len(new_name) > 255:
            raise ValueError("Session name cannot exceed 255 characters")

        self.name = new_name.strip()
        self.updated_at = datetime.now(timezone.utc)

    def mark_activity(self) -> None:
        """Mark session as having recent activity."""
        self.last_activity = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


    def can_be_deleted_by_user(self, user_id: UserId) -> bool:
        """Check if user can delete this session."""
        return self.user_id == user_id

    def can_be_accessed_by_user(self, user_id: UserId) -> bool:
        """Check if user can access this session."""
        return self.user_id == user_id