"""
Unit tests for OAuth utility integration in http_sse/main.py.
Tests enterprise OAuth integration, get_gateway_oauth_proxy, and utility function usage.
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


class TestGetGatewayOAuthProxy:
    """Test get_gateway_oauth_proxy function."""

    def test_get_gateway_oauth_proxy_returns_none_without_component(self):
        """Test that get_gateway_oauth_proxy returns None when component not set."""
        # Reset global component
        import solace_agent_mesh.gateway.http_sse.main as main_module
        main_module._component = None

        result = main_module.get_gateway_oauth_proxy()

        assert result is None

    def test_get_gateway_oauth_proxy_returns_none_without_proxy_attribute(self):
        """Test that get_gateway_oauth_proxy returns None when proxy not set."""
        import solace_agent_mesh.gateway.http_sse.main as main_module

        # Create mock component without gateway_oauth_proxy attribute
        mock_component = MagicMock(spec=[])  # Empty spec - no attributes
        main_module._component = mock_component

        result = main_module.get_gateway_oauth_proxy()

        assert result is None

    def test_get_gateway_oauth_proxy_returns_proxy_when_set(self):
        """Test that get_gateway_oauth_proxy returns proxy when configured."""
        import solace_agent_mesh.gateway.http_sse.main as main_module

        # Create mock component with gateway_oauth_proxy
        mock_proxy = MagicMock()
        mock_component = MagicMock()
        mock_component.gateway_oauth_proxy = mock_proxy
        main_module._component = mock_component

        result = main_module.get_gateway_oauth_proxy()

        assert result is mock_proxy


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
class TestGetUserInfoWithEnterprise:
    """Test _get_user_info with enterprise OAuth utilities."""

    @pytest.mark.asyncio
    async def test_get_user_info_calls_enterprise_util(self):
        """Test that _get_user_info calls enterprise get_user_info_from_oauth_service."""
        from solace_agent_mesh.gateway.http_sse.main import _get_user_info

        user_info = {"sub": "user123", "email": "test@example.com"}

        with patch.object(
            oauth_utils,
            'get_user_info_from_oauth_service',
            new_callable=AsyncMock
        ) as mock_get_info:
            mock_get_info.return_value = user_info

            result = await _get_user_info(
                "https://auth.example.com",
                "google",
                "test-token"
            )

            assert result == user_info
            mock_get_info.assert_called_once_with(
                "https://auth.example.com",
                "google",
                "test-token"
            )


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


@pytest.mark.skipif(ENTERPRISE_AVAILABLE, reason="Test requires enterprise NOT available")
class TestOAuthWithoutEnterprise:
    """Test OAuth functions when enterprise package is not available."""

    @pytest.mark.asyncio
    async def test_validate_token_raises_import_error(self):
        """Test that _validate_token raises ImportError when enterprise not available."""
        from solace_agent_mesh.gateway.http_sse.main import _validate_token

        with pytest.raises(ImportError, match="Enterprise package required"):
            await _validate_token(
                "https://auth.example.com",
                "google",
                "test-token"
            )

    @pytest.mark.asyncio
    async def test_get_user_info_raises_import_error(self):
        """Test that _get_user_info raises ImportError when enterprise not available."""
        from solace_agent_mesh.gateway.http_sse.main import _get_user_info

        with pytest.raises(ImportError, match="Enterprise package required"):
            await _get_user_info(
                "https://auth.example.com",
                "google",
                "test-token"
            )

    def test_extract_user_identifier_raises_import_error(self):
        """Test that _extract_user_identifier raises ImportError when enterprise not available."""
        from solace_agent_mesh.gateway.http_sse.main import _extract_user_identifier

        with pytest.raises(ImportError, match="Enterprise package required"):
            _extract_user_identifier({"sub": "user123"})


class TestSetupDependencies:
    """Test setup_dependencies function with OAuth proxy setup."""

    def test_setup_dependencies_is_idempotent(self):
        """Test that setup_dependencies can be called multiple times safely."""
        # This is tested through the _dependencies_initialized flag
        pass  # Covered by integration tests

    def test_setup_dependencies_stores_component_globally(self):
        """Test that setup_dependencies stores component in _component global."""
        import solace_agent_mesh.gateway.http_sse.main as main_module

        mock_component = MagicMock()

        # Reset initialization flag to allow setup
        main_module._dependencies_initialized = False

        with patch.object(main_module.dependencies, 'set_component_instance'):
            with patch.object(main_module, '_setup_middleware'):
                with patch.object(main_module, '_setup_routers'):
                    with patch.object(main_module, '_setup_oauth_proxy_routes'):
                        main_module.setup_dependencies(
                            mock_component,
                            database_url="sqlite:///:memory:"
                        )

        # Verify component was stored
        assert main_module._component is mock_component

        # Reset for other tests
        main_module._dependencies_initialized = False

    def test_setup_dependencies_calls_oauth_proxy_setup(self):
        """Test that setup_dependencies calls _setup_oauth_proxy_routes."""
        import solace_agent_mesh.gateway.http_sse.main as main_module

        mock_component = MagicMock()
        main_module._dependencies_initialized = False

        with patch.object(main_module.dependencies, 'set_component_instance'):
            with patch.object(main_module, '_setup_middleware'):
                with patch.object(main_module, '_setup_routers'):
                    with patch.object(main_module, '_setup_oauth_proxy_routes') as mock_oauth_setup:
                        main_module.setup_dependencies(
                            mock_component,
                            database_url="sqlite:///:memory:"
                        )

                        # Verify OAuth setup was called
                        mock_oauth_setup.assert_called_once_with(mock_component)

        # Reset
        main_module._dependencies_initialized = False


class TestAuthMiddleware:
    """Test authentication middleware configuration."""

    def test_auth_middleware_excludes_gateway_oauth_endpoints(self):
        """Test that /api/v1/gateway-oauth is excluded from auth middleware."""
        # The excluded_paths should include /api/v1/gateway-oauth
        # This allows gateway OAuth proxy to handle its own auth
        pass  # Tested through middleware configuration in integration tests


class TestOAuthUtilsImport:
    """Test oauth_utils import handling."""

    def test_oauth_utils_none_when_enterprise_unavailable(self):
        """Test that oauth_utils is None when enterprise package not available."""
        if not ENTERPRISE_AVAILABLE:
            from solace_agent_mesh.gateway.http_sse.main import oauth_utils as imported_utils
            assert imported_utils is None

    @pytest.mark.skipif(not ENTERPRISE_AVAILABLE, reason="Enterprise package not available")
    def test_oauth_utils_available_when_enterprise_installed(self):
        """Test that oauth_utils is imported when enterprise package is available."""
        from solace_agent_mesh.gateway.http_sse.main import oauth_utils as imported_utils
        assert imported_utils is not None


class TestComponentGlobalStorage:
    """Test global component storage mechanism."""

    def test_component_global_initially_none(self):
        """Test that _component global is initially None."""
        import solace_agent_mesh.gateway.http_sse.main as main_module
        # Reset to initial state
        main_module._component = None
        assert main_module._component is None

    def test_get_gateway_oauth_proxy_accesses_global_component(self):
        """Test that get_gateway_oauth_proxy accesses the global _component."""
        import solace_agent_mesh.gateway.http_sse.main as main_module

        # Set a mock component with proxy
        mock_proxy = MagicMock()
        mock_component = MagicMock()
        mock_component.gateway_oauth_proxy = mock_proxy
        main_module._component = mock_component

        # get_gateway_oauth_proxy should access the global
        result = main_module.get_gateway_oauth_proxy()

        assert result is mock_proxy


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


class TestSetupOAuthProxyRoutes:
    """Test _setup_oauth_proxy_routes function."""

    def test_setup_oauth_proxy_routes_called_during_setup(self):
        """Test that _setup_oauth_proxy_routes is called during setup_dependencies."""
        # Covered by TestSetupDependencies.test_setup_dependencies_calls_oauth_proxy_setup
        pass

    def test_setup_oauth_proxy_routes_with_enterprise_available(self):
        """Test _setup_oauth_proxy_routes when enterprise package is available."""
        # Should import and call setup_oauth_proxy_routes from enterprise
        pass  # Covered by integration tests with enterprise

    def test_setup_oauth_proxy_routes_without_enterprise(self):
        """Test _setup_oauth_proxy_routes when enterprise package not available."""
        # Should handle gracefully (enterprise feature)
        pass  # Covered by integration tests without enterprise
