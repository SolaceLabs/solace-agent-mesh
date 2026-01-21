"""
Unit tests for authentication features in BaseGatewayComponent.
Tests _setup_auth, _inject_auth_headers, and auth_handler functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.gateway.base.auth_interface import AuthHandler


class MockAuthHandler(AuthHandler):
    """Mock auth handler for testing."""

    def __init__(self, authenticated=True, headers=None):
        self._authenticated = authenticated
        self._headers = headers or {"Authorization": "Bearer test-token"}

    async def handle_authorize(self, request):
        return {"redirect_url": "https://auth.example.com/authorize"}

    async def handle_callback(self, request):
        return {"success": True, "message": "Auth successful"}

    async def get_auth_headers(self):
        if self._authenticated:
            return self._headers
        return {}

    async def is_authenticated(self):
        return self._authenticated


@pytest.fixture
def mock_config():
    """Mock configuration for BaseGatewayComponent."""
    return {
        "namespace": "test/namespace",
        "gateway_id": "test-gateway",
        "broker": {
            "url": "tcp://localhost:55555",
            "vpn": "default",
            "username": "test",
            "password": "test"
        }
    }

class TestInjectAuthHeaders:
    """Test _inject_auth_headers method."""

    @pytest.mark.asyncio
    async def test_inject_auth_headers_with_authenticated_handler(self):
        """Test injecting auth headers when authenticated."""
        # Create a mock component with auth handler
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(authenticated=True)
        mock_component.log_identifier = "[TestGateway]"

        # Call the actual method
        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should include auth headers
        assert "Authorization" in result
        assert result["Authorization"] == "Bearer test-token"
        assert result["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_inject_auth_headers_without_auth_handler(self):
        """Test injecting auth headers when no auth handler is set."""
        mock_component = MagicMock()
        mock_component.auth_handler = None

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should return headers unchanged
        assert result == {"Content-Type": "application/json"}
        assert "Authorization" not in result

    @pytest.mark.asyncio
    async def test_inject_auth_headers_not_authenticated(self):
        """Test injecting auth headers when handler is not authenticated."""
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(authenticated=False)
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should return headers without auth
        assert result == {"Content-Type": "application/json"}
        assert "Authorization" not in result

    @pytest.mark.asyncio
    async def test_inject_auth_headers_preserves_existing_headers(self):
        """Test that existing headers are preserved when injecting auth."""
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(
            authenticated=True,
            headers={"Authorization": "Bearer new-token"}
        )
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {
            "Content-Type": "application/json",
            "X-Custom-Header": "custom-value"
        }
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should include all headers
        assert result["Authorization"] == "Bearer new-token"
        assert result["Content-Type"] == "application/json"
        assert result["X-Custom-Header"] == "custom-value"

    @pytest.mark.asyncio
    async def test_inject_auth_headers_overwrites_existing_auth(self):
        """Test that auth headers overwrite existing Authorization header."""
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(
            authenticated=True,
            headers={"Authorization": "Bearer new-token"}
        )
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {
            "Authorization": "Bearer old-token",
            "Content-Type": "application/json"
        }
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Auth header should be overwritten
        assert result["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_inject_auth_headers_with_empty_headers(self):
        """Test injecting auth headers into empty dict."""
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(
            authenticated=True,
            headers={"Authorization": "Bearer token123"}
        )
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should add auth headers to empty dict
        assert result == {"Authorization": "Bearer token123"}

    @pytest.mark.asyncio
    async def test_inject_auth_headers_exception_handling(self):
        """Test that exceptions in get_auth_headers are handled gracefully."""

        class FailingAuthHandler(AuthHandler):
            async def handle_authorize(self, request):
                pass

            async def handle_callback(self, request):
                pass

            async def get_auth_headers(self):
                raise RuntimeError("Auth service unavailable")

            async def is_authenticated(self):
                return True

        mock_component = MagicMock()
        mock_component.auth_handler = FailingAuthHandler()
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}

        # Should not raise exception, just log warning
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should return original headers unchanged
        assert result == {"Content-Type": "application/json"}

    @pytest.mark.asyncio
    async def test_inject_auth_headers_multiple_auth_headers(self):
        """Test injecting multiple auth-related headers."""
        mock_component = MagicMock()
        mock_component.auth_handler = MockAuthHandler(
            authenticated=True,
            headers={
                "Authorization": "Bearer token123",
                "X-API-Key": "api-key-456",
                "X-Client-ID": "client-789"
            }
        )
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should include all auth headers
        assert result["Authorization"] == "Bearer token123"
        assert result["X-API-Key"] == "api-key-456"
        assert result["X-Client-ID"] == "client-789"
        assert result["Content-Type"] == "application/json"


class TestAuthHandlerIntegration:
    """Test integration between component and auth handler."""

    @pytest.mark.asyncio
    async def test_auth_workflow_integration(self):
        """Test complete auth workflow with component."""
        mock_component = MagicMock()
        auth_handler = MockAuthHandler(authenticated=False)
        mock_component.auth_handler = auth_handler
        mock_component.log_identifier = "[TestGateway]"

        # Initially not authenticated
        headers = {"Content-Type": "application/json"}
        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)
        assert "Authorization" not in result

        # Authenticate
        auth_handler._authenticated = True

        # Now should get auth headers
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)
        assert "Authorization" in result

    @pytest.mark.asyncio
    async def test_auth_handler_token_refresh(self):
        """Test that updated tokens are reflected in headers."""
        mock_component = MagicMock()
        auth_handler = MockAuthHandler(
            authenticated=True,
            headers={"Authorization": "Bearer old-token"}
        )
        mock_component.auth_handler = auth_handler
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {}

        # Get initial headers
        result1 = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)
        assert result1["Authorization"] == "Bearer old-token"

        # Update token
        auth_handler._headers = {"Authorization": "Bearer new-token"}

        # Get updated headers
        result2 = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)
        assert result2["Authorization"] == "Bearer new-token"


class TestAuthHandlerNone:
    """Test behavior when auth_handler is explicitly None."""

    @pytest.mark.asyncio
    async def test_inject_auth_headers_with_none_handler(self):
        """Test that None auth_handler is handled correctly."""
        mock_component = MagicMock()
        mock_component.auth_handler = None

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}
        result = await BaseGatewayComponent._inject_auth_headers(mock_component, headers)

        # Should return unchanged
        assert result == {"Content-Type": "application/json"}

    @pytest.mark.asyncio
    async def test_inject_auth_headers_attribute_missing(self):
        """Test behavior when auth_handler attribute doesn't exist."""
        # Create a mock component without auth_handler attribute
        mock_component = MagicMock(spec=[])  # Empty spec - no attributes
        mock_component.log_identifier = "[TestGateway]"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
        headers = {"Content-Type": "application/json"}

        # The implementation checks 'if self.auth_handler', which will raise AttributeError
        # if the attribute doesn't exist. This is an edge case that shouldn't happen in practice
        # since BaseGatewayComponent.__init__ always sets auth_handler
        # We expect this to raise AttributeError
        with pytest.raises(AttributeError):
            await BaseGatewayComponent._inject_auth_headers(mock_component, headers)
