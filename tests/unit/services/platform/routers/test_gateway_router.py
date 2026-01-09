"""
Unit tests for platform service gateway router.
Tests the gateway discovery API endpoint.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
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


def create_mock_user_config(user_id: str = "test-user") -> dict:
    """Helper to create mock user config for authorized requests."""
    return {
        "user_profile": {"id": user_id, "email": f"{user_id}@test.com"},
        "scopes": ["sam:gateways:read"],
    }


class TestGetDiscoveredGatewayCardsEndpoint:
    """Test GET /api/v1/platform/gatewayCards endpoint."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_gateways(self):
        """Test endpoint returns empty list when no gateways discovered."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        registry = GatewayRegistry()
        user_config = create_mock_user_config()

        result = await get_discovered_gateway_cards(registry, user_config)

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

        user_config = create_mock_user_config()
        result = await get_discovered_gateway_cards(registry, user_config)

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

        user_config = create_mock_user_config()
        result = await get_discovered_gateway_cards(registry, user_config)

        assert len(result) == 3
        assert [g.name for g in result] == ["alpha", "mike", "zebra"]

    @pytest.mark.asyncio
    async def test_handles_none_registry(self):
        """Test endpoint handles None registry gracefully."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )

        user_config = create_mock_user_config()

        with pytest.raises(HTTPException) as exc_info:
            await get_discovered_gateway_cards(None, user_config)

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

        user_config = create_mock_user_config()
        result = await get_discovered_gateway_cards(registry, user_config)

        assert len(result) == 1
        card = result[0]

        assert card.name == "gw-1"
        assert card.description == "HTTP_SSE Gateway"
        assert card.version == "1.0.0"
        assert "solace:prod/company" in card.url


class TestGatewayCardsAuthorization:
    """Test authorization for gatewayCards endpoint."""

    def test_validated_user_config_dependency_is_configured(self):
        """Test that endpoint uses ValidatedUserConfig with correct scope."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import (
            get_discovered_gateway_cards
        )
        import inspect

        sig = inspect.signature(get_discovered_gateway_cards)
        params = sig.parameters

        assert "user_config" in params
        default = params["user_config"].default
        assert default is not None
        assert hasattr(default, "dependency")

    def test_required_scope_is_sam_gateways_read(self):
        """Test that endpoint requires sam:gateways:read scope."""
        from solace_agent_mesh.services.platform.api.routers.gateway_router import router

        route = None
        for r in router.routes:
            if hasattr(r, "path") and r.path == "/gatewayCards":
                route = r
                break

        assert route is not None

        endpoint = route.endpoint
        import inspect
        sig = inspect.signature(endpoint)
        user_config_param = sig.parameters.get("user_config")

        assert user_config_param is not None
        validated_config = user_config_param.default
        assert validated_config.dependency.required_scopes == ["sam:gateways:read"]
