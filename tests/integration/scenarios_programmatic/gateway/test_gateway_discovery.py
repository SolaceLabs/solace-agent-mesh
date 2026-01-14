"""
Integration tests for gateway discovery functionality.

Tests the behavior of gateway card publishing, discovery message routing,
and gateway registry management in real gateway components.
"""

import pytest
import asyncio
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentExtension

from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from solace_agent_mesh.common.a2a.utils import is_gateway_card, extract_gateway_info
from solace_agent_mesh.common.gateway_registry import GatewayRegistry


pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.gateway,
]


def create_test_gateway_card(
    gateway_id: str,
    gateway_type: str = "http_sse",
    namespace: str = "test_namespace",
    deployment_id: str = None,
) -> AgentCard:
    """Create a test gateway card for discovery tests."""
    extensions = [
        AgentExtension(
            uri="https://solace.com/a2a/extensions/sam/gateway-role",
            required=False,
            params={
                "gateway_id": gateway_id,
                "gateway_type": gateway_type,
                "namespace": namespace,
            }
        )
    ]

    if deployment_id:
        extensions.append(
            AgentExtension(
                uri="https://solace.com/a2a/extensions/sam/deployment",
                required=False,
                params={"deployment_id": deployment_id}
            )
        )

    return AgentCard(
        name=gateway_id,
        url=f"solace:{namespace}/a2a/v1/gateway/request/{gateway_id}",
        description=f"{gateway_type.upper()} Gateway",
        version="1.0.0",
        protocol_version="1.0",
        capabilities=AgentCapabilities(
            supports_streaming=True,
            supports_cancellation=True,
            extensions=extensions,
        ),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[],
    )


def create_test_agent_card(agent_name: str) -> AgentCard:
    """Create a test agent card (non-gateway) for discovery tests."""
    return AgentCard(
        name=agent_name,
        description="A test agent for discovery",
        url="https://test.example.com",
        version="1.0.0",
        protocol_version="0.3.0",
        capabilities=AgentCapabilities(
            supports_streaming=True,
            supports_cancellation=False,
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="test-skill",
                name="Test Skill",
                description="A test skill",
                tags=["test"],
            )
        ],
    )


