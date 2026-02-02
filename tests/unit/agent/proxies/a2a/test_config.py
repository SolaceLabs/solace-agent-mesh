"""
Unit tests for A2A proxy configuration models with separate authentication.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.agent.proxies.a2a.config import A2AProxiedAgentConfig


class TestSeparateAuthenticationFields:
    """Tests for agent_card_authentication and task_authentication fields."""

    def test_agent_card_auth_static_bearer(self):
        """Test agent_card_authentication with static_bearer type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_bearer", "token": "card-token"},
        )
        assert config.agent_card_authentication is not None
        assert config.agent_card_authentication.type == "static_bearer"
        assert config.agent_card_authentication.token == "card-token"

    def test_agent_card_auth_static_apikey(self):
        """Test agent_card_authentication with static_apikey type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_apikey", "token": "api-key-123"},
        )
        assert config.agent_card_authentication is not None
        assert config.agent_card_authentication.type == "static_apikey"
        assert config.agent_card_authentication.token == "api-key-123"

    def test_agent_card_auth_oauth2_client_credentials(self):
        """Test agent_card_authentication with oauth2_client_credentials type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client-123",
                "client_secret": "secret-456",
            },
        )
        assert config.agent_card_authentication is not None
        assert config.agent_card_authentication.type == "oauth2_client_credentials"
        assert config.agent_card_authentication.token_url == "https://auth.example.com/token"
        assert config.agent_card_authentication.client_id == "client-123"

    def test_agent_card_auth_oauth2_authorization_code(self):
        """Test agent_card_authentication with oauth2_authorization_code type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={
                "type": "oauth2_authorization_code",
                "client_id": "client-123",
                "redirect_uri": "https://callback.example.com/oauth",
            },
        )
        assert config.agent_card_authentication is not None
        assert config.agent_card_authentication.type == "oauth2_authorization_code"
        assert config.agent_card_authentication.client_id == "client-123"
        assert config.agent_card_authentication.redirect_uri == "https://callback.example.com/oauth"

    def test_task_auth_static_bearer(self):
        """Test task_authentication with static_bearer type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            task_authentication={"type": "static_bearer", "token": "task-token"},
        )
        assert config.task_authentication is not None
        assert config.task_authentication.type == "static_bearer"
        assert config.task_authentication.token == "task-token"

    def test_task_auth_oauth2_client_credentials(self):
        """Test task_authentication with oauth2_client_credentials type."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            task_authentication={
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "task-client",
                "client_secret": "task-secret",
                "scope": "read write",
            },
        )
        assert config.task_authentication is not None
        assert config.task_authentication.type == "oauth2_client_credentials"
        assert config.task_authentication.scope == "read write"

    def test_both_auth_fields_different_types(self):
        """Test using different auth types for agent card and tasks."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_bearer", "token": "card-token"},
            task_authentication={
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "task-client",
                "client_secret": "task-secret",
            },
        )
        assert config.agent_card_authentication.type == "static_bearer"
        assert config.task_authentication.type == "oauth2_client_credentials"

    def test_only_agent_card_auth(self):
        """Test specifying only agent_card_authentication (no task auth)."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_bearer", "token": "card-token"},
        )
        assert config.agent_card_authentication is not None
        assert config.task_authentication is None
        assert config.authentication is None

    def test_only_task_auth(self):
        """Test specifying only task_authentication (no agent card auth)."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            task_authentication={"type": "static_bearer", "token": "task-token"},
        )
        assert config.task_authentication is not None
        assert config.agent_card_authentication is None
        assert config.authentication is None

    def test_no_authentication(self):
        """Test agent config with no authentication at all."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
        )
        assert config.authentication is None
        assert config.agent_card_authentication is None
        assert config.task_authentication is None


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy authentication field."""

    def test_legacy_auth_only_default_flag(self):
        """Test legacy authentication field with default use_auth_for_agent_card=False."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy-token"},
        )
        assert config.authentication is not None
        assert config.authentication.token == "legacy-token"
        assert config.use_auth_for_agent_card is False
        assert config.agent_card_authentication is None
        assert config.task_authentication is None

    def test_legacy_auth_with_agent_card_flag_true(self):
        """Test legacy authentication with use_auth_for_agent_card=True."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy-token"},
            use_auth_for_agent_card=True,
        )
        assert config.authentication is not None
        assert config.use_auth_for_agent_card is True
        assert config.agent_card_authentication is None
        assert config.task_authentication is None

    def test_legacy_auth_with_scheme_field(self):
        """Test legacy authentication using 'scheme' field (backward compat)."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"scheme": "bearer", "token": "legacy-token"},
        )
        assert config.authentication is not None
        assert config.authentication.token == "legacy-token"

    def test_new_fields_with_legacy_auth_logs_info(self, caplog):
        """Test that using new fields with legacy auth logs informational message."""
        import logging
        caplog.set_level(logging.INFO, logger="solace_ai_connector.common.log")

        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy"},
            agent_card_authentication={"type": "static_bearer", "token": "card"},
            task_authentication={"type": "static_bearer", "token": "task"},
        )

        assert config.authentication is not None
        assert config.agent_card_authentication is not None
        assert config.task_authentication is not None

        # Check that info message was logged about precedence
        assert "New auth fields take precedence" in caplog.text
        assert "test-agent" in caplog.text

    def test_use_auth_flag_with_new_fields_warns(self, caplog):
        """Test that use_auth_for_agent_card with new fields logs warning."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_bearer", "token": "card"},
            use_auth_for_agent_card=True,
        )

        assert config.agent_card_authentication is not None

        # Check that warning was logged
        assert "'use_auth_for_agent_card' is ignored" in caplog.text
        assert "test-agent" in caplog.text

    def test_use_auth_flag_with_new_fields_and_legacy_auth_no_warn(self, caplog):
        """Test that flag with both legacy and new auth doesn't double-warn."""
        import logging
        caplog.set_level(logging.WARNING, logger="solace_ai_connector.common.log")

        A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy"},
            agent_card_authentication={"type": "static_bearer", "token": "card"},
            use_auth_for_agent_card=True,
        )

        # Should log info about precedence but not warn about flag
        # (flag is relevant for legacy auth)
        assert "'use_auth_for_agent_card' is ignored" not in caplog.text
        # Note: INFO level logs might not be captured with WARNING level, so skip this assertion
        # The important test is that we don't warn about the flag


