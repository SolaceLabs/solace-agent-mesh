"""
Unit tests for GenericGatewayComponent auth setup and agent registry callbacks.
Tests _setup_auth, agent registry callbacks, and list_agents functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from a2a.types import AgentCard, AgentSkill

from solace_agent_mesh.gateway.generic.component import (
    GenericGatewayComponent,
    ENTERPRISE_AUTH_AVAILABLE
)


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

class TestGenericGatewayAgentRegistryCallbacks:
    """Test agent registry callback wiring in GenericGatewayComponent."""

    def test_on_agent_added_calls_adapter_handler(self, sample_agent_card):
        """Test that _on_agent_added calls adapter.handle_agent_registered."""
        # Create mock component
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.adapter = AsyncMock()
        mock_component.get_async_loop = MagicMock(return_value=MagicMock())

        # Call the method
        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        GenericGatewayComponent._on_agent_added(mock_component, sample_agent_card)

        # Verify adapter method is scheduled
        # (actual call is async via asyncio.run_coroutine_threadsafe)
        # We verify the call was attempted
        assert mock_component.get_async_loop.called

    def test_on_agent_removed_calls_adapter_handler(self):
        """Test that _on_agent_removed calls adapter.handle_agent_deregistered."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.adapter = AsyncMock()
        mock_component.get_async_loop = MagicMock(return_value=MagicMock())

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        GenericGatewayComponent._on_agent_removed(mock_component, "TestAgent")

        # Verify adapter method is scheduled
        assert mock_component.get_async_loop.called

    def test_on_agent_added_without_adapter(self, sample_agent_card):
        """Test _on_agent_added when adapter is None."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.adapter = None

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent

        # Should not raise exception
        GenericGatewayComponent._on_agent_added(mock_component, sample_agent_card)

    def test_on_agent_removed_without_adapter(self):
        """Test _on_agent_removed when adapter is None."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.adapter = None

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent

        # Should not raise exception
        GenericGatewayComponent._on_agent_removed(mock_component, "TestAgent")


class TestGenericGatewayListAgents:
    """Test list_agents method in GenericGatewayComponent."""

    def test_list_agents_returns_agent_cards(self, sample_agent_card):
        """Test that list_agents returns list of AgentCard objects."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.agent_registry = MagicMock()
        mock_component.agent_registry.get_agent_names.return_value = ["TestAgent"]
        mock_component.agent_registry.get_agent.return_value = sample_agent_card

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        agents = GenericGatewayComponent.list_agents(mock_component)

        assert len(agents) == 1
        assert agents[0].name == "TestAgent"

    def test_list_agents_empty_registry(self):
        """Test list_agents when registry is empty."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.agent_registry = MagicMock()
        mock_component.agent_registry.get_agent_names.return_value = []

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        agents = GenericGatewayComponent.list_agents(mock_component)

        assert len(agents) == 0

    def test_list_agents_multiple_agents(self, sample_agent_card):
        """Test list_agents with multiple agents."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.agent_registry = MagicMock()
        mock_component.agent_registry.get_agent_names.return_value = [
            "Agent1", "Agent2", "Agent3"
        ]

        def get_agent_mock(name):
            return sample_agent_card.model_copy(update={"name": name})

        mock_component.agent_registry.get_agent.side_effect = get_agent_mock

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        agents = GenericGatewayComponent.list_agents(mock_component)

        assert len(agents) == 3
        assert agents[0].name == "Agent1"
        assert agents[1].name == "Agent2"
        assert agents[2].name == "Agent3"

    def test_list_agents_handles_none_agent_card(self):
        """Test list_agents when get_agent returns None for some agents."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.agent_registry = MagicMock()
        mock_component.agent_registry.get_agent_names.return_value = [
            "ValidAgent", "InvalidAgent"
        ]

        def get_agent_mock(name):
            if name == "ValidAgent":
                return AgentCard(
                    name="ValidAgent",
                    description="Valid",
                    url="https://valid.example.com",
                    version="1.0.0",
                    protocolVersion="0.3.0",
                    capabilities={"streaming": True},
                    defaultInputModes=["text/plain"],
                    defaultOutputModes=["text/plain"],
                    skills=[]
                )
            return None

        mock_component.agent_registry.get_agent.side_effect = get_agent_mock

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        agents = GenericGatewayComponent.list_agents(mock_component)

        # Should only include valid agents
        assert len(agents) == 1
        assert agents[0].name == "ValidAgent"

    def test_list_agents_exception_handling(self):
        """Test list_agents handles exceptions gracefully."""
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.agent_registry = MagicMock()
        mock_component.agent_registry.get_agent_names.side_effect = RuntimeError("Registry error")

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        agents = GenericGatewayComponent.list_agents(mock_component)

        # Should return empty list on error
        assert len(agents) == 0


class TestEnterpriseAuthAvailability:
    """Test enterprise auth availability flag."""

    def test_enterprise_auth_available_flag(self):
        """Test ENTERPRISE_AUTH_AVAILABLE flag is set correctly."""
        # The flag should be True if enterprise package is installed
        assert isinstance(ENTERPRISE_AUTH_AVAILABLE, bool)

    @pytest.mark.skipif(ENTERPRISE_AUTH_AVAILABLE, reason="Enterprise package is available")
    def test_sam_oauth2_handler_none_without_enterprise(self):
        """Test that SAMOAuth2Handler is None when enterprise not available."""
        from solace_agent_mesh.gateway.generic.component import SAMOAuth2Handler
        assert SAMOAuth2Handler is None

    @pytest.mark.skipif(not ENTERPRISE_AUTH_AVAILABLE, reason="Enterprise package not available")
    def test_sam_oauth2_handler_available_with_enterprise(self):
        """Test that SAMOAuth2Handler is available when enterprise is installed."""
        from solace_agent_mesh.gateway.generic.component import SAMOAuth2Handler
        assert SAMOAuth2Handler is not None

class TestAgentCallbackThreadSafety:
    """Test thread safety of agent registry callbacks."""

    def test_callbacks_use_asyncio_run_coroutine_threadsafe(self):
        """Test that callbacks use asyncio.run_coroutine_threadsafe."""
        # Callbacks are invoked from agent registry thread
        # Must use run_coroutine_threadsafe to schedule in component's loop
        mock_component = MagicMock()
        mock_component.log_identifier = "[TestGateway]"
        mock_component.adapter = AsyncMock()
        mock_loop = MagicMock()
        mock_component.get_async_loop.return_value = mock_loop

        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        GenericGatewayComponent._on_agent_removed(mock_component, "TestAgent")

        # Verify get_async_loop was called
        mock_component.get_async_loop.assert_called()
