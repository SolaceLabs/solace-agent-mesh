"""
Unit tests for gateway/base/auth_interface.py
Tests the abstract AuthHandler interface.
"""

import pytest
from abc import ABC
from unittest.mock import AsyncMock, MagicMock

from solace_agent_mesh.gateway.base.auth_interface import AuthHandler


class ConcreteAuthHandler(AuthHandler):
    """Concrete implementation for testing the abstract interface."""

    def __init__(self):
        self.is_auth = False
        self.auth_headers = {}
        self.authorize_called = False
        self.callback_called = False

    async def handle_authorize(self, request):
        self.authorize_called = True
        return {"redirect_url": "https://auth.example.com/authorize", "status_code": 302}

    async def handle_callback(self, request):
        self.callback_called = True
        self.is_auth = True
        return {"success": True, "message": "Authentication successful"}

    async def get_auth_headers(self):
        if self.is_auth:
            return self.auth_headers
        return {}

    async def is_authenticated(self):
        return self.is_auth


class TestAuthHandlerInterface:
    """Test the AuthHandler abstract interface."""

    def test_auth_handler_is_abstract(self):
        """Test that AuthHandler is an abstract base class."""
        assert issubclass(AuthHandler, ABC)

        # Attempting to instantiate should raise TypeError
        with pytest.raises(TypeError):
            AuthHandler()

    def test_auth_handler_has_required_methods(self):
        """Test that AuthHandler defines all required abstract methods."""
        required_methods = [
            'handle_authorize',
            'handle_callback',
            'get_auth_headers',
            'is_authenticated'
        ]

        for method_name in required_methods:
            assert hasattr(AuthHandler, method_name)

    @pytest.mark.asyncio
    async def test_concrete_implementation_handle_authorize(self):
        """Test concrete implementation of handle_authorize."""
        handler = ConcreteAuthHandler()

        result = await handler.handle_authorize(MagicMock())

        assert handler.authorize_called is True
        assert "redirect_url" in result
        assert result["redirect_url"] == "https://auth.example.com/authorize"
        assert result["status_code"] == 302

    @pytest.mark.asyncio
    async def test_concrete_implementation_handle_callback(self):
        """Test concrete implementation of handle_callback."""
        handler = ConcreteAuthHandler()

        result = await handler.handle_callback(MagicMock())

        assert handler.callback_called is True
        assert result["success"] is True
        assert "message" in result

    @pytest.mark.asyncio
    async def test_concrete_implementation_get_auth_headers_authenticated(self):
        """Test get_auth_headers when authenticated."""
        handler = ConcreteAuthHandler()
        handler.is_auth = True
        handler.auth_headers = {"Authorization": "Bearer test-token"}

        headers = await handler.get_auth_headers()

        assert headers == {"Authorization": "Bearer test-token"}

    @pytest.mark.asyncio
    async def test_concrete_implementation_get_auth_headers_not_authenticated(self):
        """Test get_auth_headers when not authenticated."""
        handler = ConcreteAuthHandler()
        handler.is_auth = False

        headers = await handler.get_auth_headers()

        assert headers == {}

    @pytest.mark.asyncio
    async def test_concrete_implementation_is_authenticated(self):
        """Test is_authenticated method."""
        handler = ConcreteAuthHandler()

        # Initially not authenticated
        assert await handler.is_authenticated() is False

        # After callback
        await handler.handle_callback(MagicMock())
        assert await handler.is_authenticated() is True


class TestAuthHandlerWorkflow:
    """Test typical authentication workflow."""

    @pytest.mark.asyncio
    async def test_oauth_workflow(self):
        """Test a typical OAuth2 workflow."""
        handler = ConcreteAuthHandler()

        # Step 1: User initiates authorization
        authorize_result = await handler.handle_authorize(MagicMock())
        assert authorize_result["redirect_url"] is not None

        # At this point, user is not authenticated yet
        assert await handler.is_authenticated() is False
        assert await handler.get_auth_headers() == {}

        # Step 2: OAuth callback with code
        callback_result = await handler.handle_callback(MagicMock())
        assert callback_result["success"] is True

        # Step 3: Now authenticated
        assert await handler.is_authenticated() is True

        # Step 4: Can get auth headers
        handler.auth_headers = {"Authorization": "Bearer token123"}
        headers = await handler.get_auth_headers()
        assert "Authorization" in headers


class TestAuthHandlerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_auth_headers_empty_when_not_authenticated(self):
        """Test that get_auth_headers returns empty dict when not authenticated."""
        handler = ConcreteAuthHandler()
        handler.is_auth = False
        handler.auth_headers = {"Authorization": "Bearer should-not-be-returned"}

        headers = await handler.get_auth_headers()

        # Should return empty, not the stored headers
        assert headers == {}

    @pytest.mark.asyncio
    async def test_multiple_authorize_calls(self):
        """Test that handle_authorize can be called multiple times."""
        handler = ConcreteAuthHandler()

        result1 = await handler.handle_authorize(MagicMock())
        result2 = await handler.handle_authorize(MagicMock())

        # Should work both times
        assert "redirect_url" in result1
        assert "redirect_url" in result2

    @pytest.mark.asyncio
    async def test_callback_before_authorize(self):
        """Test calling callback without authorize (e.g., replay attack)."""
        handler = ConcreteAuthHandler()

        # In this simple implementation, callback works independently
        # Real implementations might validate state/nonce
        result = await handler.handle_callback(MagicMock())

        assert result["success"] is True


class FailingAuthHandler(AuthHandler):
    """Auth handler that raises exceptions for testing error handling."""

    async def handle_authorize(self, request):
        raise ValueError("Authorization service unavailable")

    async def handle_callback(self, request):
        raise ValueError("Invalid authorization code")

    async def get_auth_headers(self):
        raise RuntimeError("Token expired")

    async def is_authenticated(self):
        raise ConnectionError("Cannot reach auth service")


class TestAuthHandlerErrorHandling:
    """Test error handling in auth handlers."""

    @pytest.mark.asyncio
    async def test_handle_authorize_exception(self):
        """Test that handle_authorize can raise exceptions."""
        handler = FailingAuthHandler()

        with pytest.raises(ValueError, match="Authorization service unavailable"):
            await handler.handle_authorize(MagicMock())

    @pytest.mark.asyncio
    async def test_handle_callback_exception(self):
        """Test that handle_callback can raise exceptions."""
        handler = FailingAuthHandler()

        with pytest.raises(ValueError, match="Invalid authorization code"):
            await handler.handle_callback(MagicMock())

    @pytest.mark.asyncio
    async def test_get_auth_headers_exception(self):
        """Test that get_auth_headers can raise exceptions."""
        handler = FailingAuthHandler()

        with pytest.raises(RuntimeError, match="Token expired"):
            await handler.get_auth_headers()

    @pytest.mark.asyncio
    async def test_is_authenticated_exception(self):
        """Test that is_authenticated can raise exceptions."""
        handler = FailingAuthHandler()

        with pytest.raises(ConnectionError, match="Cannot reach auth service"):
            await handler.is_authenticated()


class MockFrameworkRequest:
    """Mock request object representing different frameworks."""

    def __init__(self, params=None, headers=None):
        self.params = params or {}
        self.headers = headers or {}


class TestAuthHandlerFrameworkAgnostic:
    """Test that AuthHandler interface works with different request objects."""

    @pytest.mark.asyncio
    async def test_handle_authorize_with_custom_request(self):
        """Test handle_authorize with custom request object."""
        handler = ConcreteAuthHandler()
        request = MockFrameworkRequest(params={"client_id": "test123"})

        result = await handler.handle_authorize(request)

        assert result is not None
        assert "redirect_url" in result

    @pytest.mark.asyncio
    async def test_handle_callback_with_custom_request(self):
        """Test handle_callback with custom request object."""
        handler = ConcreteAuthHandler()
        request = MockFrameworkRequest(
            params={"code": "auth_code_123", "state": "random_state"}
        )

        result = await handler.handle_callback(request)

        assert result["success"] is True
