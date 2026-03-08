"""Unit tests for static agent card construction in A2AProxyComponent.

Tests cover:
- Security scheme construction from authentication config
- Synthetic agent card construction from agent_card_data
- Integration with all supported authentication types
"""

from unittest.mock import MagicMock, patch

from a2a.types import AgentCard


class TestConstructSecuritySchemesFromAuth:
    """Test _construct_security_schemes_from_auth() method."""

    def test_static_bearer_auth(self):
        """Test security scheme construction for static bearer token."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "type": "static_bearer",
            "token": "test-token-123",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "Static bearer token authentication",
            }
        }
        assert security == [{"bearer": []}]

    def test_static_apikey_auth(self):
        """Test security scheme construction for static API key."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "type": "static_apikey",
            "token": "test-api-key-456",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "apikey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key authentication via X-API-Key header",
            }
        }
        assert security == [{"apikey": []}]

    def test_oauth2_client_credentials_with_scopes(self):
        """Test OAuth2 client credentials with scopes."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "type": "oauth2_client_credentials",
            "token_url": "https://auth.example.com/token",
            "client_id": "my-client-id",
            "client_secret": "my-secret",
            "scope": "read write admin",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "oauth2ClientCredentials": {
                "type": "oauth2",
                "description": "OAuth 2.0 client credentials flow",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.com/token",
                        "scopes": {
                            "read": "",
                            "write": "",
                            "admin": "",
                        }
                    }
                },
            }
        }
        assert security == [{"oauth2ClientCredentials": ["read", "write", "admin"]}]

    def test_oauth2_client_credentials_no_scopes(self):
        """Test OAuth2 client credentials without scopes."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "type": "oauth2_client_credentials",
            "token_url": "https://auth.example.com/token",
            "client_id": "my-client-id",
            "client_secret": "my-secret",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "oauth2ClientCredentials": {
                "type": "oauth2",
                "description": "OAuth 2.0 client credentials flow",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.com/token",
                        "scopes": {}
                    }
                },
            }
        }
        assert security == [{"oauth2ClientCredentials": []}]

    def test_legacy_scheme_bearer(self):
        """Test backward compatibility with legacy 'scheme' field for bearer."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "scheme": "bearer",  # Legacy field
            "token": "test-token",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "Static bearer token authentication",
            }
        }
        assert security == [{"bearer": []}]

    def test_legacy_scheme_apikey(self):
        """Test backward compatibility with legacy 'scheme' field for apikey."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        auth_config = {
            "scheme": "apikey",  # Legacy field
            "token": "test-api-key",
        }

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, auth_config
        )

        assert security_schemes == {
            "apikey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key authentication via X-API-Key header",
            }
        }
        assert security == [{"apikey": []}]

    def test_no_auth_config(self):
        """Test when auth_config is None."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, None
        )

        assert security_schemes is None
        assert security is None

    def test_empty_auth_config(self):
        """Test when auth_config is empty dict."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        security_schemes, security = A2AProxyComponent._construct_security_schemes_from_auth(
            component, {}
        )

        assert security_schemes is None
        assert security is None


