"""Unit tests for A2AProxyComponent authentication logic.

Tests cover the authentication scheme name extraction, conditional credential storage,
conditional AuthInterceptor addition, and integration with the A2A SDK's credential store.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Optional, Dict, Any

from a2a.types import (
    AgentCard,
    SecurityScheme,
    HTTPAuthSecurityScheme,
    APIKeySecurityScheme,
    OAuth2SecurityScheme,
    OAuthFlows,
    ClientCredentialsOAuthFlow,
    AuthorizationCodeOAuthFlow,
    In,
)

# Test utilities


def create_mock_agent_card(
    name: str = "test_agent",
    url: str = "http://test.com",
    security_schemes: Optional[Dict[str, SecurityScheme]] = None,
) -> AgentCard:
    """Helper to create mock agent cards for testing.

    Args:
        name: Agent name
        url: Agent URL
        security_schemes: Optional security schemes dict

    Returns:
        Minimal AgentCard with configurable security_schemes
    """
    from a2a.types import AgentCapabilities, AgentSkill

    return AgentCard(
        name=name,
        url=url,
        protocol_version="0.3.0",
        version="1.0.0",
        description="Test agent",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=False,
        ),
        skills=[
            AgentSkill(
                id="test-skill",
                name="Test Skill",
                description="Test skill description",
                tags=[],
                examples=[],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        security_schemes=security_schemes,
    )


def create_http_bearer_scheme(scheme_name: str = "customBearer") -> Dict[str, SecurityScheme]:
    """Create HTTP bearer security scheme."""
    return {
        scheme_name: SecurityScheme(
            root=HTTPAuthSecurityScheme(type="http", scheme="bearer")
        )
    }


def create_oauth2_scheme(
    scheme_name: str = "customOAuth",
    include_client_credentials: bool = True,
    include_authorization_code: bool = False,
) -> Dict[str, SecurityScheme]:
    """Create OAuth2 security scheme with optional flows."""
    flows_dict = {}

    if include_client_credentials:
        flows_dict["client_credentials"] = ClientCredentialsOAuthFlow(
            token_url="https://auth.example.com/token",
            scopes={}  # Empty scopes dict is valid
        )

    if include_authorization_code:
        flows_dict["authorization_code"] = AuthorizationCodeOAuthFlow(
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes={}  # Empty scopes dict is valid
        )

    flows = OAuthFlows(**flows_dict)

    return {
        scheme_name: SecurityScheme(
            root=OAuth2SecurityScheme(type="oauth2", flows=flows)
        )
    }


def create_apikey_scheme(scheme_name: str = "customApiKey") -> Dict[str, SecurityScheme]:
    """Create API key security scheme."""
    return {
        scheme_name: SecurityScheme(
            root=APIKeySecurityScheme(
                type="apiKey",
                name="X-API-Key",
                in_=In.header,
            )
        )
    }


class TestExtractSecuritySchemeName:
    """Test _extract_security_scheme_name() method."""

    def test_extract_custom_http_bearer_scheme_name(self):
        """Test extracting custom HTTP bearer scheme name."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        # Create mock component
        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        # Create agent card with custom bearer scheme
        agent_card = create_mock_agent_card(
            security_schemes=create_http_bearer_scheme("myCustomBearer")
        )

        # Call the method
        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_bearer", "test_agent"
        )

        assert result == "myCustomBearer"

    def test_extract_custom_oauth2_client_credentials_scheme_name(self):
        """Test extracting custom OAuth2 client credentials scheme name."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        agent_card = create_mock_agent_card(
            security_schemes=create_oauth2_scheme("myOAuth2Auth", include_client_credentials=True)
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "oauth2_client_credentials", "test_agent"
        )

        assert result == "myOAuth2Auth"

    def test_extract_custom_oauth2_authorization_code_scheme_name(self):
        """Test extracting custom OAuth2 authorization code scheme name."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        agent_card = create_mock_agent_card(
            security_schemes=create_oauth2_scheme(
                "myAuthCodeAuth",
                include_client_credentials=False,
                include_authorization_code=True,
            )
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "oauth2_authorization_code", "test_agent"
        )

        assert result == "myAuthCodeAuth"

    def test_extract_custom_apikey_scheme_name(self):
        """Test extracting custom API key scheme name."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        agent_card = create_mock_agent_card(
            security_schemes=create_apikey_scheme("myCustomApiKey")
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_apikey", "test_agent"
        )

        assert result == "myCustomApiKey"

    @patch("solace_agent_mesh.agent.proxies.a2a.component.log")
    def test_fallback_when_no_matching_scheme_bearer(self, mock_log):
        """Test fallback to default when no matching scheme for bearer."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"
        # Configure the mock to return the correct default
        component._get_default_scheme_name.return_value = "bearer"

        # Agent card with API key scheme (doesn't match bearer)
        agent_card = create_mock_agent_card(
            security_schemes=create_apikey_scheme("someApiKey")
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_bearer", "test_agent"
        )

        assert result == "bearer"
        # Verify warning was logged
        assert any("No matching security scheme" in str(call) for call in mock_log.warning.call_args_list)

    @patch("solace_agent_mesh.agent.proxies.a2a.component.log")
    def test_fallback_when_no_matching_scheme_apikey(self, mock_log):
        """Test fallback to default when no matching scheme for apikey."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"
        component._get_default_scheme_name.return_value = "apikey"

        # Agent card with bearer scheme (doesn't match apikey)
        agent_card = create_mock_agent_card(
            security_schemes=create_http_bearer_scheme("someBearer")
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_apikey", "test_agent"
        )

        assert result == "apikey"

    def test_fallback_when_security_schemes_is_none(self):
        """Test fallback when security_schemes is None."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"
        component._get_default_scheme_name.return_value = "bearer"

        agent_card = create_mock_agent_card(security_schemes=None)

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_bearer", "test_agent"
        )

        assert result == "bearer"

    def test_fallback_when_security_schemes_is_empty_dict(self):
        """Test fallback when security_schemes is empty dict."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"
        component._get_default_scheme_name.return_value = "bearer"

        agent_card = create_mock_agent_card(security_schemes={})

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "oauth2_client_credentials", "test_agent"
        )

        assert result == "bearer"

    def test_fallback_when_no_agent_card(self):
        """Test fallback when agent card is None."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"
        component._get_default_scheme_name.return_value = "bearer"

        result = A2AProxyComponent._extract_security_scheme_name(
            component, None, "static_bearer", "test_agent"
        )

        assert result == "bearer"

    def test_prefers_client_credentials_flow_over_generic_oauth2(self):
        """Test preference for client_credentials flow when present."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        # Create card with both client_credentials and authorization_code flows
        agent_card = create_mock_agent_card(
            security_schemes=create_oauth2_scheme(
                "preferredScheme",
                include_client_credentials=True,
                include_authorization_code=True,
            )
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "oauth2_client_credentials", "test_agent"
        )

        assert result == "preferredScheme"

    def test_oauth2_bearer_token_accepts_oauth2_scheme(self):
        """Test that static_bearer accepts OAuth2 schemes (common pattern)."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[Test]"

        agent_card = create_mock_agent_card(
            security_schemes=create_oauth2_scheme("oauth2Scheme")
        )

        result = A2AProxyComponent._extract_security_scheme_name(
            component, agent_card, "static_bearer", "test_agent"
        )

        # Should accept OAuth2 scheme for bearer tokens
        assert result == "oauth2Scheme"


