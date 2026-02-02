"""
Unit tests for A2A proxy component authentication resolution logic.

Tests the _get_effective_agent_card_auth() and _get_effective_task_auth() helper
methods that determine which authentication configuration to use based on the
new agent_card_authentication and task_authentication fields, with fallback
to the legacy authentication field.
"""

import pytest
from unittest.mock import patch
from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent


@pytest.fixture
def mock_component():
    """
    Create a minimal A2AProxyComponent instance for testing auth resolution.

    We mock out the initialization to avoid dependencies on the full component setup.
    """
    with patch.object(A2AProxyComponent, '__init__', lambda x, **kwargs: None):
        component = A2AProxyComponent()
        component.log_identifier = "[TestComponent]"
        component._agent_config_by_name = {}
        return component


class TestGetEffectiveAgentCardAuth:
    """Tests for _get_effective_agent_card_auth() method."""

    def test_uses_agent_card_authentication_when_present(self, mock_component):
        """
        When agent_card_authentication is specified, it should be used
        regardless of other auth fields.
        """
        agent_config = {
            "name": "test-agent",
            "agent_card_authentication": {
                "type": "static_bearer",
                "token": "card-token"
            },
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "client-id",
                "client_secret": "secret"
            },
            "use_auth_for_agent_card": False
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["agent_card_authentication"]
        assert auth_config["type"] == "static_bearer"
        assert auth_config["token"] == "card-token"

    def test_uses_legacy_auth_when_use_auth_for_agent_card_true(self, mock_component):
        """
        When only legacy authentication is present and use_auth_for_agent_card=True,
        it should use the legacy authentication.
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            },
            "use_auth_for_agent_card": True
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["authentication"]
        assert auth_config["token"] == "legacy-token"

    def test_no_auth_when_use_auth_for_agent_card_false(self, mock_component):
        """
        When only legacy authentication is present but use_auth_for_agent_card=False,
        no authentication should be used for agent card.
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            },
            "use_auth_for_agent_card": False
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is False
        assert auth_config is None

    def test_no_auth_when_use_auth_for_agent_card_not_set(self, mock_component):
        """
        When only legacy authentication is present and use_auth_for_agent_card
        is not set (defaults to False), no authentication should be used.
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is False
        assert auth_config is None

    def test_no_auth_when_no_auth_configured(self, mock_component):
        """
        When no authentication is configured at all, no authentication
        should be used for agent card.
        """
        agent_config = {
            "name": "test-agent",
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is False
        assert auth_config is None

    def test_agent_card_auth_takes_precedence_over_legacy_with_flag(self, mock_component):
        """
        When both agent_card_authentication and legacy authentication with flag are present,
        agent_card_authentication takes precedence.
        """
        agent_config = {
            "name": "test-agent",
            "agent_card_authentication": {
                "type": "static_apikey",
                "token": "new-card-token"
            },
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            },
            "use_auth_for_agent_card": True
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["agent_card_authentication"]
        assert auth_config["type"] == "static_apikey"
        assert auth_config["token"] == "new-card-token"

    def test_supports_oauth2_client_credentials_for_agent_card(self, mock_component):
        """
        OAuth2 client credentials should be supported for agent card authentication.
        """
        agent_config = {
            "name": "test-agent",
            "agent_card_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "card-client",
                "client_secret": "card-secret"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_agent_card_auth(agent_config)

        assert should_use_auth is True
        assert auth_config["type"] == "oauth2_client_credentials"
        assert auth_config["token_url"] == "https://auth.example.com/token"


class TestGetEffectiveTaskAuth:
    """Tests for _get_effective_task_auth() method."""

    def test_uses_task_authentication_when_present(self, mock_component):
        """
        When task_authentication is specified, it should be used
        regardless of other auth fields.
        """
        agent_config = {
            "name": "test-agent",
            "task_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "task-client",
                "client_secret": "task-secret"
            },
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["task_authentication"]
        assert auth_config["type"] == "oauth2_client_credentials"
        assert auth_config["client_id"] == "task-client"

    def test_uses_legacy_auth_for_tasks(self, mock_component):
        """
        When only legacy authentication is present, it should always be used
        for tasks (backward compatibility - tasks always got auth).
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["authentication"]
        assert auth_config["token"] == "legacy-token"

    def test_no_auth_when_no_auth_configured(self, mock_component):
        """
        When no authentication is configured at all, no authentication
        should be used for tasks.
        """
        agent_config = {
            "name": "test-agent",
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is False
        assert auth_config is None

    def test_task_auth_takes_precedence_over_legacy(self, mock_component):
        """
        When both task_authentication and legacy authentication are present,
        task_authentication takes precedence.
        """
        agent_config = {
            "name": "test-agent",
            "task_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "new-client",
                "client_secret": "new-secret"
            },
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is True
        assert auth_config == agent_config["task_authentication"]
        assert auth_config["type"] == "oauth2_client_credentials"
        assert auth_config["client_id"] == "new-client"

    def test_supports_static_apikey_for_tasks(self, mock_component):
        """
        Static API key authentication should be supported for tasks.
        """
        agent_config = {
            "name": "test-agent",
            "task_authentication": {
                "type": "static_apikey",
                "token": "task-apikey-12345"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is True
        assert auth_config["type"] == "static_apikey"
        assert auth_config["token"] == "task-apikey-12345"

    def test_supports_oauth2_authorization_code_for_tasks(self, mock_component):
        """
        OAuth2 authorization code flow should be supported for tasks.
        """
        agent_config = {
            "name": "test-agent",
            "task_authentication": {
                "type": "oauth2_authorization_code",
                "client_id": "task-client",
                "redirect_uri": "https://example.com/callback"
            }
        }

        auth_config, should_use_auth = mock_component._get_effective_task_auth(agent_config)

        assert should_use_auth is True
        assert auth_config["type"] == "oauth2_authorization_code"
        assert auth_config["redirect_uri"] == "https://example.com/callback"


class TestCombinedAuthScenarios:
    """Tests for realistic combined authentication scenarios."""

    def test_separate_auth_for_card_and_tasks(self, mock_component):
        """
        Agent can have different authentication for agent card vs tasks.
        """
        agent_config = {
            "name": "test-agent",
            "agent_card_authentication": {
                "type": "static_bearer",
                "token": "card-token"
            },
            "task_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "task-client",
                "client_secret": "task-secret"
            }
        }

        card_auth, card_should_use = mock_component._get_effective_agent_card_auth(agent_config)
        task_auth, task_should_use = mock_component._get_effective_task_auth(agent_config)

        # Agent card uses static bearer
        assert card_should_use is True
        assert card_auth["type"] == "static_bearer"
        assert card_auth["token"] == "card-token"

        # Tasks use OAuth2
        assert task_should_use is True
        assert task_auth["type"] == "oauth2_client_credentials"
        assert task_auth["client_id"] == "task-client"

    def test_agent_card_auth_only(self, mock_component):
        """
        Agent can have authentication only for agent card, not for tasks.
        """
        agent_config = {
            "name": "test-agent",
            "agent_card_authentication": {
                "type": "static_bearer",
                "token": "card-only-token"
            }
        }

        card_auth, card_should_use = mock_component._get_effective_agent_card_auth(agent_config)
        task_auth, task_should_use = mock_component._get_effective_task_auth(agent_config)

        # Agent card uses auth
        assert card_should_use is True
        assert card_auth["token"] == "card-only-token"

        # Tasks have no auth
        assert task_should_use is False
        assert task_auth is None

    def test_task_auth_only(self, mock_component):
        """
        Agent can have authentication only for tasks, not for agent card.
        """
        agent_config = {
            "name": "test-agent",
            "task_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "task-client",
                "client_secret": "task-secret"
            }
        }

        card_auth, card_should_use = mock_component._get_effective_agent_card_auth(agent_config)
        task_auth, task_should_use = mock_component._get_effective_task_auth(agent_config)

        # Agent card has no auth
        assert card_should_use is False
        assert card_auth is None

        # Tasks use OAuth2
        assert task_should_use is True
        assert task_auth["type"] == "oauth2_client_credentials"

    def test_legacy_config_backward_compatibility(self, mock_component):
        """
        Legacy config with authentication and use_auth_for_agent_card
        should work as before.
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "shared-token"
            },
            "use_auth_for_agent_card": True
        }

        card_auth, card_should_use = mock_component._get_effective_agent_card_auth(agent_config)
        task_auth, task_should_use = mock_component._get_effective_task_auth(agent_config)

        # Both use the same legacy auth
        assert card_should_use is True
        assert card_auth["token"] == "shared-token"
        assert task_should_use is True
        assert task_auth["token"] == "shared-token"

    def test_mixed_new_and_legacy_config(self, mock_component):
        """
        When mixing new task_authentication with legacy authentication,
        new field takes precedence for tasks, legacy doesn't apply to card.
        """
        agent_config = {
            "name": "test-agent",
            "authentication": {
                "type": "static_bearer",
                "token": "legacy-token"
            },
            "task_authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "https://auth.example.com/token",
                "client_id": "new-client",
                "client_secret": "new-secret"
            }
        }

        card_auth, card_should_use = mock_component._get_effective_agent_card_auth(agent_config)
        task_auth, task_should_use = mock_component._get_effective_task_auth(agent_config)

        # Agent card has no auth (use_auth_for_agent_card defaults to False)
        assert card_should_use is False
        assert card_auth is None

        # Tasks use new task_authentication
        assert task_should_use is True
        assert task_auth["type"] == "oauth2_client_credentials"
        assert task_auth["client_id"] == "new-client"