class TestConstructSyntheticAgentCard:
    """Test _construct_synthetic_agent_card() method."""

    @staticmethod
    def _create_component():
        """Helper to create a minimal component instance for testing."""
        from solace_agent_mesh.agent.proxies.a2a.component import (
            A2AProxyComponent,
        )

        component = A2AProxyComponent.__new__(A2AProxyComponent)
        component.log_identifier = "[Test]"
        return component

    def test_basic_card_construction_no_auth(self):
        """Test constructing a basic synthetic agent card without authentication."""
        component = self._create_component()

        agent_config = {
            "name": "TestAgent",
            "url": "http://example.com:9000",
            "agent_card_data": {
                "name": "TestAgent",
                "description": "A test agent",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [
                    {
                        "id": "test_skill",
                        "name": "Test Skill",
                        "description": "Does testing",
                        "tags": ["test"]
                    }
                ],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert isinstance(result, AgentCard)
        assert result.name == "TestAgent"
        assert result.description == "A test agent"
        assert result.version == "1.0.0"
        assert result.url == "http://example.com:9000"
        assert result.preferred_transport == "JSONRPC"
        assert result.protocol_version == "0.3.0"
        assert len(result.skills) == 1
        assert result.skills[0].id == "test_skill"
        assert result.security_schemes is None  # No auth configured

    def test_card_with_bearer_auth(self):
        """Test constructing card with static bearer authentication."""
        component = self._create_component()

        agent_config = {
            "name": "SecureAgent",
            "url": "https://secure.example.com",
            "agent_card_data": {
                "name": "SecureAgent",
                "description": "Secure test agent",
                "version": "2.0.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
            },
            "authentication": {
                "type": "static_bearer",
                "token": "secret-token-123"
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.name == "SecureAgent"
        assert result.url == "https://secure.example.com"
        assert result.security_schemes is not None
        assert "bearer" in result.security_schemes
        assert result.security_schemes["bearer"].root.type == "http"
        assert result.security_schemes["bearer"].root.scheme == "bearer"
        assert result.security is not None
        assert result.security == [{"bearer": []}]

    def test_card_with_oauth2_client_credentials(self):
        """Test constructing card with OAuth2 client credentials."""
        component = self._create_component()

        agent_config = {
            "name": "OAuth2Agent",
            "url": "http://example.com:9000",
            "agent_card_data": {
                "name": "AdditionAgent",
                "description": "Adds numbers",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [
                    {
                        "id": "add",
                        "name": "add_numbers",
                        "description": "Adds two numbers",
                        "tags": ["math"]
                    }
                ],
                "defaultInputModes": ["text", "application/json"],
                "defaultOutputModes": ["text"],
            },
            "authentication": {
                "type": "oauth2_client_credentials",
                "token_url": "http://example.com:9000/token",
                "client_id": "my-client-id",
                "client_secret": "my-secret",
                "scope": "read write"
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.name == "AdditionAgent"
        assert result.url == "http://example.com:9000"
        assert result.security_schemes is not None
        assert "oauth2ClientCredentials" in result.security_schemes

        # Verify OAuth2 flow structure
        oauth2_scheme = result.security_schemes["oauth2ClientCredentials"].root
        assert oauth2_scheme.type == "oauth2"
        assert oauth2_scheme.flows.client_credentials is not None
        assert (
            oauth2_scheme.flows.client_credentials.token_url
            == "http://example.com:9000/token"
        )
        assert oauth2_scheme.flows.client_credentials.scopes == {
            "read": "",
            "write": "",
        }

        # Verify security array
        assert result.security == [
            {"oauth2ClientCredentials": ["read", "write"]}
        ]

    def test_card_preserves_existing_protocol_fields(self):
        """Test that existing protocol fields in card_data are preserved."""
        component = self._create_component()

        agent_config = {
            "name": "CustomAgent",
            "url": "http://custom.example.com",
            "agent_card_data": {
                "name": "CustomAgent",
                "description": "Custom protocol agent",
                "version": "3.0.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "preferredTransport": "SSE",  # Custom transport
                "protocolVersion": "0.4.0",   # Custom version
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.preferred_transport == "SSE"  # Preserved
        assert result.protocol_version == "0.4.0"  # Preserved

    def test_card_with_apikey_auth(self):
        """Test constructing card with static API key authentication."""
        component = self._create_component()

        agent_config = {
            "name": "ApiKeyAgent",
            "url": "https://api.example.com",
            "agent_card_data": {
                "name": "ApiKeyAgent",
                "description": "API key secured agent",
                "version": "1.5.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
            },
            "authentication": {
                "type": "static_apikey",
                "token": "my-api-key-789"
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.security_schemes is not None
        assert "apikey" in result.security_schemes

        apikey_scheme = result.security_schemes["apikey"].root
        assert apikey_scheme.type == "apiKey"
        assert apikey_scheme.in_ == "header"
        assert apikey_scheme.name == "X-API-Key"
        assert result.security == [{"apikey": []}]

    def test_card_with_complex_skills(self):
        """Test card construction preserves complex skill definitions."""
        component = self._create_component()

        agent_config = {
            "name": "MathAgent",
            "url": "http://math.example.com",
            "agent_card_data": {
                "name": "MathAgent",
                "description": "Math operations agent",
                "version": "2.0.0",
                "capabilities": {},
                "skills": [
                    {
                        "id": "add",
                        "name": "add_numbers",
                        "description": "Adds numbers",
                        "tags": ["math", "arithmetic"]
                    },
                    {
                        "id": "multiply",
                        "name": "multiply_numbers",
                        "description": "Multiplies numbers",
                        "tags": ["math", "arithmetic"]
                    }
                ],
                "defaultInputModes": ["text", "application/json"],
                "defaultOutputModes": ["text", "application/json"],
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert len(result.skills) == 2
        assert result.skills[0].id == "add"
        assert result.skills[1].id == "multiply"
        assert result.default_input_modes == ["text", "application/json"]
        assert result.default_output_modes == ["text", "application/json"]

    def test_no_agent_card_data_returns_none(self):
        """Test that None is returned when agent_card_data is missing."""
        component = self._create_component()

        agent_config = {
            "name": "RemoteAgent",
            "url": "http://remote.example.com",
            # No agent_card_data field
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is None

    @patch("solace_agent_mesh.agent.proxies.a2a.component.log")
    def test_invalid_card_data_returns_none(self, mock_log):
        """Test that invalid card_data causes None return with error logging."""
        component = self._create_component()

        agent_config = {
            "name": "InvalidAgent",
            "url": "http://invalid.example.com",
            "agent_card_data": {
                # Missing required fields like name, skills, etc.
                "invalid_field": "invalid_value"
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is None
        # Verify error was logged
        assert mock_log.exception.called

    def test_card_with_capabilities(self):
        """Test that capabilities from card_data are preserved."""
        component = self._create_component()

        agent_config = {
            "name": "StreamingAgent",
            "url": "http://streaming.example.com",
            "agent_card_data": {
                "name": "StreamingAgent",
                "description": "Streaming capable agent",
                "version": "1.0.0",
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "capabilities": {
                    "streaming": True,
                }
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.capabilities is not None

    def test_complete_oauth2_example_from_yaml(self):
        """Test the complete example from the YAML documentation."""
        component = self._create_component()

        # Example from user's YAML
        agent_config = {
            "name": "remote_agent_abcdef12_3456_7890_abcd_ef1234567890",
            "url": "http://example.com:9000/",
            "request_timeout_seconds": 120,
            "agent_card_data": {
                "name": "AdditionAgent",
                "description": "A simple agent that can add two numbers together",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [
                    {
                        "id": "add_numbers",
                        "name": "add_numbers",
                        "description": "Adds two numbers and returns the result",
                        "tags": ["math", "calculator"]
                    },
                    {
                        "id": "multiply_numbers",
                        "name": "multiply_numbers",
                        "description": "Multiplies two numbers",
                        "tags": ["math"]
                    }
                ],
                "defaultInputModes": ["text", "application/json"],
                "defaultOutputModes": ["text", "application/json"]
            },
            "authentication": {
                "type": "oauth2_client_credentials",
                "client_id": "my-client-id-12345",
                "client_secret": "my-secret-xyz789",
                "token_url": "http://example.com:9000/token",
                "scope": "read write"
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        # Verify all expected fields
        assert result is not None
        assert result.name == "AdditionAgent"
        assert (
            result.description
            == "A simple agent that can add two numbers together"
        )
        assert result.version == "1.0.0"
        assert result.url == "http://example.com:9000/"
        assert result.preferred_transport == "JSONRPC"
        assert result.protocol_version == "0.3.0"

        # Verify skills
        assert len(result.skills) == 2
        assert result.skills[0].id == "add_numbers"
        assert result.skills[1].id == "multiply_numbers"

        # Verify modes
        assert result.default_input_modes == ["text", "application/json"]
        assert result.default_output_modes == ["text", "application/json"]

        # Verify security
        assert result.security_schemes is not None
        assert "oauth2ClientCredentials" in result.security_schemes
        oauth2_scheme = result.security_schemes["oauth2ClientCredentials"].root
        assert (
            oauth2_scheme.flows.client_credentials.token_url
            == "http://example.com:9000/token"
        )
        assert oauth2_scheme.flows.client_credentials.scopes == {
            "read": "",
            "write": "",
        }
        assert result.security == [
            {"oauth2ClientCredentials": ["read", "write"]}
        ]

    def test_url_added_to_card_data(self):
        """Test that URL is correctly added from config to card data."""
        component = self._create_component()

        agent_config = {
            "name": "UrlTest",
            "url": "http://myurl.example.com:8080",
            "agent_card_data": {
                "name": "UrlTest",
                "description": "URL test",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                # Note: no "url" field in card_data
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        assert result.url == "http://myurl.example.com:8080"

    def test_protocol_defaults_only_added_if_missing(self):
        """Test defaults are only added when not present in card_data."""
        component = self._create_component()

        agent_config = {
            "name": "DefaultTest",
            "url": "http://example.com",
            "agent_card_data": {
                "name": "DefaultTest",
                "description": "Testing defaults",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                # No preferredTransport or protocolVersion
            }
        }

        result = component._construct_synthetic_agent_card(agent_config)

        assert result is not None
        # Defaults should be added
        assert result.preferred_transport == "JSONRPC"
        assert result.protocol_version == "0.3.0"


class TestStaticAgentCardIntegration:
    """Integration tests for static agent card handling in discovery."""

    def test_static_agents_skip_url_fetch(self):
        """Test that agents with agent_card_data skip URL-based discovery."""
        # This would be an integration test that verifies _initial_discovery_sync
        # calls _construct_synthetic_agent_card instead of fetching from URL
        # Marking as placeholder for now
        pass

    def test_static_agents_skip_polling(self):
        """Test that agents with agent_card_data are skipped during polling."""
        # This would test that _discover_and_publish_agents skips the fetch
        # for static agents but still publishes them
        # Marking as placeholder for now
        pass
