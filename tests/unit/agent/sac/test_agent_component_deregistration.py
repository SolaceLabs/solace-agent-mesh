import unittest
from unittest.mock import MagicMock
from a2a.types import AgentCard
from solace_agent_mesh.agent.sac.component import SamAgentComponent

from solace_agent_mesh.common.agent_registry import AgentRegistry


class TestSamAgentComponentDeregistration(unittest.TestCase):
    """Test suite for agent de-registration in SamAgentComponent."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the SamAgentComponent with minimal required attributes
        self.component = MagicMock(spec=SamAgentComponent)
        self.component.log_identifier = "[TestAgent]"
        self.component.agent_name = "test_agent"
        self.component.namespace = "test/namespace"
        self.component.peer_agents = {}
        
        # Create a real AgentRegistry for testing
        self.agent_registry = AgentRegistry()
        self.component.agent_registry = self.agent_registry
        
        # Mock the publish_a2a_message method
        self.component.publish_a2a_message = MagicMock()
        
        # Create test agent cards
        self.agent_card1 = AgentCard(
            name="agent1",
            description="Test Agent 1",
            capabilities={},
            skills=[],
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            url="http://localhost:8000/agent1"
        )
        self.agent_card2 = AgentCard(
            name="agent2",
            description="Test Agent 2",
            capabilities={},
            skills=[],
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            url="http://localhost:8000/agent2"
        )
        
        # Add agents to registry
        self.agent_registry.add_or_update_agent(self.agent_card1)
        self.agent_registry.add_or_update_agent(self.agent_card2)
        
        # Add to peer_agents dictionary
        self.component.peer_agents = {
            "agent1": self.agent_card1,
            "agent2": self.agent_card2
        }

    def test_check_agent_health_no_expired_agents(self):
        """Test _check_agent_health when no agents have expired TTLs."""
        # Set up
        self.component._deregister_agent = MagicMock()
        self.component.agent_discovery_config = {
            "health_check_ttl_seconds": 300,  # 5 minutes
            "health_check_interval_seconds": 10
        }
        
        # Execute
        SamAgentComponent._check_agent_health(self.component)
        
        # Verify
        self.component._deregister_agent.assert_not_called()
        self.assertEqual(len(self.agent_registry.get_agent_names()), 2)
        self.assertEqual(len(self.component.peer_agents), 2)

    def test_check_agent_health_with_expired_agents(self):
        """Test _check_agent_health when some agents have expired TTLs."""
        # Set up
        self.component._deregister_agent = MagicMock()
        self.component.agent_discovery_config = {
            "health_check_ttl_seconds": 10,  # 10 seconds
            "health_check_interval_seconds": 5
        }
        
        # Mock the check_ttl_expired method to simulate agent1 being expired
        self.agent_registry.check_ttl_expired = MagicMock()
        self.agent_registry.check_ttl_expired.side_effect = lambda agent_name, ttl: (True, 20) if agent_name == "agent1" else (False, 0)
        
        # Execute
        SamAgentComponent._check_agent_health(self.component)
        
        # Verify
        self.component._deregister_agent.assert_called_once_with("agent1")

    def test_deregister_agent(self):
        """Test _deregister_agent removes the agent and publishes an event."""
        # Execute
        SamAgentComponent._deregister_agent(self.component, "agent1")

        # Verify
        # Agent should be removed from registry
        self.assertNotIn("agent1", self.agent_registry.get_agent_names())
        # Agent should be removed from peer_agents
        self.assertNotIn("agent1", self.component.peer_agents)
        # De-registration event should be published
        self.component.publish_a2a_message.assert_called_once()

        # Verify payload contents
        # The IndexError indicates the payload is not a positional argument.
        # We assume it's passed as a keyword argument, likely 'payload'.
        _, kwargs = self.component.publish_a2a_message.call_args
        payload = kwargs['payload']
        self.assertEqual(payload["event_type"], "agent.deregistered")
        self.assertEqual(payload["agent_name"], "agent1")
        self.assertEqual(payload["reason"], "health_check_failure")
        self.assertIn("metadata", payload)
        self.assertEqual(payload["metadata"]["deregistered_by"], "test_agent")
        self.assertIn("timestamp", payload["metadata"])

    def test_deregister_nonexistent_agent(self):
        """Test _deregister_agent with a non-existent agent."""
        # Execute
        SamAgentComponent._deregister_agent(self.component, "nonexistent_agent")
        
        # Verify
        # Registry should remain unchanged
        self.assertEqual(len(self.agent_registry.get_agent_names()), 2)
        # peer_agents should remain unchanged
        self.assertEqual(len(self.component.peer_agents), 2)
        # No event should be published
        self.component.publish_a2a_message.assert_not_called()

    def test_check_agent_health_skips_own_agent(self):
        """Test _check_agent_health skips the component's own agent name."""
        # Set up
        self.component._deregister_agent = MagicMock()
        self.component.agent_discovery_config = {
            "health_check_ttl_seconds": 10,
            "health_check_interval_seconds": 5
        }
        
        # Add the component's own agent name to the registry
        own_agent_card = AgentCard(
            name="test_agent",  # Same as self.component.agent_name
            description="Own Agent",
            capabilities={},
            skills=[],
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            url="http://localhost:8000/test_agent"
        )
        self.agent_registry.add_or_update_agent(own_agent_card)
        
        # Mock the check_ttl_expired method to simulate all agents being expired
        self.agent_registry.check_ttl_expired = MagicMock()
        self.agent_registry.check_ttl_expired.return_value = (True, 20)  # All agents expired
        
        # Execute
        SamAgentComponent._check_agent_health(self.component)
        
        # Verify
        # Should call _deregister_agent for agent1 and agent2, but not for test_agent
        self.assertEqual(self.component._deregister_agent.call_count, 2)
        self.component._deregister_agent.assert_any_call("agent1")
        self.component._deregister_agent.assert_any_call("agent2")
        
        # Ensure own agent name wasn't deregistered
        calls = [call[0][0] for call in self.component._deregister_agent.call_args_list]
        self.assertNotIn("test_agent", calls)

