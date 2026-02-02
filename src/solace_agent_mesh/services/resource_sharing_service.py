from abc import ABC, abstractmethod
from typing import List, Optional
from enum import Enum


class ResourceType(Enum):
    PROJECT = "project"


class ResourceSharingService(ABC):
    """Abstract base class for resource sharing functionality."""

    @property
    def is_resource_sharing_available(self) -> bool:
        """Returns True if resource sharing functionality is available."""
        return False

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
    ) -> Optional[str]:
        """
        Check if user has access to a specific resource.

        Returns:
            Access level string (e.g., "RESOURCE_VIEWER") if user has access, None otherwise.
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

    @abstractmethod
    def get_shared_users(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType
    ) -> List[str]:
        """
        Get list of user emails with shared access to a resource.

        This is used when deleting resources to ensure sessions created by
        shared users are also cleaned up.

        Returns:
            List of user emails. Empty list for community, actual emails for enterprise.
        """
        pass