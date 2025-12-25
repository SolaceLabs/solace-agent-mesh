"""
Unit tests for auth router endpoints.

These tests verify the internal logic of auth endpoints using mocked dependencies.
For integration tests that verify HTTP responses and external service interactions,
see tests/integration/apis/test_auth_api.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

# Test if enterprise package is available
try:
    from solace_agent_mesh_enterprise.gateway.auth.internal import oauth_utils
    ENTERPRISE_AVAILABLE = True
except ImportError:
    oauth_utils = None
    ENTERPRISE_AVAILABLE = False

class TestLogoutEndpoint:
    """Unit tests for the logout endpoint logic"""

    @pytest.mark.asyncio
    async def test_logout_clears_access_token_from_session(self):
        """Test that logout removes access_token from session"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request with session containing access_token
        mock_request = MagicMock()
        mock_request.session = {
            'access_token': 'test-access-token',
            'other_data': 'should-also-be-cleared'
        }

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: access_token is removed from session
        assert 'access_token' not in mock_request.session
        assert result["success"] is True
        assert result["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_clears_refresh_token_from_session(self):
        """Test that logout removes refresh_token from session"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request with session containing refresh_token
        mock_request = MagicMock()
        mock_request.session = {
            'access_token': 'test-access-token',
            'refresh_token': 'test-refresh-token'
        }

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: refresh_token is removed from session
        assert 'refresh_token' not in mock_request.session
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logout_clears_all_session_data(self):
        """Test that logout clears all session data including tokens"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request with session containing multiple items
        mock_request = MagicMock()
        mock_request.session = {
            'access_token': 'test-access-token',
            'refresh_token': 'test-refresh-token',
            'user_id': 'test-user',
            'other_data': 'value'
        }

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: All session data is cleared
        assert len(mock_request.session) == 0
        assert 'access_token' not in mock_request.session
        assert 'refresh_token' not in mock_request.session
        assert 'user_id' not in mock_request.session
        assert 'other_data' not in mock_request.session
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logout_is_idempotent_without_session(self):
        """Test that logout succeeds even when session has no tokens"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request with empty session
        mock_request = MagicMock()
        mock_request.session = {}

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: Still returns success (idempotent)
        assert result["success"] is True
        assert result["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_handles_session_without_access_token(self):
        """Test logout when session has refresh_token but no access_token"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Session with only refresh_token
        mock_request = MagicMock()
        mock_request.session = {
            'refresh_token': 'test-refresh-token',
            'user_id': 'test-user'
        }

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: Clears all session data
        assert len(mock_request.session) == 0
        assert 'refresh_token' not in mock_request.session
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logout_handles_session_without_refresh_token(self):
        """Test logout when session has access_token but no refresh_token"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Session with only access_token
        mock_request = MagicMock()
        mock_request.session = {
            'access_token': 'test-access-token',
            'user_id': 'test-user'
        }

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: Clears all session data
        assert len(mock_request.session) == 0
        assert 'access_token' not in mock_request.session
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logout_returns_success_even_on_exception(self):
        """Test that logout returns success even if an exception occurs (idempotent design)"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request where session operations raise exceptions
        mock_request = MagicMock()
        mock_request.session = MagicMock()
        mock_request.session.__contains__ = MagicMock(side_effect=Exception("Test exception"))

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: Still returns success (graceful degradation)
        assert result["success"] is True
        assert result["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_with_request_without_session_attribute(self):
        """Test logout handles request without session attribute gracefully"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import logout

        # Arrange: Create mock request without session attribute
        mock_request = MagicMock(spec=[])  # spec=[] means no attributes

        # Act: Call logout
        result = await logout(mock_request)

        # Assert: Still returns success
        assert result["success"] is True
        assert result["message"] == "Logged out successfully"


class TestGetCsrfTokenEndpoint:
    """Unit tests for the CSRF token endpoint logic"""

    @pytest.mark.asyncio
    async def test_get_csrf_token_generates_token(self):
        """Test that get_csrf_token generates a CSRF token"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import get_csrf_token

        # Arrange: Create mock response and component
        mock_response = MagicMock()
        mock_component = MagicMock()

        # Act: Call get_csrf_token
        with patch('solace_agent_mesh.gateway.http_sse.routers.auth.secrets.token_urlsafe') as mock_token:
            mock_token.return_value = 'test-csrf-token-123'
            result = await get_csrf_token(mock_response, mock_component)

        # Assert: Returns the generated token
        assert result["message"] == "CSRF token set"
        assert result["csrf_token"] == 'test-csrf-token-123'
        mock_token.assert_called_once_with(32)

    @pytest.mark.asyncio
    async def test_get_csrf_token_sets_cookie(self):
        """Test that get_csrf_token sets a cookie with correct attributes"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import get_csrf_token

        # Arrange: Create mock response and component
        mock_response = MagicMock()
        mock_component = MagicMock()

        # Act: Call get_csrf_token
        with patch('solace_agent_mesh.gateway.http_sse.routers.auth.secrets.token_urlsafe') as mock_token:
            mock_token.return_value = 'test-csrf-token-456'
            await get_csrf_token(mock_response, mock_component)

        # Assert: Cookie is set with correct parameters
        mock_response.set_cookie.assert_called_once_with(
            key="csrf_token",
            value="test-csrf-token-456",
            httponly=False,
            secure=False,
            samesite="lax",
            max_age=3600,
        )

    @pytest.mark.asyncio
    async def test_get_csrf_token_generates_unique_tokens(self):
        """Test that get_csrf_token generates cryptographically secure tokens"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import get_csrf_token

        # Arrange
        mock_response = MagicMock()
        mock_component = MagicMock()

        # Act: Call twice to verify randomness
        with patch('solace_agent_mesh.gateway.http_sse.routers.auth.secrets.token_urlsafe') as mock_token:
            mock_token.side_effect = ['token1', 'token2']
            result1 = await get_csrf_token(mock_response, mock_component)
            result2 = await get_csrf_token(mock_response, mock_component)

        # Assert: Different tokens generated
        assert result1['csrf_token'] != result2['csrf_token']
        assert mock_token.call_count == 2


@pytest.mark.skipif(not ENTERPRISE_AVAILABLE, reason="Enterprise package not available")
class TestInitiateLoginEndpoint:
    """Unit tests for the initiate login endpoint logic"""

    @pytest.mark.asyncio
    async def test_initiate_login_redirects_to_auth_service(self):
        """Test that initiate_login redirects to external auth service"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import initiate_login

        # Arrange: Create mock request and config
        mock_request = MagicMock()
        mock_config = {
            'external_auth_service_url': 'https://auth.example.com',
            'external_auth_callback_uri': 'https://app.example.com/callback',
            'external_auth_provider': 'azure'
        }

        # Act: Call initiate_login
        result = await initiate_login(mock_request, mock_config)

        # Assert: Returns RedirectResponse
        assert isinstance(result, RedirectResponse)
        assert 'auth.example.com/login' in result.headers['location']
        assert 'provider=azure' in result.headers['location']
        assert 'redirect_uri=https%3A%2F%2Fapp.example.com%2Fcallback' in result.headers['location']

    @pytest.mark.asyncio
    async def test_initiate_login_uses_default_values(self):
        """Test that initiate_login uses default config values when not provided"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import initiate_login

        # Arrange: Empty config to use defaults
        mock_request = MagicMock()
        mock_config = {}

        # Act: Call initiate_login
        result = await initiate_login(mock_request, mock_config)

        # Assert: Uses default values
        assert isinstance(result, RedirectResponse)
        assert 'localhost:8080/login' in result.headers['location']
        assert 'provider=azure' in result.headers['location']
        assert 'redirect_uri=http%3A%2F%2Flocalhost%3A8000' in result.headers['location']

    @pytest.mark.asyncio
    async def test_initiate_login_includes_all_required_params(self):
        """Test that login URL includes provider and redirect_uri parameters"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import initiate_login

        # Arrange
        mock_request = MagicMock()
        mock_config = {
            'external_auth_service_url': 'https://auth.test.com',
            'external_auth_callback_uri': 'https://app.test.com/auth/callback',
            'external_auth_provider': 'google'
        }

        # Act
        result = await initiate_login(mock_request, mock_config)

        # Assert: All parameters present
        location = result.headers['location']
        assert 'provider=google' in location
        assert 'redirect_uri=' in location
        assert 'auth.test.com/login' in location

    @pytest.mark.asyncio
    async def test_initiate_login_encodes_redirect_uri(self):
        """Test that redirect_uri is properly URL encoded"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import initiate_login

        # Arrange
        mock_request = MagicMock()
        mock_config = {
            'external_auth_callback_uri': 'https://app.example.com/auth/callback?test=1'
        }

        # Act
        result = await initiate_login(mock_request, mock_config)

        # Assert: Special characters are encoded
        location = result.headers['location']
        # ? should be encoded as %3F
        assert '%3F' in location or 'redirect_uri=https%3A%2F%2Fapp.example.com%2Fauth%2Fcallback' in location

    @pytest.mark.asyncio
    async def test_initiate_login_with_custom_provider(self):
        """Test login initiation with different OAuth providers"""
        from solace_agent_mesh.gateway.http_sse.routers.auth import initiate_login

        # Arrange: Test with different providers
        mock_request = MagicMock()
        providers = ['azure', 'google', 'okta', 'auth0']

        for provider in providers:
            mock_config = {'external_auth_provider': provider}

            # Act
            result = await initiate_login(mock_request, mock_config)

            # Assert: Provider is included in URL
            assert f'provider={provider}' in result.headers['location']
