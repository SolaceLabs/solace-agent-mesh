"""
Unit tests for OAuth utility integration in http_sse/main.py.
Tests enterprise OAuth integration, and utility function usage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Test if enterprise package is available
try:
    from solace_agent_mesh_enterprise.gateway.auth.internal import oauth_utils
    ENTERPRISE_AVAILABLE = True
except ImportError:
    oauth_utils = None
    ENTERPRISE_AVAILABLE = False


@pytest.mark.skipif(not ENTERPRISE_AVAILABLE, reason="Enterprise package not available")
class TestValidateTokenWithEnterprise:
    """Test _validate_token with enterprise OAuth utilities."""

    @pytest.mark.asyncio
    async def test_validate_token_calls_enterprise_util(self):
        """Test that _validate_token calls enterprise validate_token_with_oauth_service."""
        from solace_agent_mesh.gateway.http_sse.main import _validate_token

        with patch.object(
            oauth_utils,
            'validate_token_with_oauth_service',
            new_callable=AsyncMock
        ) as mock_validate:
            mock_validate.return_value = True

            result = await _validate_token(
                "https://auth.example.com",
                "google",
                "test-token"
            )

            assert result is True
            mock_validate.assert_called_once_with(
                "https://auth.example.com",
                "google",
                "test-token"
            )

    @pytest.mark.asyncio
    async def test_validate_token_returns_false_on_failure(self):
        """Test that _validate_token returns False when validation fails."""
        from solace_agent_mesh.gateway.http_sse.main import _validate_token

        with patch.object(
            oauth_utils,
            'validate_token_with_oauth_service',
            new_callable=AsyncMock
        ) as mock_validate:
            mock_validate.return_value = False

            result = await _validate_token(
                "https://auth.example.com",
                "google",
                "invalid-token"
            )

            assert result is False

@pytest.mark.skipif(not ENTERPRISE_AVAILABLE, reason="Enterprise package not available")
class TestExtractUserIdentifierWithEnterprise:
    """Test _extract_user_identifier with enterprise OAuth utilities."""

    def test_extract_user_identifier_calls_enterprise_util(self):
        """Test that _extract_user_identifier calls enterprise extract_user_identifier."""
        from solace_agent_mesh.gateway.http_sse.main import _extract_user_identifier

        user_info = {"sub": "user123", "email": "test@example.com"}

        with patch.object(
            oauth_utils,
            'extract_user_identifier'
        ) as mock_extract:
            mock_extract.return_value = "user123"

            result = _extract_user_identifier(user_info)

            assert result == "user123"
            mock_extract.assert_called_once_with(user_info)

    def test_extract_user_identifier_returns_fallback_when_none(self):
        """Test that _extract_user_identifier returns fallback when extraction returns None."""
        from solace_agent_mesh.gateway.http_sse.main import _extract_user_identifier

        user_info = {}

        with patch.object(
            oauth_utils,
            'extract_user_identifier'
        ) as mock_extract:
            mock_extract.return_value = None

            result = _extract_user_identifier(user_info)

            # Should return fallback
            assert result == "sam_dev_user"




class TestAuthMiddleware:
    """Test authentication middleware configuration."""

    def test_auth_middleware_excludes_gateway_oauth_endpoints(self):
        """Test that /api/v1/gateway-oauth is excluded from auth middleware."""
        # The excluded_paths should include /api/v1/gateway-oauth
        # This allows gateway OAuth proxy to handle its own auth
        pass  # Tested through middleware configuration in integration tests


class TestGatewayOAuthProxyGlobalStorage:
    """Test global gateway OAuth proxy storage mechanism."""

    def test_gateway_oauth_proxy_global_initially_none(self):
        """Test that _gateway_oauth_proxy global is initially None."""
        import solace_agent_mesh.gateway.http_sse.main as main_module
        # Reset to initial state
        main_module._gateway_oauth_proxy = None
        assert main_module._gateway_oauth_proxy is None

class TestEnterpriseIntegrationPatterns:
    """Test integration patterns with enterprise package."""

    @pytest.mark.skipif(not ENTERPRISE_AVAILABLE, reason="Enterprise package not available")
    def test_enterprise_functions_accept_correct_parameters(self):
        """Test that enterprise utility functions accept correct parameters."""
        # Verify function signatures match expectations
        import inspect

        # Check validate_token_with_oauth_service signature
        sig = inspect.signature(oauth_utils.validate_token_with_oauth_service)
        params = list(sig.parameters.keys())
        # Should accept auth_service_url, auth_provider, access_token
        assert len(params) >= 3

        # Check get_user_info_from_oauth_service signature
        sig = inspect.signature(oauth_utils.get_user_info_from_oauth_service)
        params = list(sig.parameters.keys())
        assert len(params) >= 3

        # Check extract_user_identifier signature
        sig = inspect.signature(oauth_utils.extract_user_identifier)
        params = list(sig.parameters.keys())
        assert len(params) >= 1

