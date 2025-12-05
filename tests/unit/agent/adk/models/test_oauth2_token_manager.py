"""Unit tests for OAuth2ClientCredentialsTokenManager."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from solace_agent_mesh.agent.adk.models.oauth2_token_manager import (
    OAuth2ClientCredentialsTokenManager,
)


@pytest.fixture
def token_manager():
    """Create a token manager instance for testing."""
    manager = OAuth2ClientCredentialsTokenManager(
        token_url="https://auth.example.com/oauth/token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        scope="read write",
        refresh_buffer_seconds=300,
    )
    # Clear cache before each test
    manager._cache.clear()
    return manager


@pytest.fixture
def mock_token_response():
    """Mock successful token response."""
    return {
        "access_token": "test_access_token_12345",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "read write",
    }


class TestOAuth2ClientCredentialsTokenManager:
    """Test cases for OAuth2ClientCredentialsTokenManager."""

    def test_init_valid_parameters(self):
        """Test initialization with valid parameters."""
        manager = OAuth2ClientCredentialsTokenManager(
            token_url="https://auth.example.com/oauth/token",
            client_id="test_client",
            client_secret="test_secret",
        )
        
        assert manager.token_url == "https://auth.example.com/oauth/token"
        assert manager.client_id == "test_client"
        assert manager.client_secret == "test_secret"
        assert manager.scope is None
        assert manager.refresh_buffer_seconds == 300
        assert manager._cache is not None

    def test_init_invalid_parameters(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(ValueError, match="token_url is required"):
            OAuth2ClientCredentialsTokenManager(
                token_url="",
                client_id="test_client",
                client_secret="test_secret",
            )
        
        with pytest.raises(ValueError, match="client_id is required"):
            OAuth2ClientCredentialsTokenManager(
                token_url="https://auth.example.com/oauth/token",
                client_id="",
                client_secret="test_secret",
            )
        
        with pytest.raises(ValueError, match="client_secret is required"):
            OAuth2ClientCredentialsTokenManager(
                token_url="https://auth.example.com/oauth/token",
                client_id="test_client",
                client_secret="",
            )

    @pytest.mark.asyncio
    async def test_token_acquisition_success(self, token_manager, mock_token_response):
        """Test successful token acquisition."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Test token acquisition
            token = await token_manager.get_token()

            assert token == "test_access_token_12345"

            # Verify the request was made correctly
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args

            assert call_args[0][0] == "https://auth.example.com/oauth/token"
            assert call_args[1]["data"]["grant_type"] == "client_credentials"
            assert call_args[1]["data"]["client_id"] == "test_client_id"
            assert call_args[1]["data"]["client_secret"] == "test_client_secret"
            assert call_args[1]["data"]["scope"] == "read write"

    @pytest.mark.asyncio
    async def test_token_caching(self, token_manager, mock_token_response):
        """Test that subsequent calls use cached token."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # First call should fetch token
            token1 = await token_manager.get_token()
            assert token1 == "test_access_token_12345"

            # Second call should use cached token
            token2 = await token_manager.get_token()
            assert token2 == "test_access_token_12345"

            # Verify only one HTTP request was made
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 1

    @pytest.mark.asyncio
    async def test_token_refresh_on_expiration(self, token_manager, mock_token_response):
        """Test token refresh when token is expired or near expiry."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client, \
             patch("solace_agent_mesh.common.oauth.utils.time.time") as mock_time:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Mock time progression
            current_time = 1000
            mock_time.return_value = current_time

            # First call - token is cached
            token1 = await token_manager.get_token()
            assert token1 == "test_access_token_12345"

            # Advance time to near expiry (within refresh buffer)
            mock_time.return_value = current_time + 3600 - 200  # 200 seconds before expiry

            # Second call should refresh token
            token2 = await token_manager.get_token()
            assert token2 == "test_access_token_12345"

            # Verify two HTTP requests were made (initial + refresh)
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 2

    @pytest.mark.asyncio
    async def test_http_error_handling(self, token_manager):
        """Test handling of various HTTP errors."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client:
            # Test 401 Unauthorized (should not retry)
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401 Unauthorized", request=MagicMock(), response=mock_response
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                await token_manager.get_token()

            # Verify only one attempt was made (no retries for 4xx errors)
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 1

    @pytest.mark.asyncio
    async def test_http_error_handling_with_retries(self, token_manager):
        """Test handling of 5xx errors with retries."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client, \
             patch("solace_agent_mesh.common.oauth.oauth_client.asyncio.sleep") as mock_sleep:
            # Test 500 Internal Server Error (should retry)
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Internal Server Error", request=MagicMock(), response=mock_response
                )
            )
            mock_sleep.return_value = None  # Skip actual sleep

            with pytest.raises(httpx.HTTPStatusError):
                await token_manager.get_token()

            # Verify retries were attempted (max_retries + 1 = 4 attempts)
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 4

    @pytest.mark.asyncio
    async def test_ssl_certificate_validation(self, mock_token_response):
        """Test SSL certificate validation with custom CA."""
        manager = OAuth2ClientCredentialsTokenManager(
            token_url="https://auth.example.com/oauth/token",
            client_id="test_client",
            client_secret="test_secret",
            ca_cert_path="/path/to/ca.crt",
        )

        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await manager.get_token()

            # Verify AsyncClient was called with custom CA cert
            mock_client.assert_called_with(verify="/path/to/ca.crt")

    @pytest.mark.asyncio
    async def test_concurrent_token_requests(self, token_manager, mock_token_response):
        """Test thread safety with concurrent token requests."""
        with patch("solace_agent_mesh.common.oauth.oauth_client.httpx.AsyncClient") as mock_client:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Make multiple concurrent requests
            tasks = [token_manager.get_token() for _ in range(5)]
            tokens = await asyncio.gather(*tasks)

            # All should return the same token
            assert all(token == "test_access_token_12345" for token in tokens)

            # Only one HTTP request should have been made due to caching and locking
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 1

    def test_is_token_expired(self, token_manager):
        """Test token expiration checking."""
        from solace_agent_mesh.common.oauth import is_token_expired

        current_time = time.time()

        # Token that expires in the future (not expired)
        assert not is_token_expired(current_time + 1000, buffer_seconds=token_manager.refresh_buffer_seconds)

        # Token that expires within buffer time (considered expired)
        assert is_token_expired(current_time + 200, buffer_seconds=token_manager.refresh_buffer_seconds)  # 200 < 300 buffer

        # Token that has already expired
        assert is_token_expired(current_time - 100, buffer_seconds=token_manager.refresh_buffer_seconds)

        # Edge case: token expires exactly at buffer boundary
        assert is_token_expired(current_time + 300, buffer_seconds=token_manager.refresh_buffer_seconds)
