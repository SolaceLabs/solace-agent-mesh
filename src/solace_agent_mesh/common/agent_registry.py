"""
Manages discovered A2A agents.
Consolidated from src/tools/common/agent_registry.py and src/tools/a2a_cli_client/agent_registry.py.
"""

import threading
from typing import Dict, List, Optional

from a2a.types import AgentCard


class AgentRegistry:
    """Stores and manages discovered AgentCards."""

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._lock = threading.Lock()

    def add_or_update_agent(self, agent_card: AgentCard):
        """Adds a new agent or updates an existing one."""
        if not agent_card or not agent_card.name:
            return

        with self._lock:
            is_new = agent_card.name not in self._agents
            self._agents[agent_card.name] = agent_card
            return is_new

    def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Retrieves an agent card by name."""
        with self._lock:
            return self._agents.get(agent_name)

    def get_agent_names(self) -> List[str]:
        """Returns a sorted list of discovered agent names."""
        with self._lock:
            return sorted(list(self._agents.keys()))

    def clear(self):
        """Clears all registered agents."""
        with self._lock:
            self._agents.clear()
