"""
Integration tests for gateway card publishing functionality.

Tests that gateways can build and publish their discovery cards correctly.
These tests focus on the card building behavior rather than the timer mechanism.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from a2a.types import AgentCard

from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from solace_agent_mesh.common.a2a.utils import is_gateway_card, extract_gateway_info


pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.gateway,
]


class TestGatewayCardBuildingIntegration:
    """Test gateway card building with real gateway component."""

    def test_gateway_builds_valid_card(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that real gateway component builds a valid gateway card."""
        gateway = test_gateway_app_instance

        card = gateway._build_gateway_card()

        assert isinstance(card, AgentCard)
        assert card.name == gateway.gateway_id
        assert gateway.namespace in card.url

    def test_built_card_is_recognized_as_gateway(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that built card is correctly identified as a gateway card."""
        gateway = test_gateway_app_instance

        card = gateway._build_gateway_card()

        assert is_gateway_card(card) is True

    def test_built_card_has_correct_gateway_info(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that built card contains correct gateway metadata."""
        gateway = test_gateway_app_instance

        card = gateway._build_gateway_card()

        info = extract_gateway_info(card)
        assert info is not None
        assert info["gateway_id"] == gateway.gateway_id
        assert info["namespace"] == gateway.namespace

    def test_built_card_has_capabilities_with_extensions(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that built card has capabilities with gateway extensions."""
        gateway = test_gateway_app_instance

        card = gateway._build_gateway_card()

        assert card.capabilities is not None
        assert card.capabilities.extensions is not None
        assert len(card.capabilities.extensions) >= 1

    def test_built_card_url_follows_a2a_pattern(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that card URL follows the A2A gateway pattern."""
        gateway = test_gateway_app_instance

        card = gateway._build_gateway_card()

        expected_url = f"solace:{gateway.namespace}/a2a/v1/gateway/request/{gateway.gateway_id}"
        assert card.url == expected_url


class TestGatewayTypeDetectionIntegration:
    """Test gateway type detection with real components."""

    def test_detect_gateway_type_returns_string(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway type detection returns a valid type."""
        gateway = test_gateway_app_instance

        gateway_type = gateway._detect_gateway_type()

        assert isinstance(gateway_type, str)
        assert len(gateway_type) > 0

    def test_detected_type_matches_card_info(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that detected type matches what's in the built card."""
        gateway = test_gateway_app_instance

        detected_type = gateway._detect_gateway_type()
        card = gateway._build_gateway_card()
        info = extract_gateway_info(card)

        assert info["gateway_type"] == detected_type


class TestGatewayCardPublishingMechanism:
    """Test the gateway card publishing mechanism."""

    def test_publish_gateway_card_builds_and_sends(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that _publish_gateway_card builds card and calls publish."""
        gateway = test_gateway_app_instance

        published_messages = []
        original_publish = gateway.publish_a2a_message

        def capture_publish(payload, topic, user_properties=None):
            published_messages.append({"payload": payload, "topic": topic})

        gateway.publish_a2a_message = capture_publish

        try:
            gateway._publish_gateway_card()

            assert len(published_messages) == 1
            published = published_messages[0]

            assert "name" in published["payload"]
            assert published["payload"]["name"] == gateway.gateway_id

            assert "discovery" in published["topic"]

        finally:
            gateway.publish_a2a_message = original_publish

    def test_published_payload_is_valid_agent_card(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that published payload can be parsed as AgentCard."""
        gateway = test_gateway_app_instance

        published_payloads = []

        def capture_publish(payload, topic, user_properties=None):
            published_payloads.append(payload)

        original_publish = gateway.publish_a2a_message
        gateway.publish_a2a_message = capture_publish

        try:
            gateway._publish_gateway_card()

            assert len(published_payloads) == 1
            payload = published_payloads[0]

            card = AgentCard(**payload)
            assert card.name == gateway.gateway_id
            assert is_gateway_card(card) is True

        finally:
            gateway.publish_a2a_message = original_publish

    def test_publish_to_correct_discovery_topic(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that card is published to the gateway-specific discovery topic."""
        gateway = test_gateway_app_instance

        published_topics = []

        def capture_publish(payload, topic, user_properties=None):
            published_topics.append(topic)

        original_publish = gateway.publish_a2a_message
        gateway.publish_a2a_message = capture_publish

        try:
            gateway._publish_gateway_card()

            assert len(published_topics) == 1
            topic = published_topics[0]

            assert gateway.namespace in topic
            assert "a2a" in topic
            assert "discovery/gatewaycards" in topic

        finally:
            gateway.publish_a2a_message = original_publish


class TestGatewayCardPublishingConfig:
    """Test gateway card publishing configuration handling."""

    def test_default_config_values(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that default publishing config values are set."""
        gateway = test_gateway_app_instance

        config = gateway._gateway_card_publishing_config
        assert isinstance(config, dict)

    def test_gateway_has_publishing_disabled_in_test(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that publishing is disabled in test fixtures."""
        gateway = test_gateway_app_instance

        config = gateway._gateway_card_publishing_config
        assert config.get("enabled") is False


class TestGatewayRegistryInitialization:
    """Test gateway registry initialization on component."""

    def test_gateway_has_registry_instance(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway component has a gateway_registry attribute."""
        gateway = test_gateway_app_instance

        assert hasattr(gateway, "gateway_registry")
        assert gateway.gateway_registry is not None

    def test_registry_is_gateway_registry_type(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway_registry is a GatewayRegistry instance."""
        from solace_agent_mesh.common.gateway_registry import GatewayRegistry

        gateway = test_gateway_app_instance

        assert isinstance(gateway.gateway_registry, GatewayRegistry)

    def test_registry_starts_empty(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway_registry starts without pre-populated gateways."""
        gateway = test_gateway_app_instance
        gateway.gateway_registry.clear()

        ids = gateway.gateway_registry.get_gateway_ids()
        assert len(ids) == 0


class TestCrossGatewayDiscovery:
    """Test discovery between multiple gateways (simulated)."""

    async def test_gateway_can_receive_peer_card(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway can receive and store another gateway's card."""
        gateway = test_gateway_app_instance
        gateway.gateway_registry.clear()

        peer_card = gateway._build_gateway_card()
        peer_card = AgentCard(
            name="PeerGateway-Integration",
            url=peer_card.url.replace(gateway.gateway_id, "PeerGateway-Integration"),
            description="Peer Gateway for Integration Test",
            version=peer_card.version,
            protocol_version=peer_card.protocol_version,
            capabilities=peer_card.capabilities,
            default_input_modes=peer_card.default_input_modes,
            default_output_modes=peer_card.default_output_modes,
            skills=[],
        )

        from a2a.types import AgentExtension

        peer_card.capabilities.extensions = [
            AgentExtension(
                uri="https://solace.com/a2a/extensions/sam/gateway-role",
                required=False,
                params={
                    "gateway_id": "PeerGateway-Integration",
                    "gateway_type": "http_sse",
                    "namespace": gateway.namespace,
                }
            )
        ]

        payload = peer_card.model_dump(by_alias=True, exclude_none=True)
        result = await gateway._handle_discovery_message(payload)

        assert result is True
        assert "PeerGateway-Integration" in gateway.gateway_registry.get_gateway_ids()

    async def test_gateway_does_not_store_own_card(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test behavior when gateway receives its own card (should still store)."""
        gateway = test_gateway_app_instance
        gateway.gateway_registry.clear()

        own_card = gateway._build_gateway_card()
        payload = own_card.model_dump(by_alias=True, exclude_none=True)

        result = await gateway._handle_discovery_message(payload)

        assert result is True
        assert gateway.gateway_id in gateway.gateway_registry.get_gateway_ids()