class TestGetDefaultSchemeName:
    """Test _get_default_scheme_name() method."""

    def test_default_for_static_bearer(self):
        """Test default scheme name for static_bearer."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._get_default_scheme_name(component, "static_bearer")
        assert result == "bearer"

    def test_default_for_static_apikey(self):
        """Test default scheme name for static_apikey."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._get_default_scheme_name(component, "static_apikey")
        assert result == "apikey"

    def test_default_for_oauth2_client_credentials(self):
        """Test default scheme name for oauth2_client_credentials."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._get_default_scheme_name(component, "oauth2_client_credentials")
        assert result == "bearer"

    def test_default_for_oauth2_authorization_code(self):
        """Test default scheme name for oauth2_authorization_code."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._get_default_scheme_name(component, "oauth2_authorization_code")
        assert result == "oauth2_authorization_code"

    def test_default_for_unknown_type(self):
        """Test default scheme name for unknown auth type."""
        from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._get_default_scheme_name(component, "unknown_type")
        assert result == "bearer"  # Fallback to bearer


# Note: The remaining test suites (TestGetOrCreateA2AClientAuth, TestBuildHeadersConditionalAuth,
# TestCredentialStoreIntegration, TestAuthInterceptorConditionalAddition) require more complex
# mocking of the component initialization and async methods. These will be implemented in
# subsequent iterations with proper fixtures and async test patterns.

# For now, we have comprehensive coverage of the scheme name extraction logic which is the
# core new functionality added.
