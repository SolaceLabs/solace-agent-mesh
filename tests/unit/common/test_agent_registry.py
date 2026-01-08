"""
Unit tests for common/agent_registry.py
Tests the AgentRegistry class for managing discovered A2A agents.
"""

import pytest
import time
import threading
from unittest.mock import MagicMock
from a2a.types import AgentCard, AgentSkill

from solace_agent_mesh.common.agent_registry import AgentRegistry


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


@pytest.fixture
def agent_registry():
    """Create a fresh AgentRegistry instance for each test."""
    return AgentRegistry()


class TestAgentRegistryBasicOperations:
    """Test basic CRUD operations on AgentRegistry."""

    def test_add_new_agent(self, agent_registry, sample_agent_card):
        """Test adding a new agent to the registry."""
        is_new = agent_registry.add_or_update_agent(sample_agent_card)
        
        assert is_new is True
        assert "TestAgent" in agent_registry.get_agent_names()
        
        retrieved = agent_registry.get_agent("TestAgent")
        assert retrieved is not None
        assert retrieved.name == "TestAgent"
        assert retrieved.description == "A test agent"

    def test_update_existing_agent(self, agent_registry, sample_agent_card):
        """Test updating an existing agent in the registry."""
        # Add agent first
        is_new_first = agent_registry.add_or_update_agent(sample_agent_card)
        assert is_new_first is True
        
        # Update the same agent
        updated_card = sample_agent_card.model_copy(
            update={"description": "Updated description"}
        )
        is_new_second = agent_registry.add_or_update_agent(updated_card)
        
        assert is_new_second is False
        retrieved = agent_registry.get_agent("TestAgent")
        assert retrieved.description == "Updated description"

    def test_add_invalid_agent_card(self, agent_registry):
        """Test adding an invalid agent card (None or missing name)."""
        # Test with None
        result = agent_registry.add_or_update_agent(None)
        assert result is False
        
        # Test with agent card missing name
        invalid_card = MagicMock()
        invalid_card.name = None
        result = agent_registry.add_or_update_agent(invalid_card)
        assert result is False

    def test_get_nonexistent_agent(self, agent_registry):
        """Test retrieving an agent that doesn't exist."""
        result = agent_registry.get_agent("NonExistentAgent")
        assert result is None

    def test_get_agent_names_empty(self, agent_registry):
        """Test getting agent names from empty registry."""
        names = agent_registry.get_agent_names()
        assert names == []

    def test_get_agent_names_sorted(self, agent_registry):
        """Test that agent names are returned in sorted order."""
        agents = [
            AgentCard(
                name=name,
                description=f"Agent {name}",
                url=f"https://{name}.example.com",
                version="1.0.0",
                protocolVersion="0.3.0",
                capabilities={"streaming": True},
                defaultInputModes=["text/plain"],
                defaultOutputModes=["text/plain"],
                skills=[],
            )
            for name in ["Zebra", "Alpha", "Mike", "Charlie"]
        ]
        
        for agent in agents:
            agent_registry.add_or_update_agent(agent)
        
        names = agent_registry.get_agent_names()
        assert names == ["Alpha", "Charlie", "Mike", "Zebra"]

    def test_remove_existing_agent(self, agent_registry, sample_agent_card):
        """Test removing an existing agent from the registry."""
        agent_registry.add_or_update_agent(sample_agent_card)
        
        result = agent_registry.remove_agent("TestAgent")
        assert result is True
        
        # Verify agent is removed
        assert agent_registry.get_agent("TestAgent") is None
        assert "TestAgent" not in agent_registry.get_agent_names()

    def test_remove_nonexistent_agent(self, agent_registry):
        """Test removing an agent that doesn't exist."""
        result = agent_registry.remove_agent("NonExistentAgent")
        assert result is False

    def test_clear_registry(self, agent_registry, sample_agent_card):
        """Test clearing all agents from the registry."""
        # Add multiple agents
        for i in range(3):
            card = sample_agent_card.model_copy(
                update={"name": f"TestAgent{i}"}
            )
            agent_registry.add_or_update_agent(card)
        
        assert len(agent_registry.get_agent_names()) == 3
        
        agent_registry.clear()
        
        assert len(agent_registry.get_agent_names()) == 0
        assert agent_registry.get_agent("TestAgent0") is None


