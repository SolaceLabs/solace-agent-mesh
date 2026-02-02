from unittest.mock import Mock

from solace_agent_mesh.common.services.default_resource_sharing_service import (
    DefaultResourceSharingService,
)
from solace_agent_mesh.services.resource_sharing_service import ResourceType


class TestDefaultResourceSharingService:
    """Tests for the DefaultResourceSharingService stub implementation."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.service = DefaultResourceSharingService()
        self.mock_session = Mock()
        self.resource_id = "test-project-123"
        self.resource_type = ResourceType.PROJECT
        self.user_email = "test@example.com"

    def test_get_shared_resource_ids_returns_empty_list(self):
        """Test that get_shared_resource_ids returns an empty list.

        Community edition has no shared resources, so this method always
        returns an empty list regardless of the user or resource type.
        """
        result = self.service.get_shared_resource_ids(
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

    def test_get_shared_users_returns_empty_list(self):
        """Test that get_shared_users returns an empty list.

        Community edition has no sharing, so there are never any shared users.
        This method is called when deleting projects to clean up shared users'
        sessions. Returning an empty list means no additional session cleanup
        is needed beyond the owner's sessions.
        """
        result = self.service.get_shared_users(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
        )

        assert result == []