class TestDiscoveryMessageRouting:
    """Test that discovery messages are routed to the correct registry."""

    async def test_gateway_card_routed_to_gateway_registry(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway cards are stored in gateway_registry."""
        gateway = test_gateway_app_instance

        peer_gateway_card = create_test_gateway_card(
            gateway_id="PeerGateway-001",
            gateway_type="slack",
            namespace="test_namespace",
        )
        payload = peer_gateway_card.model_dump(by_alias=True, exclude_none=True)

        result = await gateway._handle_discovery_message(payload)

        assert result is True
        assert "PeerGateway-001" in gateway.gateway_registry.get_gateway_ids()

        stored_card = gateway.gateway_registry.get_gateway("PeerGateway-001")
        assert stored_card is not None
        assert stored_card.name == "PeerGateway-001"

    async def test_gateway_registry_extracts_gateway_metadata(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway registry correctly extracts metadata from cards."""
        gateway = test_gateway_app_instance

        peer_gateway_card = create_test_gateway_card(
            gateway_id="MetadataGateway",
            gateway_type="rest",
            namespace="production/sam",
            deployment_id="k8s-pod-xyz789",
        )
        payload = peer_gateway_card.model_dump(by_alias=True, exclude_none=True)

        await gateway._handle_discovery_message(payload)

        assert gateway.gateway_registry.get_gateway_type("MetadataGateway") == "rest"
        assert gateway.gateway_registry.get_gateway_namespace("MetadataGateway") == "production/sam"
        assert gateway.gateway_registry.get_deployment_id("MetadataGateway") == "k8s-pod-xyz789"

    async def test_agent_card_routed_to_agent_registry(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that agent cards (non-gateway) are routed to core_a2a_service."""
        gateway = test_gateway_app_instance

        initial_gateway_count = len(gateway.gateway_registry.get_gateway_ids())

        agent_card = create_test_agent_card("DiscoveryTestAgent")
        payload = agent_card.model_dump(by_alias=True, exclude_none=True)

        result = await gateway._handle_discovery_message(payload)

        assert result is True
        assert len(gateway.gateway_registry.get_gateway_ids()) == initial_gateway_count
        assert "DiscoveryTestAgent" not in gateway.gateway_registry.get_gateway_ids()

    async def test_multiple_gateway_cards_stored_correctly(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that multiple peer gateways can be discovered and stored."""
        gateway = test_gateway_app_instance

        gateway.gateway_registry.clear()

        gateway_configs = [
            ("Gateway-HTTP", "http_sse"),
            ("Gateway-Slack", "slack"),
            ("Gateway-REST", "rest"),
            ("Gateway-Teams", "teams"),
        ]

        for gw_id, gw_type in gateway_configs:
            card = create_test_gateway_card(gateway_id=gw_id, gateway_type=gw_type)
            payload = card.model_dump(by_alias=True, exclude_none=True)
            await gateway._handle_discovery_message(payload)

        ids = gateway.gateway_registry.get_gateway_ids()
        assert len(ids) == 4

        for gw_id, gw_type in gateway_configs:
            assert gw_id in ids
            assert gateway.gateway_registry.get_gateway_type(gw_id) == gw_type


class TestGatewayHeartbeat:
    """Test gateway heartbeat (re-registration) behavior."""

    async def test_heartbeat_updates_last_seen_timestamp(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that republishing same gateway card updates last_seen."""
        gateway = test_gateway_app_instance

        peer_card = create_test_gateway_card(
            gateway_id="HeartbeatGateway",
            gateway_type="http_sse",
        )
        payload = peer_card.model_dump(by_alias=True, exclude_none=True)

        await gateway._handle_discovery_message(payload)
        first_seen = gateway.gateway_registry.get_last_seen("HeartbeatGateway")

        await asyncio.sleep(0.1)

        await gateway._handle_discovery_message(payload)
        second_seen = gateway.gateway_registry.get_last_seen("HeartbeatGateway")

        assert second_seen > first_seen

    async def test_heartbeat_does_not_duplicate_gateway(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that heartbeat doesn't create duplicate registry entries."""
        gateway = test_gateway_app_instance
        gateway.gateway_registry.clear()

        peer_card = create_test_gateway_card(
            gateway_id="NoDuplicateGateway",
            gateway_type="http_sse",
        )
        payload = peer_card.model_dump(by_alias=True, exclude_none=True)

        for _ in range(5):
            await gateway._handle_discovery_message(payload)

        ids = gateway.gateway_registry.get_gateway_ids()
        assert ids.count("NoDuplicateGateway") == 1
        assert len(ids) == 1

    async def test_heartbeat_returns_false_for_update(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that add_or_update returns False for heartbeat (existing gateway)."""
        gateway = test_gateway_app_instance

        peer_card = create_test_gateway_card(
            gateway_id="UpdateCheckGateway",
            gateway_type="http_sse",
        )
        payload = peer_card.model_dump(by_alias=True, exclude_none=True)

        first_result = await gateway._handle_discovery_message(payload)
        assert first_result is True

        is_new = gateway.gateway_registry.add_or_update_gateway(peer_card)
        assert is_new is False


class TestDiscoveryErrorHandling:
    """Test error handling in discovery message processing."""

    async def test_handles_invalid_payload_gracefully(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that invalid payloads are handled without crashing."""
        gateway = test_gateway_app_instance

        invalid_payload = {"invalid": "data", "not_a_card": True}

        result = await gateway._handle_discovery_message(invalid_payload)

        assert result is False

    async def test_handles_empty_payload(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that empty payload is handled gracefully."""
        gateway = test_gateway_app_instance

        result = await gateway._handle_discovery_message({})

        assert result is False

    async def test_handles_payload_missing_required_fields(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test payload with some but not all required fields."""
        gateway = test_gateway_app_instance

        partial_payload = {
            "name": "PartialGateway",
        }

        result = await gateway._handle_discovery_message(partial_payload)

        assert result is False


class TestGatewayRegistryIsolation:
    """Test that gateway registry is isolated from agent registry."""

    async def test_gateway_and_agent_registries_are_separate(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that gateway and agent cards go to different registries."""
        gateway = test_gateway_app_instance
        gateway.gateway_registry.clear()

        gateway_card = create_test_gateway_card(
            gateway_id="IsolationGateway",
            gateway_type="http_sse",
        )
        agent_card = create_test_agent_card("IsolationAgent")

        await gateway._handle_discovery_message(
            gateway_card.model_dump(by_alias=True, exclude_none=True)
        )
        await gateway._handle_discovery_message(
            agent_card.model_dump(by_alias=True, exclude_none=True)
        )

        gateway_ids = gateway.gateway_registry.get_gateway_ids()
        assert "IsolationGateway" in gateway_ids
        assert "IsolationAgent" not in gateway_ids

    async def test_is_gateway_card_distinguishes_correctly(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that is_gateway_card correctly identifies card types."""
        gateway_card = create_test_gateway_card("TestGW", "http_sse")
        agent_card = create_test_agent_card("TestAgent")

        assert is_gateway_card(gateway_card) is True
        assert is_gateway_card(agent_card) is False


class TestGatewayRegistryCallbacks:
    """Test that registry callbacks are invoked correctly."""

    async def test_on_added_callback_invoked_for_new_gateway(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that on_gateway_added callback is invoked for new discoveries."""
        gateway = test_gateway_app_instance

        added_gateways = []

        def on_added(card):
            added_gateways.append(card.name)

        gateway.gateway_registry.set_on_added_callback(on_added)
        gateway.gateway_registry.clear()

        peer_card = create_test_gateway_card(
            gateway_id="CallbackTestGateway",
            gateway_type="http_sse",
        )
        payload = peer_card.model_dump(by_alias=True, exclude_none=True)

        await gateway._handle_discovery_message(payload)

        assert "CallbackTestGateway" in added_gateways

    async def test_on_added_callback_not_invoked_for_heartbeat(
        self, test_gateway_app_instance: TestGatewayComponent
    ):
        """Test that on_gateway_added is NOT called for heartbeat updates."""
        gateway = test_gateway_app_instance

        callback_count = {"count": 0}

        def on_added(card):
            callback_count["count"] += 1

        gateway.gateway_registry.set_on_added_callback(on_added)
        gateway.gateway_registry.clear()

        peer_card = create_test_gateway_card(
            gateway_id="HeartbeatCallbackGateway",
            gateway_type="http_sse",
        )
        payload = peer_card.model_dump(by_alias=True, exclude_none=True)

        await gateway._handle_discovery_message(payload)
        await gateway._handle_discovery_message(payload)
        await gateway._handle_discovery_message(payload)

        assert callback_count["count"] == 1