class TestAgentRegistryHealthTracking:
    """Test health tracking and TTL functionality."""

    def test_last_seen_timestamp_on_add(self, agent_registry, sample_agent_card):
        """Test that last_seen timestamp is set when adding an agent."""
        before_time = time.time()
        agent_registry.add_or_update_agent(sample_agent_card)
        after_time = time.time()
        
        last_seen = agent_registry.get_last_seen("TestAgent")
        assert last_seen is not None
        assert before_time <= last_seen <= after_time

    def test_last_seen_timestamp_on_update(self, agent_registry, sample_agent_card):
        """Test that last_seen timestamp is updated when updating an agent."""
        agent_registry.add_or_update_agent(sample_agent_card)
        first_seen = agent_registry.get_last_seen("TestAgent")
        
        time.sleep(0.1)  # Small delay to ensure timestamp difference
        
        updated_card = sample_agent_card.model_copy(
            update={"description": "Updated"}
        )
        agent_registry.add_or_update_agent(updated_card)
        second_seen = agent_registry.get_last_seen("TestAgent")
        
        assert second_seen > first_seen

    def test_get_last_seen_nonexistent_agent(self, agent_registry):
        """Test getting last_seen for an agent that doesn't exist."""
        result = agent_registry.get_last_seen("NonExistentAgent")
        assert result is None

    def test_check_ttl_not_expired(self, agent_registry, sample_agent_card):
        """Test checking TTL for an agent that hasn't expired."""
        agent_registry.add_or_update_agent(sample_agent_card)
        
        is_expired, seconds_since = agent_registry.check_ttl_expired(
            "TestAgent", ttl_seconds=60
        )
        
        assert is_expired is False
        assert seconds_since < 60

    def test_check_ttl_expired(self, agent_registry, sample_agent_card):
        """Test checking TTL for an agent that has expired."""
        agent_registry.add_or_update_agent(sample_agent_card)
        
        # Manually set last_seen to past time
        agent_registry._last_seen["TestAgent"] = time.time() - 100
        
        is_expired, seconds_since = agent_registry.check_ttl_expired(
            "TestAgent", ttl_seconds=60
        )
        
        assert is_expired is True
        assert seconds_since > 60

    def test_check_ttl_nonexistent_agent(self, agent_registry):
        """Test checking TTL for an agent that doesn't exist."""
        is_expired, seconds_since = agent_registry.check_ttl_expired(
            "NonExistentAgent", ttl_seconds=60
        )
        
        assert is_expired is False
        assert seconds_since == 0


