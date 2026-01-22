from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from enum import Enum


class ResourceType(Enum):
    PROJECT = "project"


class SharingRole(Enum):
    RESOURCE_VIEWER = "resource_viewer"
    RESOURCE_EDITOR = "resource_editor"
    RESOURCE_ADMINISTRATOR = "resource_administrator"


class ResourceSharingService(ABC):
    """Abstract base class for resource sharing functionality."""

    @abstractmethod
    def share_resource(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        shared_with_user_email: str,
        access_level: SharingRole,
        shared_by_user_email: str
    ) -> bool:
        """Share a resource with another user."""
        pass

    @abstractmethod
    def get_shared_resources(
        self,
        session,
        user_email: str,
        resource_type: Optional[ResourceType] = None
    ) -> List[Dict]:
        """Get resources shared with a user."""
        pass

    @abstractmethod
    def can_access_resource(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        user_email: str
    ) -> bool:
        """Check if user can access a resource."""
        pass

    @abstractmethod
    def unshare_resource(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        shared_with_user_email: str
    ) -> bool:
        """Remove sharing access for a user."""
        pass

    @abstractmethod
    def check_user_access(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        user_email: str
    ) -> Optional[SharingRole]:
        """Check user access and return their access level if they have access."""
        pass

    @abstractmethod
    def get_resource_collaborators(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType
    ) -> List[Dict]:
        """Get all users who have access to a resource."""
        pass

    @abstractmethod
    def delete_resource_shares(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType
    ) -> bool:
        """Delete all sharing records for a resource (e.g., when resource is deleted)."""
        pass