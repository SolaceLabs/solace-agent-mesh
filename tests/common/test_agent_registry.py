import unittest
from unittest.mock import patch, MagicMock
import time

from a2a.types import AgentCard, AgentCapabilities
from solace_agent_mesh.common.agent_registry import AgentRegistry


class TestAgentRegistry(unittest.TestCase):
    """Test suite for AgentRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = AgentRegistry()
        
        # Create test agent cards
        self.agent_card1 = AgentCard(
            name="agent1",
            description="Test Agent 1",
            capabilities=AgentCapabilities(
                streaming=False,
                push_notifications=False,
                state_transition_history=False
            ),
            skills=[],
            version="1.0.0",
            url="solace:test/agent1",
            defaultInputModes=["text"],
            defaultOutputModes=["text"]
        )
        self.agent_card2 = AgentCard(
            name="agent2",
            description="Test Agent 2",
            capabilities=AgentCapabilities(
                streaming=False,
                push_notifications=False,
                state_transition_history=False
            ),
            skills=[],
            version="1.0.0",
            url="solace:test/agent2",
            defaultInputModes=["text"],
            defaultOutputModes=["text"]
        )
        
        # Add agents to registry
        self.registry.add_or_update_agent(self.agent_card1)
        self.registry.add_or_update_agent(self.agent_card2)

    def test_check_ttl_expired_not_expired(self):
        """Test check_ttl_expired when TTL has not expired."""
        # Execute
        is_expired, time_since_last_seen = self.registry.check_ttl_expired("agent1", 300)
        
        # Verify
        self.assertFalse(is_expired)
        self.assertLessEqual(time_since_last_seen, 1)  # Should be very recent

    def test_check_ttl_expired_is_expired(self):
        """Test check_ttl_expired when TTL has expired."""
        # Set up - manually modify the last_seen time
        current_time = time.time()
        expired_time = current_time - 20
        
        # Directly modify the _last_seen dictionary
        self.registry._last_seen["agent1"] = expired_time
        
        # Execute
        is_expired, time_since_last_seen = self.registry.check_ttl_expired("agent1", 10)
        
        # Verify
        self.assertTrue(is_expired)
        self.assertGreaterEqual(time_since_last_seen, 10)

    def test_check_ttl_expired_nonexistent_agent(self):
        """Test check_ttl_expired with a non-existent agent."""
        # Execute
        is_expired, time_since_last_seen = self.registry.check_ttl_expired("nonexistent_agent", 10)
        
        # Verify
        self.assertFalse(is_expired)
        self.assertEqual(time_since_last_seen, 0)

    def test_remove_agent_existing(self):
        """Test remove_agent with an existing agent."""
        # Execute
        result = self.registry.remove_agent("agent1")
        
        # Verify
        self.assertTrue(result)
        self.assertNotIn("agent1", self.registry.get_agent_names())
        self.assertIn("agent2", self.registry.get_agent_names())

    def test_remove_agent_nonexistent(self):
        """Test remove_agent with a non-existent agent."""
        # Execute
        result = self.registry.remove_agent("nonexistent_agent")
        
        # Verify
        self.assertFalse(result)
        self.assertEqual(len(self.registry.get_agent_names()), 2)

    def test_clear(self):
        """Test clear method."""
        # Execute
        self.registry.clear()
        
        # Verify
        self.assertEqual(len(self.registry.get_agent_names()), 0)


if __name__ == "__main__":
    unittest.main()