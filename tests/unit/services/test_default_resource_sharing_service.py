from unittest.mock import Mock

from solace_agent_mesh.common.services.default_resource_sharing_service import (
    DefaultResourceSharingService,
)
from solace_agent_mesh.services.resource_sharing_service import (
    ResourceType,
    SharingRole,
)


class TestDefaultResourceSharingService:
    """Tests for the DefaultResourceSharingService stub implementation."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.service = DefaultResourceSharingService()
        self.mock_session = Mock()
        self.resource_id = "test-project-123"
        self.resource_type = ResourceType.PROJECT
        self.user_email = "test@example.com"
        self.shared_by_email = "owner@example.com"
        self.access_level = SharingRole.RESOURCE_VIEWER

    def test_share_resource_returns_false(self):
        """Test that share_resource returns False since community edition does not support sharing.

        Community edition cannot create shares, so this method always returns False
        to indicate the share operation was not performed.
        """
        result = self.service.share_resource(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            shared_with_user_email=self.user_email,
            access_level=self.access_level,
            shared_by_user_email=self.shared_by_email,
        )

        assert result is False

    def test_unshare_resource_returns_false(self):
        """Test that unshare_resource returns False since there are no shares to remove.

        Since community edition has no sharing capability, there are no shares
        to remove. The method returns False indicating no share was found/removed.
        """
        result = self.service.unshare_resource(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            shared_with_user_email=self.user_email,
        )

        assert result is False

    def test_can_access_resource_returns_false(self):
        """Test that can_access_resource returns False since no shared access exists.

        This is critical for authorization: community edition users cannot access
        resources via sharing. Access is determined solely by ownership. Returning
        False ensures authorization checks fall back to owner-only access.
        """
        result = self.service.can_access_resource(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            user_email=self.user_email,
        )

        assert result is False

    def test_get_shared_resources_returns_empty_list(self):
        """Test that get_shared_resources returns an empty list.

        Community edition has no shared resources, so this method always
        returns an empty list regardless of the user or resource type filter.
        """
        result = self.service.get_shared_resources(
            session=self.mock_session,
            user_email=self.user_email,
            resource_type=self.resource_type,
        )

        assert result == []

    def test_check_user_access_returns_none(self):
        """Test that check_user_access returns None indicating no access level.

        This is the primary method used by authorization helpers. Returning None
        means the user has no shared access, so they can only access resources
        they own in community edition.
        """
        result = self.service.check_user_access(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            user_email=self.user_email,
        )

        assert result is None

    def test_get_resource_collaborators_returns_empty_list(self):
        """Test that get_resource_collaborators returns an empty list.

        Community edition has no collaborators on any resource since sharing
        is disabled. This ensures UI/API correctly shows no collaborators.
        """
        result = self.service.get_resource_collaborators(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
        )

        assert result == []

    def test_delete_resource_shares_returns_true(self):
        """Test that delete_resource_shares returns True indicating successful cleanup.

        When a resource is deleted, this method is called to clean up any shares.
        In community edition, there are no shares to delete, but the cleanup
        operation succeeds (nothing to clean up = success). Returning True
        allows resource deletion to proceed without errors.
        """
        result = self.service.delete_resource_shares(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
        )

        assert result is True
