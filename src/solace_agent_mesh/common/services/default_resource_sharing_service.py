from typing import List, Dict, Optional
from ...services.resource_sharing_service import ResourceSharingService, ResourceType, SharingRole


class DefaultResourceSharingService(ResourceSharingService):
    """Default implementation with no sharing features."""
    
    def share_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        shared_with_user_id: str, 
        role: SharingRole, 
        shared_by_user_id: str
    ) -> bool:
        return False
        
    def get_shared_resources(
        self, 
        session, 
        user_id: str, 
        resource_type: Optional[ResourceType] = None
    ) -> List[Dict]:
        return []
        
    def can_access_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        user_id: str
    ) -> bool:
        return True
        
    def unshare_resource(
        self, 
        session, 
        resource_id: str, 
        resource_type: ResourceType, 
        shared_with_user_id: str
    ) -> bool:
        return False