"""
Tests for Platform Service health endpoint.

Verifies that the Platform Service health check endpoint works correctly.
"""


class TestPlatformHealthEndpoint:
    """Tests for the /api/v1/platform/health endpoint."""

    def test_health_endpoint_returns_healthy(self, platform_api_client):
        """Test that health endpoint returns healthy status."""
        response = platform_api_client.get("/api/v1/platform/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "Platform" in data["service"]

    def test_health_endpoint_no_auth_required(self, platform_api_client):
        """Test that health endpoint doesn't require authentication."""
        response = platform_api_client.get("/api/v1/platform/health")
        assert response.status_code == 200

    def test_factory_initialization(self, platform_api_client_factory):
        """Test that PlatformServiceFactory initializes correctly."""
        assert platform_api_client_factory is not None
        assert platform_api_client_factory.app is not None
        assert platform_api_client_factory.engine is not None
        assert platform_api_client_factory.Session is not None
        assert platform_api_client_factory.mock_component is not None

    def test_factory_mock_component_configuration(self, platform_api_client_factory):
        """Test that mock component is configured correctly."""
        mock_component = platform_api_client_factory.mock_component
        assert mock_component.namespace == "test_namespace"
        assert mock_component.get_config("frontend_use_authorization", False) is False
        assert mock_component.get_cors_origins() == ["*"]

    def test_factory_heartbeat_tracker_available(self, platform_api_client_factory):
        """Test that heartbeat tracker is available in mock component."""
        heartbeat_tracker = platform_api_client_factory.mock_component.get_heartbeat_tracker()
        assert heartbeat_tracker is not None

    def test_factory_agent_registry_available(self, platform_api_client_factory):
        """Test that agent registry is available in mock component."""
        agent_registry = platform_api_client_factory.mock_component.get_agent_registry()
        assert agent_registry is not None
