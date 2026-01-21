"""
Unit tests for gateway adapter agent registry handler methods.
Tests the handle_agent_registered and handle_agent_deregistered methods.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from a2a.types import AgentCard, AgentSkill

from solace_agent_mesh.gateway.adapter.base import GatewayAdapter
from solace_agent_mesh.gateway.adapter.types import (
    AuthClaims,
    ResponseContext,
    SamError,
    SamTask,
    SamUpdate,
)


class MockAdapter(GatewayAdapter):
    """Mock adapter for testing agent registry handlers."""

    def __init__(self):
        super().__init__()
        self.registered_agents = []
        self.deregistered_agents = []


    async def prepare_task(self, external_input, endpoint_context=None):
        return SamTask(
            target_agent="test-agent",
            message="Test message",
            conversation_id="conv-123",
            platform_context={}
        )

    async def deliver_update(self, update, context):
        pass

    async def deliver_response(self, response_parts, context):
        pass

    async def handle_error(self, error, context):
        pass

    async def handle_agent_registered(self, agent_card):
        """Track registered agents."""
        self.registered_agents.append(agent_card.name)

    async def handle_agent_deregistered(self, agent_name):
        """Track deregistered agents."""
        self.deregistered_agents.append(agent_name)


class DefaultAdapter(GatewayAdapter):
    """Adapter that uses default (no-op) implementations."""


    async def prepare_task(self, external_input, endpoint_context=None):
        return SamTask(
            target_agent="test-agent",
            message="Test message",
            conversation_id="conv-123",
            platform_context={}
        )

    async def deliver_update(self, update, context):
        pass

    async def deliver_response(self, response_parts, context):
        pass

    async def handle_error(self, error, context):
        pass


@pytest.fixture
def sample_agent_card():
    """Create a sample AgentCard for testing."""
    return AgentCard(
        name="TestAgent",
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


class TestAgentRegistryHandlers:
    """Test agent registry handler methods."""

    @pytest.mark.asyncio
    async def test_handle_agent_registered_called(self, sample_agent_card):
        """Test that handle_agent_registered is called with correct agent card."""
        adapter = MockAdapter()

        await adapter.handle_agent_registered(sample_agent_card)

        assert len(adapter.registered_agents) == 1
        assert adapter.registered_agents[0] == "TestAgent"

    @pytest.mark.asyncio
    async def test_handle_agent_deregistered_called(self):
        """Test that handle_agent_deregistered is called with correct agent name."""
        adapter = MockAdapter()

        await adapter.handle_agent_deregistered("TestAgent")

        assert len(adapter.deregistered_agents) == 1
        assert adapter.deregistered_agents[0] == "TestAgent"

    @pytest.mark.asyncio
    async def test_multiple_agent_registrations(self, sample_agent_card):
        """Test handling multiple agent registrations."""
        adapter = MockAdapter()

        # Register multiple agents
        for i in range(3):
            card = sample_agent_card.model_copy(update={"name": f"Agent{i}"})
            await adapter.handle_agent_registered(card)

        assert len(adapter.registered_agents) == 3
        assert adapter.registered_agents == ["Agent0", "Agent1", "Agent2"]

    @pytest.mark.asyncio
    async def test_multiple_agent_deregistrations(self):
        """Test handling multiple agent deregistrations."""
        adapter = MockAdapter()

        # Deregister multiple agents
        for i in range(3):
            await adapter.handle_agent_deregistered(f"Agent{i}")

        assert len(adapter.deregistered_agents) == 3
        assert adapter.deregistered_agents == ["Agent0", "Agent1", "Agent2"]

    @pytest.mark.asyncio
    async def test_default_implementation_handle_agent_registered(self, sample_agent_card):
        """Test that default implementation of handle_agent_registered is a no-op."""
        adapter = DefaultAdapter()

        # Should not raise any errors
        await adapter.handle_agent_registered(sample_agent_card)

    @pytest.mark.asyncio
    async def test_default_implementation_handle_agent_deregistered(self):
        """Test that default implementation of handle_agent_deregistered is a no-op."""
        adapter = DefaultAdapter()

        # Should not raise any errors
        await adapter.handle_agent_deregistered("TestAgent")

    @pytest.mark.asyncio
    async def test_agent_card_properties_accessible(self, sample_agent_card):
        """Test that adapter can access agent card properties."""
        received_cards = []

        class InspectingAdapter(GatewayAdapter):
            async def extract_auth_claims(self, external_input, endpoint_context=None):
                return AuthClaims(id="test-user", name="Test User")

            async def prepare_task(self, external_input, endpoint_context=None):
                return SamTask(
                    target_agent="test-agent",
                    message="Test message",
                    conversation_id="conv-123",
                    platform_context={}
                )

            async def deliver_update(self, update, context):
                pass

            async def deliver_response(self, response_parts, context):
                pass

            async def handle_error(self, error, context):
                pass

            async def handle_agent_registered(self, agent_card):
                # Access various properties
                received_cards.append({
                    "name": agent_card.name,
                    "description": agent_card.description,
                    "version": agent_card.version,
                    "skills": len(agent_card.skills),
                })

        adapter = InspectingAdapter()
        await adapter.handle_agent_registered(sample_agent_card)

        assert len(received_cards) == 1
        card_info = received_cards[0]
        assert card_info["name"] == "TestAgent"
        assert card_info["description"] == "A test agent"
        assert card_info["version"] == "1.0.0"
        assert card_info["skills"] == 1


class TestAgentRegistryHandlerErrorHandling:
    """Test error handling in agent registry handlers."""

    @pytest.mark.asyncio
    async def test_handle_agent_registered_exception(self, sample_agent_card):
        """Test that exceptions in handle_agent_registered can be raised."""

        class FailingAdapter(GatewayAdapter):
            async def extract_auth_claims(self, external_input, endpoint_context=None):
                return AuthClaims(id="test-user", name="Test User")

            async def prepare_task(self, external_input, endpoint_context=None):
                return SamTask(
                    target_agent="test-agent",
                    message="Test message",
                    conversation_id="conv-123",
                    platform_context={}
                )

            async def deliver_update(self, update, context):
                pass

            async def deliver_response(self, response_parts, context):
                pass

            async def handle_error(self, error, context):
                pass

            async def handle_agent_registered(self, agent_card):
                raise RuntimeError("Failed to register agent")

        adapter = FailingAdapter()

        with pytest.raises(RuntimeError, match="Failed to register agent"):
            await adapter.handle_agent_registered(sample_agent_card)

    @pytest.mark.asyncio
    async def test_handle_agent_deregistered_exception(self):
        """Test that exceptions in handle_agent_deregistered can be raised."""

        class FailingAdapter(GatewayAdapter):
            async def extract_auth_claims(self, external_input, endpoint_context=None):
                return AuthClaims(id="test-user", name="Test User")

            async def prepare_task(self, external_input, endpoint_context=None):
                return SamTask(
                    target_agent="test-agent",
                    message="Test message",
                    conversation_id="conv-123",
                    platform_context={}
                )

            async def deliver_update(self, update, context):
                pass

            async def deliver_response(self, response_parts, context):
                pass

            async def handle_error(self, error, context):
                pass

            async def handle_agent_deregistered(self, agent_name):
                raise RuntimeError("Failed to deregister agent")

        adapter = FailingAdapter()

        with pytest.raises(RuntimeError, match="Failed to deregister agent"):
            await adapter.handle_agent_deregistered("TestAgent")


class TestAgentRegistryHandlerUseCases:
    """Test real-world use cases for agent registry handlers."""

    @pytest.mark.asyncio
    async def test_dynamic_tool_registration_use_case(self, sample_agent_card):
        """Test use case: dynamically registering tools when agents are added."""

        class MCPAdapter(GatewayAdapter):
            def __init__(self):
                super().__init__()
                self.available_tools = []

            async def extract_auth_claims(self, external_input, endpoint_context=None):
                return AuthClaims(id="test-user", name="Test User")

            async def prepare_task(self, external_input, endpoint_context=None):
                return SamTask(
                    target_agent="test-agent",
                    message="Test message",
                    conversation_id="conv-123",
                    platform_context={}
                )

            async def deliver_update(self, update, context):
                pass

            async def deliver_response(self, response_parts, context):
                pass

            async def handle_error(self, error, context):
                pass

            async def handle_agent_registered(self, agent_card):
                # Simulate registering tools for each agent skill
                for skill in agent_card.skills:
                    tool_name = f"{agent_card.name}_{skill.id}"
                    self.available_tools.append(tool_name)

            async def handle_agent_deregistered(self, agent_name):
                # Remove tools when agent is deregistered
                self.available_tools = [
                    tool for tool in self.available_tools
                    if not tool.startswith(agent_name)
                ]

        adapter = MCPAdapter()

        # Register agent with skills
        await adapter.handle_agent_registered(sample_agent_card)
        assert len(adapter.available_tools) == 1
        assert adapter.available_tools[0] == "TestAgent_test-skill"

        # Deregister agent
        await adapter.handle_agent_deregistered("TestAgent")
        assert len(adapter.available_tools) == 0

    @pytest.mark.asyncio
    async def test_agent_discovery_notification_use_case(self, sample_agent_card):
        """Test use case: notifying users when new agents become available."""

        class NotifyingAdapter(GatewayAdapter):
            def __init__(self):
                super().__init__()
                self.notifications = []

            async def extract_auth_claims(self, external_input, endpoint_context=None):
                return AuthClaims(id="test-user", name="Test User")

            async def prepare_task(self, external_input, endpoint_context=None):
                return SamTask(
                    target_agent="test-agent",
                    message="Test message",
                    conversation_id="conv-123",
                    platform_context={}
                )

            async def deliver_update(self, update, context):
                pass

            async def deliver_response(self, response_parts, context):
                pass

            async def handle_error(self, error, context):
                pass

            async def handle_agent_registered(self, agent_card):
                # Notify users of new agent
                self.notifications.append(
                    f"New agent available: {agent_card.name} - {agent_card.description}"
                )

            async def handle_agent_deregistered(self, agent_name):
                # Notify users of agent removal
                self.notifications.append(
                    f"Agent no longer available: {agent_name}"
                )

        adapter = NotifyingAdapter()

        # Register agent
        await adapter.handle_agent_registered(sample_agent_card)
        assert len(adapter.notifications) == 1
        assert "TestAgent" in adapter.notifications[0]
        assert "A test agent" in adapter.notifications[0]

        # Deregister agent
        await adapter.handle_agent_deregistered("TestAgent")
        assert len(adapter.notifications) == 2
        assert "TestAgent" in adapter.notifications[1]
        assert "no longer available" in adapter.notifications[1]
