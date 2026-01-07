"""
Unit tests for platform service gateway router.
Tests the gateway discovery and health monitoring API endpoints.
"""

import pytest
from unittest.mock import MagicMock
from a2a.types import AgentCard, AgentCapabilities, AgentExtension

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


class TestListGatewaysEndpoint:
    """Test GET /api/v1/platform/gateways endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_gateways(self):
        """Test endpoint returns empty list when no gateways discovered."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            list_gateways
        )

        registry = GatewayRegistry()

        result = await list_gateways(registry)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_discovered_gateways(self):
        """Test endpoint returns list of discovered gateways."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            list_gateways
        )

        registry = GatewayRegistry()
        gw1 = create_test_gateway_card("gw-1", "http_sse")
        gw2 = create_test_gateway_card("gw-2", "slack")

        registry.add_or_update_gateway(gw1)
        registry.add_or_update_gateway(gw2)

        result = await list_gateways(registry)

        assert len(result) == 2
        assert result[0].name == "gw-1"
        assert result[1].name == "gw-2"

    @pytest.mark.asyncio
    async def test_returns_gateways_in_sorted_order(self):
        """Test endpoint returns gateways in sorted order."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            list_gateways
        )

        registry = GatewayRegistry()
        for name in ["zebra", "alpha", "mike"]:
            card = create_test_gateway_card(name, "http_sse")
            registry.add_or_update_gateway(card)

        result = await list_gateways(registry)

        assert len(result) == 3
        assert [g.name for g in result] == ["alpha", "mike", "zebra"]

    @pytest.mark.asyncio
    async def test_handles_none_registry(self):
        """Test endpoint handles None registry gracefully."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            list_gateways
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await list_gateways(None)

        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail.lower()


class TestGetGatewaysHealthEndpoint:
    """Test GET /api/v1/platform/gateways/health endpoint."""

    @pytest.mark.asyncio
    async def test_returns_health_for_all_gateways(self):
        """Test endpoint returns health status for all gateways."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateways_health
        )
        import time

        registry = GatewayRegistry()
        gw1 = create_test_gateway_card("healthy-gw", "http_sse")
        gw2 = create_test_gateway_card("stale-gw", "slack")

        registry.add_or_update_gateway(gw1)
        registry.add_or_update_gateway(gw2)

        registry._last_seen["stale-gw"] = time.time() - 120

        result = await get_gateways_health(registry, ttl_seconds=90)

        assert result["total_gateways"] == 2
        assert result["healthy_count"] == 1
        assert result["unhealthy_count"] == 1
        assert result["ttl_seconds"] == 90

        gateways = result["gateways"]
        assert len(gateways) == 2

        healthy = [g for g in gateways if g["health_status"] == "healthy"]
        unhealthy = [g for g in gateways if g["health_status"] == "unhealthy"]

        assert len(healthy) == 1
        assert healthy[0]["gateway_id"] == "healthy-gw"

        assert len(unhealthy) == 1
        assert unhealthy[0]["gateway_id"] == "stale-gw"

    @pytest.mark.asyncio
    async def test_includes_gateway_metadata(self):
        """Test endpoint includes gateway type, namespace, deployment_id."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateways_health
        )

        registry = GatewayRegistry()
        gw = create_test_gateway_card(
            "gw-1",
            "http_sse",
            namespace="prod/company",
            deployment_id="k8s-pod-123"
        )
        registry.add_or_update_gateway(gw)

        result = await get_gateways_health(registry)

        assert len(result["gateways"]) == 1
        gateway_info = result["gateways"][0]

        assert gateway_info["gateway_id"] == "gw-1"
        assert gateway_info["gateway_type"] == "http_sse"
        assert gateway_info["namespace"] == "prod/company"
        assert gateway_info["deployment_id"] == "k8s-pod-123"
        assert "health_status" in gateway_info
        assert "last_seen" in gateway_info

    @pytest.mark.asyncio
    async def test_handles_none_registry(self):
        """Test endpoint handles None registry gracefully."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateways_health
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_gateways_health(None)

        assert exc_info.value.status_code == 503


class TestGetGatewayHealthEndpoint:
    """Test GET /api/v1/platform/gateways/{gateway_id}/health endpoint."""

    @pytest.mark.asyncio
    async def test_returns_health_for_specific_gateway(self):
        """Test endpoint returns health for specific gateway."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateway_health
        )

        registry = GatewayRegistry()
        gw = create_test_gateway_card("gw-1", "http_sse")
        registry.add_or_update_gateway(gw)

        result = await get_gateway_health("gw-1", registry)

        assert result["gateway_id"] == "gw-1"
        assert result["gateway_type"] == "http_sse"
        assert result["health_status"] == "healthy"
        assert result["seconds_since_last_seen"] < 5

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_gateway(self):
        """Test endpoint returns 404 when gateway not found."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateway_health
        )
        from fastapi import HTTPException

        registry = GatewayRegistry()

        with pytest.raises(HTTPException) as exc_info:
            await get_gateway_health("nonexistent", registry)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_respects_custom_ttl(self):
        """Test endpoint respects custom TTL parameter."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateway_health
        )
        import time

        registry = GatewayRegistry()
        gw = create_test_gateway_card("gw-1", "http_sse")
        registry.add_or_update_gateway(gw)

        registry._last_seen["gw-1"] = time.time() - 50

        result_long_ttl = await get_gateway_health("gw-1", registry, ttl_seconds=60)
        assert result_long_ttl["health_status"] == "healthy"

        result_short_ttl = await get_gateway_health("gw-1", registry, ttl_seconds=30)
        assert result_short_ttl["health_status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_handles_none_registry(self):
        """Test endpoint handles None registry gracefully."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_gateway_health
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_gateway_health("gw-1", None)

        assert exc_info.value.status_code == 503
