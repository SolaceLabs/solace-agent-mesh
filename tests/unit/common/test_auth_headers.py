"""Tests for common authentication header building utilities."""

import pytest
from unittest.mock import AsyncMock, patch
from solace_agent_mesh.common.auth_headers import (
    build_static_auth_headers,
    build_full_auth_headers,
)


class TestBuildStaticAuthHeaders:
    """Test suite for build_static_auth_headers()."""

    def test_static_bearer_token(self):
        """Test static bearer token authentication."""
        agent_config = {
            "authentication": {"type": "static_bearer", "token": "test_token_123"}
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {"Authorization": "Bearer test_token_123"}

    def test_static_apikey(self):
        """Test static API key authentication."""
        agent_config = {
            "authentication": {"type": "static_apikey", "token": "api_key_456"}
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {"X-API-Key": "api_key_456"}

    def test_legacy_bearer_scheme(self):
        """Test backward compatibility with legacy 'scheme' field."""
        agent_config = {
            "authentication": {
                "scheme": "bearer",  # Legacy format
                "token": "legacy_token",
            }
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {"Authorization": "Bearer legacy_token"}

    def test_legacy_apikey_scheme(self):
        """Test backward compatibility with legacy 'apikey' scheme."""
        agent_config = {
            "authentication": {
                "scheme": "apikey",  # Legacy format
                "token": "legacy_key",
            }
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {"X-API-Key": "legacy_key"}

    def test_custom_headers_override_auth(self):
        """Test that custom headers override auth headers."""
        agent_config = {
            "authentication": {"type": "static_bearer", "token": "original_token"},
            "agent_card_headers": [
                {"name": "Authorization", "value": "Custom override"},
                {"name": "X-Custom", "value": "custom_value"},
            ],
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {
            "Authorization": "Custom override",  # Overridden
            "X-Custom": "custom_value",
        }

    @patch("solace_agent_mesh.common.auth_headers.log")
    def test_oauth2_skipped_with_warning(self, mock_log):
        """Test that OAuth2 is skipped in sync context with warning."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            }
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
            log_identifier="[Test]",
        )

        # No auth header should be added
        assert headers == {}
        # Warning should be logged
        mock_log.warning.assert_called_once()
        call_args = " ".join(str(arg) for arg in mock_log.warning.call_args[0])
        assert "OAuth2 authentication" in call_args
        assert "not supported in synchronous context" in call_args

    def test_use_auth_false(self):
        """Test that use_auth=False skips authentication."""
        agent_config = {
            "authentication": {"type": "static_bearer", "token": "test_token"}
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=False,
        )

        assert headers == {}

    def test_no_authentication_config(self):
        """Test behavior when no authentication is configured."""
        agent_config = {}

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {}

    def test_missing_token(self):
        """Test behavior when token is missing."""
        agent_config = {
            "authentication": {
                "type": "static_bearer"
                # No token field
            }
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=True,
        )

        assert headers == {}

    def test_custom_headers_only(self):
        """Test custom headers without authentication."""
        agent_config = {
            "task_headers": [
                {"name": "X-Request-ID", "value": "req-123"},
                {"name": "X-Tenant", "value": "tenant-456"},
            ]
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=False,
        )

        assert headers == {"X-Request-ID": "req-123", "X-Tenant": "tenant-456"}

    def test_custom_headers_with_missing_fields(self):
        """Test that custom headers with missing name or value are skipped."""
        agent_config = {
            "agent_card_headers": [
                {"name": "X-Valid", "value": "valid_value"},
                {"name": "X-No-Value"},  # Missing value
                {"value": "no_name"},  # Missing name
                {},  # Both missing
            ]
        }

        headers = build_static_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="agent_card_headers",
            use_auth=False,
        )

        assert headers == {"X-Valid": "valid_value"}


class TestBuildAuthHeadersAsync:
    """Test suite for build_full_auth_headers()."""

    @pytest.mark.asyncio
    async def test_static_bearer_async(self):
        """Test static bearer token in async context."""
        agent_config = {
            "authentication": {"type": "static_bearer", "token": "async_token"}
        }

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=True,
        )

        assert headers == {"Authorization": "Bearer async_token"}

    @pytest.mark.asyncio
    async def test_oauth2_with_token_fetcher(self):
        """Test OAuth2 with token fetcher."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            }
        }

        # Mock token fetcher
        async def mock_fetcher(agent_name, auth_config):
            assert agent_name == "test-agent"
            assert auth_config["client_id"] == "client123"
            return "oauth_access_token_xyz"

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=True,
            oauth_token_fetcher=mock_fetcher,
        )

        assert headers == {"Authorization": "Bearer oauth_access_token_xyz"}

    @pytest.mark.asyncio
    async def test_oauth2_without_token_fetcher_raises(self):
        """Test that OAuth2 without token fetcher raises ValueError."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            }
        }

        with pytest.raises(ValueError, match="no oauth_token_fetcher provided"):
            await build_full_auth_headers(
                agent_name="test-agent",
                agent_config=agent_config,
                custom_headers_key="task_headers",
                use_auth=True,
                oauth_token_fetcher=None,  # Missing!
            )

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.common.auth_headers.log")
    async def test_oauth2_token_fetch_failure(self, mock_log):
        """Test that OAuth2 token fetch failure is logged but non-fatal."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            }
        }

        # Mock token fetcher that raises
        async def failing_fetcher(agent_name, auth_config):
            raise RuntimeError("Token service unavailable")

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=True,
            log_identifier="[Test]",
            oauth_token_fetcher=failing_fetcher,
        )

        # Should return headers without auth (matches existing behavior)
        assert "Authorization" not in headers
        # Error should be logged
        mock_log.error.assert_called_once()
        call_args = " ".join(str(arg) for arg in mock_log.error.call_args[0])
        assert "Failed to obtain OAuth 2.0 token" in call_args

    @pytest.mark.asyncio
    async def test_oauth2_with_custom_headers(self):
        """Test OAuth2 + custom headers combination."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            },
            "task_headers": [{"name": "X-Custom", "value": "custom_value"}],
        }

        async def mock_fetcher(agent_name, auth_config):
            return "oauth_token"

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=True,
            oauth_token_fetcher=mock_fetcher,
        )

        assert headers == {
            "Authorization": "Bearer oauth_token",
            "X-Custom": "custom_value",
        }

    @pytest.mark.asyncio
    async def test_static_auth_with_custom_headers_override(self):
        """Test that custom headers override OAuth2 auth headers."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            },
            "task_headers": [
                {"name": "Authorization", "value": "Custom Bearer override"}
            ],
        }

        async def mock_fetcher(agent_name, auth_config):
            return "oauth_token"

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=True,
            oauth_token_fetcher=mock_fetcher,
        )

        # Custom header should override OAuth2 token
        assert headers == {"Authorization": "Custom Bearer override"}

    @pytest.mark.asyncio
    async def test_use_auth_false_in_async(self):
        """Test that use_auth=False works in async context."""
        agent_config = {
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client123",
                "client_secret": "secret456",
            }
        }

        async def mock_fetcher(agent_name, auth_config):
            pytest.fail("Token fetcher should not be called when use_auth=False")

        headers = await build_full_auth_headers(
            agent_name="test-agent",
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=False,
            oauth_token_fetcher=mock_fetcher,
        )

        assert headers == {}
