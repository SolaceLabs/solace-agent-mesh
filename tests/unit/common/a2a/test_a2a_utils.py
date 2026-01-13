"""
Unit tests for common/a2a/utils.py
Tests gateway card identification and metadata extraction utilities.
"""

import pytest
from a2a.types import AgentCard, AgentCapabilities, AgentExtension, AgentSkill

from solace_agent_mesh.common.a2a.utils import (
    is_gateway_card,
    extract_gateway_info,
)


def create_gateway_card(
    gateway_id: str = "test-gateway",
    gateway_type: str = "http_sse",
    namespace: str = "test/sam",
    deployment_id: str = None
) -> AgentCard:
    """Helper to create gateway cards for testing."""
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


def create_agent_card(agent_name: str = "test-agent") -> AgentCard:
    """Helper to create agent cards for testing."""
    return AgentCard(
        name=agent_name,
        description="A test agent",
        url="https://test.example.com",
        version="1.0.0",
        protocolVersion="0.3.0",
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="test-skill",
                name="Test Skill",
                description="A test skill",
                tags=["test"],
            )
        ],
    )


class TestIsGatewayCard:
    """Test is_gateway_card() function."""

    def test_returns_true_for_gateway_card(self):
        """Test returns True for card with gateway-role extension."""
        card = create_gateway_card()
        assert is_gateway_card(card) is True

    def test_returns_false_for_agent_card(self):
        """Test returns False for regular agent card."""
        card = create_agent_card()
        assert is_gateway_card(card) is False

    def test_returns_false_for_none(self):
        """Test returns False for None."""
        assert is_gateway_card(None) is False

    def test_returns_false_for_card_without_extensions(self):
        """Test returns False when extensions missing."""
        card = AgentCard(
            name="test",
            url="https://test.com",
            description="Test",
            version="1.0.0",
            protocolVersion="1.0",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                "extensions": None
            },
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            skills=[]
        )
        assert is_gateway_card(card) is False

    def test_returns_false_for_card_with_empty_extensions(self):
        """Test returns False when extensions list is empty."""
        card = AgentCard(
            name="test",
            url="https://test.com",
            description="Test",
            version="1.0.0",
            protocolVersion="1.0",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                "extensions": []
            },
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            skills=[]
        )
        assert is_gateway_card(card) is False

    def test_gateway_with_multiple_extensions(self):
        """Test correctly identifies gateway with multiple extensions."""
        card = create_gateway_card(deployment_id="k8s-pod-123")
        assert is_gateway_card(card) is True

    def test_returns_true_for_different_gateway_types(self):
        """Test identifies gateways of different types."""
        assert is_gateway_card(create_gateway_card(gateway_type="http_sse")) is True
        assert is_gateway_card(create_gateway_card(gateway_type="slack")) is True
        assert is_gateway_card(create_gateway_card(gateway_type="rest")) is True
        assert is_gateway_card(create_gateway_card(gateway_type="teams")) is True


class TestExtractGatewayInfo:
    """Test extract_gateway_info() function."""

    def test_extracts_complete_gateway_info(self):
        """Test extracts all gateway info when present."""
        card = create_gateway_card(
            gateway_id="gw-1",
            gateway_type="http_sse",
            namespace="test/prod",
            deployment_id="k8s-pod-123"
        )

        info = extract_gateway_info(card)

        assert info is not None
        assert info["gateway_id"] == "gw-1"
        assert info["gateway_type"] == "http_sse"
        assert info["namespace"] == "test/prod"
        assert info["deployment_id"] == "k8s-pod-123"

    def test_extracts_gateway_info_without_deployment(self):
        """Test extracts gateway info without deployment ID."""
        card = create_gateway_card(
            gateway_id="gw-1",
            gateway_type="slack",
            namespace="test/staging"
        )

        info = extract_gateway_info(card)

        assert info is not None
        assert info["gateway_id"] == "gw-1"
        assert info["gateway_type"] == "slack"
        assert info["namespace"] == "test/staging"
        assert "deployment_id" not in info

    def test_returns_none_for_agent_card(self):
        """Test returns None for non-gateway card."""
        card = create_agent_card()

        info = extract_gateway_info(card)

        assert info is None

    def test_returns_none_for_none(self):
        """Test returns None for None input."""
        info = extract_gateway_info(None)
        assert info is None

    def test_handles_missing_params_in_extension(self):
        """Test handles extension with missing params."""
        card = AgentCard(
            name="gw-1",
            url="solace:test/sam/a2a/v1/gateway/request/gw-1",
            description="Gateway",
            version="1.0.0",
            protocolVersion="1.0",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
                "extensions": [
                    AgentExtension(
                        uri="https://solace.com/a2a/extensions/sam/gateway-role",
                        required=False,
                        params={}
                    )
                ]
            },
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            skills=[]
        )

        info = extract_gateway_info(card)

        assert info is not None
        assert info["gateway_id"] is None
        assert info["gateway_type"] is None
        assert info["namespace"] is None

    def test_extracts_different_gateway_types(self):
        """Test extracts info for different gateway types."""
        types = ["http_sse", "slack", "rest", "teams"]

        for gw_type in types:
            card = create_gateway_card(gateway_type=gw_type)
            info = extract_gateway_info(card)

            assert info is not None
            assert info["gateway_type"] == gw_type

    def test_extracts_different_namespaces(self):
        """Test extracts info for different namespaces."""
        namespaces = ["test/prod", "test/staging", "mycompany/dev", "org/env"]

        for ns in namespaces:
            card = create_gateway_card(namespace=ns)
            info = extract_gateway_info(card)

            assert info is not None
            assert info["namespace"] == ns
