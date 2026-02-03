from typing import List, Dict, Optional
from ...services.resource_sharing_service import ResourceSharingService, ResourceType, SharingRole


class DefaultResourceSharingService(ResourceSharingService):
    """Default implementation with no sharing features (Community edition)."""

    def get_shared_resource_ids(
        self,
        session,
        user_email: str,
        resource_type: ResourceType
    ) -> List[str]:
        """Community has no sharing - return empty list."""
        return []

    def check_user_access(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType,
        user_email: str
    ) -> Optional[SharingRole]:
        """Community has no sharing - return None (no access via sharing)."""
        return None

    def delete_resource_shares(
        self,
        session,
        resource_id: str,
        resource_type: ResourceType
    ) -> bool:
        """Community has no shares to delete - return True (no-op success)."""
        return True