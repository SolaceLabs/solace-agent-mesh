"""
Unit tests for gateway card building functionality.
Tests _build_gateway_card and _detect_gateway_type methods in BaseGatewayComponent.
"""

import pytest
from unittest.mock import MagicMock, patch
from a2a.types import AgentCard

from solace_agent_mesh.common.a2a.utils import is_gateway_card, extract_gateway_info


class TestDetectGatewayType:
    """Test _detect_gateway_type method behavior."""

    def test_returns_configured_gateway_type_when_set(self):
        """Test that configured gateway_type takes precedence."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = "custom_type"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "custom_type"
        mock_component.get_config.assert_called_with("gateway_type")

    def test_detects_http_sse_from_webui_class_name(self):
        """Test detection of http_sse type from WebUI class name."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "WebUIGatewayComponent"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "http_sse"

    def test_detects_http_sse_from_httpsse_class_name(self):
        """Test detection of http_sse type from HttpSse class name."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "HttpSseComponent"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "http_sse"

    def test_detects_rest_from_adapter_name(self):
        """Test detection of rest type from adapter class name."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "GenericGatewayComponent"
        mock_component.adapter = MagicMock()
        mock_component.adapter.__class__.__name__ = "RestAdapter"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "rest"

    def test_detects_slack_from_adapter_name(self):
        """Test detection of slack type from adapter class name."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "GenericGatewayComponent"
        mock_component.adapter = MagicMock()
        mock_component.adapter.__class__.__name__ = "SlackBotAdapter"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "slack"

    def test_detects_teams_from_adapter_name(self):
        """Test detection of teams type from adapter class name."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "GenericGatewayComponent"
        mock_component.adapter = MagicMock()
        mock_component.adapter.__class__.__name__ = "MicrosoftTeamsAdapter"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "teams"

    def test_returns_generic_when_no_match(self):
        """Test fallback to 'generic' when no patterns match."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "UnknownComponent"
        mock_component.adapter = None

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "generic"

    def test_returns_generic_when_adapter_has_no_matching_name(self):
        """Test fallback to generic when adapter name doesn't match patterns."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = None
        mock_component.__class__.__name__ = "GenericGatewayComponent"
        mock_component.adapter = MagicMock()
        mock_component.adapter.__class__.__name__ = "CustomAdapter"

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        result = BaseGatewayComponent._detect_gateway_type(mock_component)

        assert result == "generic"


