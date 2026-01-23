"""
Share link domain entity.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


class ShareLink(BaseModel):
    """Share link domain entity with business logic."""

    model_config = ConfigDict(from_attributes=True)

    share_id: str
    session_id: str
    user_id: str
    title: Optional[str] = None
    is_public: bool = True
    require_authentication: bool = False
    allowed_domains: Optional[str] = None  # Comma-separated in DB
    created_time: int
    updated_time: int
    deleted_at: Optional[int] = None

    def is_deleted(self) -> bool:
        """Check if share link is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete the share link."""
        self.deleted_at = now_epoch_ms()
        self.updated_time = now_epoch_ms()

    def get_access_type(self) -> str:
        """
        Determine the access type for this share link.
        
        Returns:
            "public", "authenticated", or "domain-restricted"
        """
        if not self.require_authentication:
            return "public"
        if not self.allowed_domains:
            return "authenticated"
        return "domain-restricted"

    def get_allowed_domains_list(self) -> List[str]:
        """
        Parse allowed_domains string into a list.
        
        Returns:
            List of domain strings, or empty list if none
        """
        if not self.allowed_domains:
            return []
        return [d.strip() for d in self.allowed_domains.split(',') if d.strip()]

    def set_allowed_domains_list(self, domains: List[str]) -> None:
        """
        Set allowed domains from a list.
        
        Args:
            domains: List of domain strings
        """
        if domains:
            self.allowed_domains = ','.join(domains)
        else:
            self.allowed_domains = None
        self.updated_time = now_epoch_ms()

    def update_authentication_settings(
        self, 
        require_authentication: Optional[bool] = None,
        allowed_domains: Optional[List[str]] = None
    ) -> None:
        """
        Update authentication settings.
        
        Args:
            require_authentication: Whether to require authentication
            allowed_domains: List of allowed email domains
        """
        if require_authentication is not None:
            self.require_authentication = require_authentication
        
        if allowed_domains is not None:
            self.set_allowed_domains_list(allowed_domains)
        
        self.updated_time = now_epoch_ms()

    def can_be_accessed_by_user(self, user_id: Optional[str], user_email: Optional[str]) -> tuple[bool, str]:
        """
        Check if a user can access this share link.
        
        Args:
            user_id: User ID (None if not authenticated)
            user_email: User email (None if not authenticated)
        
        Returns:
            Tuple of (can_access: bool, reason: str)
        """
        # Public access - anyone can view
        if not self.require_authentication:
            return (True, "public")
        
        # Authentication required but user not logged in
        if user_id is None:
            return (False, "authentication_required")
        
        # No domain restriction - any authenticated user
        if not self.allowed_domains:
            return (True, "authenticated")
        
        # Domain restriction - check user's email domain
        if not user_email or '@' not in user_email:
            return (False, "invalid_email")
        
        user_domain = user_email.split('@')[1].lower().strip()
        allowed_domains = [d.lower() for d in self.get_allowed_domains_list()]
        
        if user_domain in allowed_domains:
            return (True, "domain_match")
        else:
            return (False, "domain_mismatch")

    def can_be_modified_by_user(self, user_id: str) -> bool:
        """Check if user can modify this share link."""
        return self.user_id == user_id and not self.is_deleted()


class SharedArtifact(BaseModel):
    """Shared artifact domain entity."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    share_id: str
    artifact_uri: str
    artifact_version: Optional[int] = None
    is_public: bool = True
    created_time: int
