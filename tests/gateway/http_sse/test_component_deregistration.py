import unittest
from unittest.mock import MagicMock, patch
import time

from a2a.types import AgentCard
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from solace_agent_mesh.common.agent_registry import AgentRegistry


class TestWebUIBackendComponentDeregistration(unittest.TestCase):
    """Test suite for agent de-registration in WebUIBackendComponent."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the WebUIBackendComponent with minimal required attributes
        self.component = MagicMock(spec=WebUIBackendComponent)
        self.component.log_identifier = "[TestGateway]"
        self.component.gateway_id = "test_gateway"
        
        # Create a real AgentRegistry for testing
        self.agent_registry = AgentRegistry()
        self.component.agent_registry = self.agent_registry
        
        # Create test agent cards
        self.agent_card1 = AgentCard(
            name="agent1",
            description="Test Agent 1",
            capabilities=[],
            skills=[],
            version="1.0.0"
        )
        self.agent_card2 = AgentCard(
            name="agent2",
            description="Test Agent 2",
            capabilities=[],
            skills=[],
            version="1.0.0"
        )
        
        # Add agents to registry
        self.agent_registry.add_or_update_agent(self.agent_card1)
        self.agent_registry.add_or_update_agent(self.agent_card2)

    def test_check_agent_health_no_expired_agents(self):
        """Test _check_agent_health when no agents have expired TTLs."""
        # Set up
        self.component._check_agent_health = WebUIBackendComponent._check_agent_health.__get__(self.component)
        self.component._deregister_agent = MagicMock()
        self.component.get_config = MagicMock()
        self.component.get_config.side_effect = lambda key, default=None: {
            "agent_health_check_ttl_seconds": 300,  # 5 minutes
            "agent_health_check_interval_seconds": 10
        }.get(key, default)
        
        # Execute
        self.component._check_agent_health()
        
        # Verify
        self.component._deregister_agent.assert_not_called()
        self.assertEqual(len(self.agent_registry.get_agent_names()), 2)

    def test_check_agent_health_with_expired_agents(self):
        """Test _check_agent_health when some agents have expired TTLs."""
        # Set up
        self.component._check_agent_health = WebUIBackendComponent._check_agent_health.__get__(self.component)
        self.component._deregister_agent = MagicMock()
        self.component.get_config = MagicMock()
        self.component.get_config.side_effect = lambda key, default=None: {
            "agent_health_check_ttl_seconds": 10,  # 10 seconds
            "agent_health_check_interval_seconds": 5
        }.get(key, default)
        
        # Manually modify the last_seen time for agent1 to simulate expiration
        with patch.object(self.agent_registry, '_last_seen') as mock_last_seen:
            mock_last_seen.__getitem__.side_effect = lambda key: time.time() - 20 if key == "agent1" else time.time()
            mock_last_seen.__contains__ = lambda self, key: key in ["agent1", "agent2"]
            
            # Execute
            self.component._check_agent_health()
        
        # Verify
        self.component._deregister_agent.assert_called_once_with("agent1")

    def test_deregister_agent(self):
        """Test _deregister_agent removes the agent from the registry."""
        # Set up
        self.component._deregister_agent = WebUIBackendComponent._deregister_agent.__get__(self.component)
        
        # Execute
        self.component._deregister_agent("agent1")
        
        # Verify
        # Agent should be removed from registry
        self.assertNotIn("agent1", self.agent_registry.get_agent_names())
        self.assertIn("agent2", self.agent_registry.get_agent_names())

    def test_deregister_nonexistent_agent(self):
        """Test _deregister_agent with a non-existent agent."""
        # Set up
        self.component._deregister_agent = WebUIBackendComponent._deregister_agent.__get__(self.component)
        
        # Execute
        self.component._deregister_agent("nonexistent_agent")
        
        # Verify
        # Registry should remain unchanged
        self.assertEqual(len(self.agent_registry.get_agent_names()), 2)
        
    def test_check_agent_health_multiple_expired_agents(self):
        """Test _check_agent_health when multiple agents have expired TTLs."""
        # Set up
        self.component._check_agent_health = WebUIBackendComponent._check_agent_health.__get__(self.component)
        self.component._deregister_agent = MagicMock()
        self.component.get_config = MagicMock()
        self.component.get_config.side_effect = lambda key, default=None: {
            "agent_health_check_ttl_seconds": 10,  # 10 seconds
            "agent_health_check_interval_seconds": 5
        }.get(key, default)
        
        # Add a third agent
        agent_card3 = AgentCard(
            name="agent3",
            description="Test Agent 3",
            capabilities=[],
            skills=[],
            version="1.0.0"
        )
        self.agent_registry.add_or_update_agent(agent_card3)
        
        # Manually modify the last_seen time for agent1 and agent3 to simulate expiration
        with patch.object(self.agent_registry, '_last_seen') as mock_last_seen:
            mock_last_seen.__getitem__.side_effect = lambda key: (
                time.time() - 20 if key in ["agent1", "agent3"] else time.time()
            )
            mock_last_seen.__contains__ = lambda self, key: key in ["agent1", "agent2", "agent3"]
            
            # Execute
            self.component._check_agent_health()
        
        # Verify
        self.assertEqual(self.component._deregister_agent.call_count, 2)
        self.component._deregister_agent.assert_any_call("agent1")
        self.component._deregister_agent.assert_any_call("agent3")
        
    def test_check_agent_health_disabled_by_config(self):
        """Test _check_agent_health when disabled by configuration."""
        # Set up
        self.component._check_agent_health = WebUIBackendComponent._check_agent_health.__get__(self.component)
        self.component._deregister_agent = MagicMock()
        self.component.get_config = MagicMock()
        self.component.get_config.side_effect = lambda key, default=None: {
            "agent_health_check_ttl_seconds": 0,  # Disabled
            "agent_health_check_interval_seconds": 0  # Disabled
        }.get(key, default)
        
        # Manually modify the last_seen time for all agents to simulate expiration
        with patch.object(self.agent_registry, '_last_seen') as mock_last_seen:
            mock_last_seen.__getitem__.side_effect = lambda key: time.time() - 9999  # Very old
            mock_last_seen.__contains__ = lambda self, key: key in ["agent1", "agent2"]
            
            # Execute
            self.component._check_agent_health()
        
        # Verify - no agents should be deregistered when health check is disabled
        self.component._deregister_agent.assert_not_called()


if __name__ == "__main__":
    unittest.main()