class TestBuildGatewayCard:
    """Test _build_gateway_card method behavior."""

    def _create_mock_component(self, gateway_id, namespace, gateway_type, deployment=None, card_config=None):
        """Helper to create properly configured mock component."""
        mock_component = MagicMock()
        mock_component.gateway_id = gateway_id
        mock_component.namespace = namespace
        mock_component._gateway_card_config = card_config or {}
        mock_component._detect_gateway_type = MagicMock(return_value=gateway_type)
        mock_component.get_config.side_effect = lambda key, default=None: {
            "gateway_type": gateway_type,
            "deployment": deployment,
        }.get(key, default)
        return mock_component

    def test_builds_valid_gateway_card(self):
        """Test that _build_gateway_card creates a valid AgentCard."""
        mock_component = self._create_mock_component(
            gateway_id="test-gateway-001",
            namespace="test/namespace",
            gateway_type="http_sse"
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert isinstance(card, AgentCard)
        assert card.name == "test-gateway-001"
        assert "test/namespace" in card.url
        assert card.url == "solace:test/namespace/a2a/v1/gateway/request/test-gateway-001"

    def test_gateway_card_has_gateway_role_extension(self):
        """Test that built card includes gateway-role extension."""
        mock_component = self._create_mock_component(
            gateway_id="my-gateway",
            namespace="prod/sam",
            gateway_type="http_sse"
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert is_gateway_card(card) is True

        info = extract_gateway_info(card)
        assert info is not None
        assert info["gateway_id"] == "my-gateway"
        assert info["gateway_type"] == "http_sse"
        assert info["namespace"] == "prod/sam"

    def test_gateway_card_includes_deployment_extension_when_configured(self):
        """Test that deployment extension is added when deployment.id is configured."""
        mock_component = self._create_mock_component(
            gateway_id="deployed-gateway",
            namespace="test/sam",
            gateway_type="http_sse",
            deployment={"id": "k8s-pod-abc123"}
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        info = extract_gateway_info(card)
        assert info is not None
        assert info.get("deployment_id") == "k8s-pod-abc123"

    def test_gateway_card_uses_custom_description(self):
        """Test that custom description from config is used."""
        mock_component = self._create_mock_component(
            gateway_id="custom-gw",
            namespace="test/sam",
            gateway_type="http_sse",
            card_config={"description": "My Custom Gateway Description"}
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert card.description == "My Custom Gateway Description"

    def test_gateway_card_uses_default_description(self):
        """Test that default description is generated from gateway type."""
        mock_component = self._create_mock_component(
            gateway_id="default-gw",
            namespace="test/sam",
            gateway_type="slack"
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert card.description == "SLACK Gateway"

    def test_gateway_card_has_capabilities(self):
        """Test that gateway card has capabilities set."""
        mock_component = self._create_mock_component(
            gateway_id="capabilities-gw",
            namespace="test/sam",
            gateway_type="http_sse"
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert card.capabilities is not None
        assert card.capabilities.extensions is not None
        assert len(card.capabilities.extensions) >= 1

    def test_gateway_card_uses_custom_input_output_modes(self):
        """Test that custom input/output modes are used from config."""
        mock_component = self._create_mock_component(
            gateway_id="custom-modes-gw",
            namespace="test/sam",
            gateway_type="http_sse",
            card_config={
                "defaultInputModes": ["text", "image"],
                "defaultOutputModes": ["text", "markdown"],
            }
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert card.default_input_modes == ["text", "image"]
        assert card.default_output_modes == ["text", "markdown"]


class TestGatewayCardIntegration:
    """Integration tests ensuring built cards work with registry and utils."""

    def _create_mock_component(self, gateway_id, namespace, gateway_type, deployment=None, card_config=None):
        """Helper to create properly configured mock component."""
        mock_component = MagicMock()
        mock_component.gateway_id = gateway_id
        mock_component.namespace = namespace
        mock_component._gateway_card_config = card_config or {}
        mock_component._detect_gateway_type = MagicMock(return_value=gateway_type)
        mock_component.get_config.side_effect = lambda key, default=None: {
            "gateway_type": gateway_type,
            "deployment": deployment,
        }.get(key, default)
        return mock_component

    def test_built_card_can_be_added_to_registry(self):
        """Test that built gateway card can be stored in GatewayRegistry."""
        from solace_agent_mesh.common.gateway_registry import GatewayRegistry

        mock_component = self._create_mock_component(
            gateway_id="registry-test-gw",
            namespace="test/sam",
            gateway_type="http_sse",
            deployment={"id": "pod-123"}
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        registry = GatewayRegistry()
        is_new = registry.add_or_update_gateway(card)

        assert is_new is True
        assert "registry-test-gw" in registry.get_gateway_ids()

        stored_card = registry.get_gateway("registry-test-gw")
        assert stored_card.name == card.name
        assert registry.get_gateway_type("registry-test-gw") == "http_sse"
        assert registry.get_deployment_id("registry-test-gw") == "pod-123"

    def test_built_card_is_identified_as_gateway_card(self):
        """Test that is_gateway_card() correctly identifies built cards."""
        mock_component = self._create_mock_component(
            gateway_id="identification-test-gw",
            namespace="test/sam",
            gateway_type="rest"
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        assert is_gateway_card(card) is True

    def test_built_card_metadata_extraction(self):
        """Test that extract_gateway_info() extracts correct metadata."""
        mock_component = self._create_mock_component(
            gateway_id="metadata-test-gw",
            namespace="production/sam",
            gateway_type="teams",
            deployment={"id": "aks-deployment-xyz"}
        )

        from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

        card = BaseGatewayComponent._build_gateway_card(mock_component)

        info = extract_gateway_info(card)

        assert info["gateway_id"] == "metadata-test-gw"
        assert info["gateway_type"] == "teams"
        assert info["namespace"] == "production/sam"
        assert info["deployment_id"] == "aks-deployment-xyz"
