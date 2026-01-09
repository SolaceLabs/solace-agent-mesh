"""
Unit tests for platform service gateway router.
Tests the gateway discovery API endpoint.
"""

import pytest
from a2a.types import AgentCard, AgentExtension

from solace_agent_mesh.common.gateway_registry import GatewayRegistry


def create_test_gateway_card(
    gateway_id: str,
    gateway_type: str,
    namespace: str = "test/sam",
    deployment_id: str = None
) -> AgentCard:
    """Helper to create test gateway cards."""
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
        protocolVersion="1.0",
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": extensions,
        },
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[],
    )


class TestGetDiscoveredGatewayCardsEndpoint:
    """Test GET /api/v1/platform/gatewayCards endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_gateways(self):
        """Test endpoint returns empty list when no gateways discovered."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        registry = GatewayRegistry()

        result = await get_discovered_gateway_cards(registry)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_discovered_gateways(self):
        """Test endpoint returns list of discovered gateways."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        registry = GatewayRegistry()
        gw1 = create_test_gateway_card("gw-1", "http_sse")
        gw2 = create_test_gateway_card("gw-2", "slack")

        registry.add_or_update_gateway(gw1)
        registry.add_or_update_gateway(gw2)

        result = await get_discovered_gateway_cards(registry)

        assert len(result) == 2
        assert result[0].name == "gw-1"
        assert result[1].name == "gw-2"

    @pytest.mark.asyncio
    async def test_returns_gateways_in_sorted_order(self):
        """Test endpoint returns gateways in sorted order."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        registry = GatewayRegistry()
        for name in ["zebra", "alpha", "mike"]:
            card = create_test_gateway_card(name, "http_sse")
            registry.add_or_update_gateway(card)

        result = await get_discovered_gateway_cards(registry)

        assert len(result) == 3
        assert [g.name for g in result] == ["alpha", "mike", "zebra"]

    @pytest.mark.asyncio
    async def test_handles_none_registry(self):
        """Test endpoint handles None registry gracefully."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_discovered_gateway_cards(None)

        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_full_agent_card(self):
        """Test endpoint returns complete AgentCard objects."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        registry = GatewayRegistry()
        gw = create_test_gateway_card(
            "gw-1",
            "http_sse",
            namespace="prod/company",
            deployment_id="k8s-pod-123"
        )
        registry.add_or_update_gateway(gw)

        result = await get_discovered_gateway_cards(registry)

        assert len(result) == 1
        card = result[0]

        assert card.name == "gw-1"
        assert card.description == "HTTP_SSE Gateway"
        assert card.version == "1.0.0"
        assert "solace:prod/company" in card.url
