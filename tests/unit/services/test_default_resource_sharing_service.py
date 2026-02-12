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

    def test_unshare_users_from_resource_returns_true(self):
        """Test that unshare_users_from_resource returns True indicating successful operation.

        When users are unshared from a resource, this method is called to remove
        their access. In community edition, there are no shares to remove, but
        the operation succeeds (no-op). Returning True indicates the operation
        completed successfully without errors.
        """
        user_emails = ["user1@example.com", "user2@example.com"]

        result = self.service.unshare_users_from_resource(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            user_emails=user_emails,
        )

        assert result is True

    def test_unshare_users_from_resource_handles_empty_list(self):
        """Test that unshare_users_from_resource handles empty email list correctly.

        Edge case: when called with an empty list of user emails, the method
        should still succeed (no-op on empty input).
        """
        result = self.service.unshare_users_from_resource(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            user_emails=[],
        )

        assert result is True

    def test_get_shared_users_returns_empty_list(self):
        """Test that get_shared_users returns an empty list.

        This method is used to retrieve users who have shared access to a resource.
        In community edition, no users have shared access (only ownership exists),
        so this method always returns an empty list.
        """
        result = self.service.get_shared_users(
            session=self.mock_session,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
        )

        assert result == []
