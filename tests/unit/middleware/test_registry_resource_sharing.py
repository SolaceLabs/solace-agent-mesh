"""Tests for MiddlewareRegistry resource sharing service binding."""
import pytest
from solace_agent_mesh.common.middleware.registry import MiddlewareRegistry
from solace_agent_mesh.common.services.default_resource_sharing_service import (
    DefaultResourceSharingService,
)
from solace_agent_mesh.services.resource_sharing_service import (
    ResourceSharingService,
    ResourceType,
)


class TestResourceSharingServiceBinding:
    """Test resource sharing service binding in MiddlewareRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        MiddlewareRegistry.reset_bindings()

    def teardown_method(self):
        """Reset registry after each test."""
        MiddlewareRegistry.reset_bindings()

    def test_get_resource_sharing_service_returns_default_when_none_bound(self):
        """Test that get_resource_sharing_service returns default when none bound."""
        service_class = MiddlewareRegistry.get_resource_sharing_service()
        assert service_class == DefaultResourceSharingService

    def test_bind_resource_sharing_service_stores_custom_service(self):
        """Test that bind_resource_sharing_service stores custom service."""

        class CustomResourceSharingService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return ["custom-id"]

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return "CUSTOM_ACCESS"

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        MiddlewareRegistry.bind_resource_sharing_service(CustomResourceSharingService)
        service_class = MiddlewareRegistry.get_resource_sharing_service()
        assert service_class == CustomResourceSharingService

    def test_bind_resource_sharing_service_replaces_existing_binding(self):
        """Test that binding a new service replaces the existing one."""

        class FirstService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return []

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return None

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        class SecondService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return []

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return None

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        MiddlewareRegistry.bind_resource_sharing_service(FirstService)
        MiddlewareRegistry.bind_resource_sharing_service(SecondService)
        service_class = MiddlewareRegistry.get_resource_sharing_service()
        assert service_class == SecondService

    def test_reset_bindings_clears_resource_sharing_service(self):
        """Test that reset_bindings clears resource sharing service binding."""

        class CustomService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return []

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return None

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        MiddlewareRegistry.bind_resource_sharing_service(CustomService)
        assert MiddlewareRegistry.get_resource_sharing_service() == CustomService

        MiddlewareRegistry.reset_bindings()
        service_class = MiddlewareRegistry.get_resource_sharing_service()
        assert service_class == DefaultResourceSharingService

    def test_get_registry_status_includes_resource_sharing_service(self):
        """Test that get_registry_status includes resource sharing service info."""
        status = MiddlewareRegistry.get_registry_status()
        assert "resource_sharing_service" in status
        assert status["resource_sharing_service"] == "default"

    def test_get_registry_status_shows_custom_resource_sharing_service(self):
        """Test that get_registry_status shows custom service name."""

        class CustomService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return []

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return None

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        MiddlewareRegistry.bind_resource_sharing_service(CustomService)
        status = MiddlewareRegistry.get_registry_status()
        assert status["resource_sharing_service"] == "CustomService"

    def test_get_registry_status_has_custom_bindings_with_resource_sharing(self):
        """Test that has_custom_bindings is True when resource sharing service is bound."""

        class CustomService(ResourceSharingService):
            def get_shared_resource_ids(self, session, user_email, resource_type):
                return []

            def check_user_access(
                self, session, resource_id, resource_type, user_email
            ):
                return None

            def delete_resource_shares(self, session, resource_id, resource_type):
                return True

        MiddlewareRegistry.bind_resource_sharing_service(CustomService)
        status = MiddlewareRegistry.get_registry_status()
        assert status["has_custom_bindings"] is True
