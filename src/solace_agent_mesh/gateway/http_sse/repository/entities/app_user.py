"""
App user access domain entity.
"""

from pydantic import BaseModel, Field


class AppUser(BaseModel):
    """
    App user access domain entity.

    Represents a user's access to an app with a specific role.
    """

    id: str
    app_id: str
    user_id: str
    role: str = Field(..., pattern="^(owner|editor|viewer)$")
    added_at: int
    added_by_user_id: str

    def can_edit_app(self) -> bool:
        """Check if this user can edit the app based on their role."""
        return self.role in ["owner", "editor"]

    def can_manage_users(self) -> bool:
        """Check if this user can manage other users' access to the app."""
        return self.role == "owner"

    def can_view_app(self) -> bool:
        """Check if this user can view the app."""
        return self.role in ["owner", "editor", "viewer"]

    def update_role(self, new_role: str) -> None:
        """Update the user's role with validation."""
        valid_roles = ["owner", "editor", "viewer"]
        if new_role not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        self.role = new_role

    class Config:
        """Pydantic configuration."""
        frozen = False