class TestAuthenticationValidation:
    """Tests for authentication config validation."""

    def test_static_bearer_requires_token(self):
        """Test that static_bearer requires token field."""
        with pytest.raises(ValidationError, match="requires 'token'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                agent_card_authentication={"type": "static_bearer"},
            )

    def test_static_apikey_requires_token(self):
        """Test that static_apikey requires token field."""
        with pytest.raises(ValidationError, match="requires 'token'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                task_authentication={"type": "static_apikey"},
            )

    def test_oauth2_client_credentials_requires_fields(self):
        """Test that oauth2_client_credentials requires all necessary fields."""
        # Missing token_url
        with pytest.raises(ValidationError, match="requires 'token_url'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                agent_card_authentication={
                    "type": "oauth2_client_credentials",
                    "client_id": "client",
                    "client_secret": "secret",
                },
            )

        # Missing client_id
        with pytest.raises(ValidationError, match="requires 'client_id'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                task_authentication={
                    "type": "oauth2_client_credentials",
                    "token_url": "https://auth.example.com/token",
                    "client_secret": "secret",
                },
            )

        # Missing client_secret
        with pytest.raises(ValidationError, match="requires 'client_secret'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                agent_card_authentication={
                    "type": "oauth2_client_credentials",
                    "token_url": "https://auth.example.com/token",
                    "client_id": "client",
                },
            )

    def test_oauth2_token_url_must_be_https(self):
        """Test that oauth2 token_url must use HTTPS."""
        with pytest.raises(ValidationError, match="must use HTTPS"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                task_authentication={
                    "type": "oauth2_client_credentials",
                    "token_url": "http://auth.example.com/token",  # HTTP not allowed
                    "client_id": "client",
                    "client_secret": "secret",
                },
            )

    def test_oauth2_authorization_code_requires_fields(self):
        """Test that oauth2_authorization_code requires necessary fields."""
        # Missing client_id
        with pytest.raises(ValidationError, match="requires 'client_id'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                agent_card_authentication={
                    "type": "oauth2_authorization_code",
                    "redirect_uri": "https://callback.example.com/oauth",
                },
            )

        # Missing redirect_uri
        with pytest.raises(ValidationError, match="requires 'redirect_uri'"):
            A2AProxiedAgentConfig(
                name="test-agent",
                url="https://example.com",
                task_authentication={
                    "type": "oauth2_authorization_code",
                    "client_id": "client",
                },
            )


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_explicit_none_for_agent_card_auth(self):
        """Test explicitly setting agent_card_authentication to None."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy"},
            agent_card_authentication=None,
        )
        assert config.agent_card_authentication is None
        assert config.authentication is not None

    def test_explicit_none_for_task_auth(self):
        """Test explicitly setting task_authentication to None."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            authentication={"type": "static_bearer", "token": "legacy"},
            task_authentication=None,
        )
        assert config.task_authentication is None
        assert config.authentication is not None

    def test_all_header_types_together(self):
        """Test using custom headers with separate auth configs."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={"type": "static_bearer", "token": "card-token"},
            task_authentication={"type": "static_bearer", "token": "task-token"},
            agent_card_headers=[{"name": "X-Custom-Card", "value": "card-value"}],
            task_headers=[{"name": "X-Custom-Task", "value": "task-value"}],
        )
        assert config.agent_card_authentication is not None
        assert config.task_authentication is not None
        assert len(config.agent_card_headers) == 1
        assert len(config.task_headers) == 1
        assert config.agent_card_headers[0].name == "X-Custom-Card"
        assert config.task_headers[0].name == "X-Custom-Task"

    def test_oauth2_with_optional_scope(self):
        """Test OAuth2 client credentials with optional scope parameter."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            task_authentication={
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client",
                "client_secret": "secret",
                "scope": "read write admin",
            },
        )
        assert config.task_authentication.scope == "read write admin"

    def test_oauth2_authorization_code_with_optional_fields(self):
        """Test OAuth2 authorization code with optional authorization_url and scopes."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            agent_card_authentication={
                "type": "oauth2_authorization_code",
                "client_id": "client",
                "redirect_uri": "https://callback.example.com/oauth",
                "authorization_url": "https://auth.example.com/authorize",
                "scopes": ["read", "write", "profile"],
                "client_secret": "optional-secret",
            },
        )
        assert config.agent_card_authentication.authorization_url == "https://auth.example.com/authorize"
        assert config.agent_card_authentication.scopes == ["read", "write", "profile"]
        assert config.agent_card_authentication.client_secret == "optional-secret"


class TestDisplayNameField:
    """Tests for display_name field in A2AProxiedAgentConfig."""

    def test_display_name_provided(self):
        """Test display_name field is accepted and stored."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            display_name="My Custom Agent",
        )
        assert config.display_name == "My Custom Agent"

    def test_display_name_none_default(self):
        """Test display_name defaults to None when not provided."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
        )
        assert config.display_name is None

    def test_display_name_empty_string(self):
        """Test display_name accepts empty string."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            display_name="",
        )
        assert config.display_name == ""

    def test_display_name_with_special_characters(self):
        """Test display_name accepts special characters (for UI display)."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            display_name="Agent™ (Beta) - v2.0 🚀",
        )
        assert config.display_name == "Agent™ (Beta) - v2.0 🚀"

    def test_display_name_with_whitespace(self):
        """Test display_name accepts whitespace (will be stripped at usage)."""
        config = A2AProxiedAgentConfig(
            name="test-agent",
            url="https://example.com",
            display_name="   My Agent   ",
        )
        assert config.display_name == "   My Agent   "
