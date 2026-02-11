"""Tests for ResourceSharingService abstract base class."""

from solace_agent_mesh.services.resource_sharing_service import (
    ResourceSharingService,
    ResourceType,
)


class ConcreteResourceSharingService(ResourceSharingService):
    """Concrete implementation for testing the ABC."""

    def get_shared_resource_ids(self, session, user_email: str, resource_type: ResourceType):
        return []

    def check_user_access(self, session, resource_id: str, resource_type: ResourceType, user_email: str):
        return None

    def delete_resource_shares(self, session, resource_id: str, resource_type: ResourceType):
        return True

    def unshare_users_from_resource(self, session, resource_id: str, resource_type: ResourceType, user_emails):
        return True

    def get_shared_users(self, session, resource_id: str, resource_type: ResourceType):
        return []


class TestResourceSharingServiceABC:
    """Test the abstract base class contract."""

    def test_resource_type_enum_has_project(self):
        """Test that ResourceType enum includes PROJECT."""
        assert ResourceType.PROJECT.value == "project"

    def test_is_resource_sharing_available_default_false(self):
        """Test that default is_resource_sharing_available returns False."""
        service = ConcreteResourceSharingService()
        assert service.is_resource_sharing_available is False

    def test_abstract_methods_can_be_implemented(self):
        """Test that all abstract methods can be implemented."""
        service = ConcreteResourceSharingService()

        # Test all abstract methods can be called
        assert service.get_shared_resource_ids(None, "test@example.com", ResourceType.PROJECT) == []
        assert service.check_user_access(None, "id", ResourceType.PROJECT, "test@example.com") is None
        assert service.delete_resource_shares(None, "id", ResourceType.PROJECT) is True
        assert service.unshare_users_from_resource(None, "id", ResourceType.PROJECT, []) is True
        assert service.get_shared_users(None, "id", ResourceType.PROJECT) == []
