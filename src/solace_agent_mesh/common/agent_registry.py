"""
Manages discovered A2A agents.
Consolidated from src/tools/common/agent_registry.py and src/tools/a2a_cli_client/agent_registry.py.
"""

from typing import List, Optional, Tuple

from a2a.types import AgentCard

from solace_agent_mesh.common.base_registry import BaseRegistry


class AgentRegistry(BaseRegistry):
    """Stores and manages discovered AgentCards with health tracking."""

    def __init__(self, on_agent_added=None, on_agent_removed=None):
        """
        Initialize the agent registry.

        Args:
            on_agent_added: Optional callback(agent_card) when a new agent is discovered
            on_agent_removed: Optional callback(agent_name) when an agent is removed
        """
        super().__init__("agent", on_agent_added, on_agent_removed)

    def set_on_agent_added_callback(self, callback):
        """Sets the callback function to be called when a new agent is added."""
        self.set_on_added_callback(callback)

    def set_on_agent_removed_callback(self, callback):
        """Sets the callback function to be called when an agent is removed."""
        self.set_on_removed_callback(callback)

    def add_or_update_agent(self, agent_card: AgentCard) -> bool:
        """Adds a new agent or updates an existing one."""
        return self.add_or_update(agent_card)

    def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Retrieves an agent card by name."""
        return self.get(agent_name)

    def get_agent_names(self) -> List[str]:
        """Returns a sorted list of discovered agent names."""
        return self.get_ids()

    def get_last_seen(self, agent_name: str) -> Optional[float]:
        """Returns the timestamp when the agent was last seen."""
        return super().get_last_seen(agent_name)

    def check_ttl_expired(self, agent_name: str, ttl_seconds: int) -> Tuple[bool, int]:
        """
        Checks if an agent's TTL has expired.

        Args:
            agent_name: The name of the agent to check
            ttl_seconds: The TTL in seconds

        Returns:
            A tuple of (is_expired, seconds_since_last_seen)
        """
        return super().check_ttl_expired(agent_name, ttl_seconds)

    def remove_agent(self, agent_name: str) -> bool:
        """Removes an agent from the registry."""
        return self.remove(agent_name)
