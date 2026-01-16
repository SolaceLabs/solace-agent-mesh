from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from enum import Enum


class ResourceType(Enum):
    PROJECT = "project"


class SharingRole(Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMINISTRATOR = "administrator"


class ResourceSharingService(ABC):
    """Abstract base class for resource sharing functionality."""

    @abstractmethod
    def share_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        shared_with_user_id: str, 
        role: SharingRole, 
        shared_by_user_id: str
    ) -> bool:
        """
        Share a resource with another user.
        
        Args:
            session: Database session
            resource_id: ID of the resource to share
            resource_type: Type of resource being shared
            shared_with_user_id: ID of user receiving access
            role: Access level being granted
            shared_by_user_id: ID of user granting access
            
        Returns:
            True if sharing was successful, False otherwise
        """
        pass

    @abstractmethod
    def get_shared_resources(
        self, 
        session, 
        user_id: str, 
        resource_type: Optional[ResourceType] = None
    ) -> List[Dict]:
        """
        Get resources shared with a user.
        
        Args:
            session: Database session
            user_id: ID of user to get shared resources for
            resource_type: Optional filter by resource type
            
        Returns:
            List of shared resource dictionaries
        """
        pass

    @abstractmethod
    def can_access_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        user_id: str
    ) -> bool:
        """
        Check if user can access a resource.
        
        Args:
            session: Database session
            resource_id: ID of resource to check
            resource_type: Type of resource
            user_id: ID of user to check access for
            
        Returns:
            True if user has access, False otherwise
        """
        pass

    @abstractmethod
    def unshare_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        shared_with_user_id: str
    ) -> bool:
        """
        Remove sharing access for a user.
        
        Args:
            session: Database session
            resource_id: ID of resource to unshare
            resource_type: Type of resource
            shared_with_user_id: ID of user to remove access from
            
        Returns:
            True if unsharing was successful, False otherwise
        """
        pass