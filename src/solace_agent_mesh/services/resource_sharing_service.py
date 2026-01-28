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
    def get_shared_resource_ids(
        self,
        session,
        user_email: str,
        resource_type: ResourceType
    ) -> List[str]:
        """
        Get resource IDs that user has shared access to (any access level).

        Returns:
            List of resource IDs. Empty list for community, actual IDs for enterprise.
        """
        pass

    @abstractmethod
    def check_user_access(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        user_email: str
    ) -> Optional[SharingRole]:
        """
        Check if user has access to a specific resource.

        Returns:
            SharingRole if user has access, None otherwise.
        """
        pass

    @abstractmethod
    def delete_resource_shares(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType
    ) -> bool:
        """
        Delete all sharing records for a resource (e.g., when resource is deleted).

        Returns:
            True if successful, False otherwise.
        """
        pass