class TestAgentRegistryThreadSafety:
    """Test thread safety of AgentRegistry operations."""

    def test_concurrent_add_operations(self, agent_registry):
        """Test concurrent add operations from multiple threads."""
        num_threads = 10
        agents_per_thread = 5
        
        def add_agents(thread_id):
            for i in range(agents_per_thread):
                card = AgentCard(
                    name=f"Agent_{thread_id}_{i}",
                    description=f"Agent from thread {thread_id}",
                    url=f"https://agent{thread_id}-{i}.example.com",
                    version="1.0.0",
                    protocolVersion="0.3.0",
                    capabilities={"streaming": True},
                    defaultInputModes=["text/plain"],
                    defaultOutputModes=["text/plain"],
                    skills=[],
                )
                agent_registry.add_or_update_agent(card)
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_agents, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all agents were added
        names = agent_registry.get_agent_names()
        assert len(names) == num_threads * agents_per_thread

    def test_concurrent_read_write_operations(self, agent_registry, sample_agent_card):
        """Test concurrent read and write operations."""
        agent_registry.add_or_update_agent(sample_agent_card)
        
        results = {"reads": 0, "writes": 0}
        lock = threading.Lock()
        
        def read_agent():
            for _ in range(100):
                agent = agent_registry.get_agent("TestAgent")
                if agent:
                    with lock:
                        results["reads"] += 1
        
        def write_agent():
            for i in range(100):
                updated_card = sample_agent_card.model_copy(
                    update={"description": f"Update {i}"}
                )
                agent_registry.add_or_update_agent(updated_card)
                with lock:
                    results["writes"] += 1
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=read_agent))
            threads.append(threading.Thread(target=write_agent))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify operations completed without errors
        assert results["reads"] == 500
        assert results["writes"] == 500
        
        # Verify agent still exists and is valid
        final_agent = agent_registry.get_agent("TestAgent")
        assert final_agent is not None
        assert final_agent.name == "TestAgent"

    def test_concurrent_remove_operations(self, agent_registry):
        """Test concurrent remove operations."""
        # Add multiple agents
        for i in range(10):
            card = AgentCard(
                name=f"Agent_{i}",
                description=f"Agent {i}",
                url=f"https://agent{i}.example.com",
                version="1.0.0",
                protocolVersion="0.3.0",
                capabilities={"streaming": True},
                defaultInputModes=["text/plain"],
                defaultOutputModes=["text/plain"],
                skills=[],
            )
            agent_registry.add_or_update_agent(card)
        
        def remove_agents(start_idx, end_idx):
            for i in range(start_idx, end_idx):
                agent_registry.remove_agent(f"Agent_{i}")
        
        threads = [
            threading.Thread(target=remove_agents, args=(0, 5)),
            threading.Thread(target=remove_agents, args=(5, 10)),
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all agents were removed
        assert len(agent_registry.get_agent_names()) == 0


class TestAgentRegistryEdgeCases:
    """Test edge cases and error conditions."""

    def test_add_agent_with_empty_name(self, agent_registry):
        """Test adding an agent with an empty name."""
        card = AgentCard(
            name="",
            description="Agent with empty name",
            url="https://test.example.com",
            version="1.0.0",
            protocolVersion="0.3.0",
            capabilities={"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"],
            skills=[],
        )
        
        result = agent_registry.add_or_update_agent(card)
        assert result is False

    def test_multiple_updates_preserve_last_seen(self, agent_registry, sample_agent_card):
        """Test that multiple rapid updates preserve last_seen tracking."""
        timestamps = []
        
        for i in range(5):
            agent_registry.add_or_update_agent(sample_agent_card)
            timestamps.append(agent_registry.get_last_seen("TestAgent"))
            time.sleep(0.05)
        
        # Verify timestamps are monotonically increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1]

    def test_remove_agent_clears_last_seen(self, agent_registry, sample_agent_card):
        """Test that removing an agent also clears its last_seen timestamp."""
        agent_registry.add_or_update_agent(sample_agent_card)
        assert agent_registry.get_last_seen("TestAgent") is not None
        
        agent_registry.remove_agent("TestAgent")
        assert agent_registry.get_last_seen("TestAgent") is None

    def test_clear_removes_all_tracking_data(self, agent_registry, sample_agent_card):
        """Test that clear() removes both agents and tracking data."""
        # Add multiple agents
        for i in range(3):
            card = sample_agent_card.model_copy(update={"name": f"Agent{i}"})
            agent_registry.add_or_update_agent(card)
        
        # Verify tracking data exists
        for i in range(3):
            assert agent_registry.get_last_seen(f"Agent{i}") is not None
        
        agent_registry.clear()
        
        # Verify all tracking data is cleared
        for i in range(3):
            assert agent_registry.get_last_seen(f"Agent{i}") is None