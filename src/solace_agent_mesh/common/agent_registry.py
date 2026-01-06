"""
Manages discovered A2A agents.
Consolidated from src/tools/common/agent_registry.py and src/tools/a2a_cli_client/agent_registry.py.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple
import logging

from a2a.types import AgentCard

log = logging.getLogger(__name__)


class AgentRegistry:
    """Stores and manages discovered AgentCards with health tracking."""

    def __init__(self, on_agent_added=None, on_agent_removed=None):
        self._agents: Dict[str, AgentCard] = {}
        self._last_seen: Dict[str, float] = {}  # Timestamp of last agent card received
        self._lock = threading.Lock()
        self._on_agent_added = on_agent_added
        self._on_agent_removed = on_agent_removed
    
    def set_on_agent_added_callback(self, callback):
        """Sets the callback function to be called when a new agent is added."""
        self._on_agent_added = callback
    
    def set_on_agent_removed_callback(self, callback):
        """Sets the callback function to be called when an agent is removed."""
        self._on_agent_removed = callback

    def add_or_update_agent(self, agent_card: AgentCard):
        """Adds a new agent or updates an existing one."""

        if not agent_card or not agent_card.name:
            log.warning("Attempted to register agent with invalid agent card or missing name")
            return False

        with self._lock:
            is_new = agent_card.name not in self._agents
            current_time = time.time()

            # Store the agent information
            self._agents[agent_card.name] = agent_card
            self._last_seen[agent_card.name] = current_time

        # Call callback OUTSIDE the lock to avoid deadlock
        if is_new and self._on_agent_added:
            try:
                self._on_agent_added(agent_card)
            except Exception as e:
                log.error(f"Error in agent added callback for {agent_card.name}: {e}", exc_info=True)

        return is_new

    def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """Retrieves an agent card by name."""
        with self._lock:
            return self._agents.get(agent_name)

    def get_agent_names(self) -> List[str]:
        """Returns a sorted list of discovered agent names."""
        with self._lock:
            return sorted(list(self._agents.keys()))
            
    def get_last_seen(self, agent_name: str) -> Optional[float]:
        """Returns the timestamp when the agent was last seen."""
        with self._lock:
            return self._last_seen.get(agent_name)
            
    def check_ttl_expired(self, agent_name: str, ttl_seconds: int) -> Tuple[bool, int]:
        """
        Checks if an agent's TTL has expired.
        
        Args:
            agent_name: The name of the agent to check
            ttl_seconds: The TTL in seconds
            
        Returns:
            A tuple of (is_expired, seconds_since_last_seen)
        """
        
        with self._lock:
            if agent_name not in self._last_seen:
                log.debug("Attempted to check TTL for non-existent agent '%s'", agent_name)
                return False, 0
                
            last_seen_time = self._last_seen.get(agent_name)
            current_time = time.time()
            time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else 0
            
            is_expired = time_since_last_seen > ttl_seconds
            
            if is_expired:
                log.warning(
                    "AGENT HEALTH CRITICAL: Agent '%s' TTL expired. "
                    "Last seen: %s seconds ago, TTL: %d seconds",
                    agent_name,
                    time_since_last_seen,
                    ttl_seconds
                )
            
            return is_expired, time_since_last_seen
            
    def remove_agent(self, agent_name: str) -> bool:
        """Removes an agent from the registry."""

        with self._lock:
            if agent_name in self._agents:
                # Get agent details before removal for logging
                last_seen_time = self._last_seen.get(agent_name)
                current_time = time.time()
                time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else "unknown"

                # Log detailed information about the agent being removed
                log.warning(
                    "AGENT DE-REGISTRATION: Removing agent '%s' from registry. "
                    "Last seen: %s seconds ago",
                    agent_name,
                    time_since_last_seen
                )

                # Remove the agent from all tracking dictionaries
                del self._agents[agent_name]
                if agent_name in self._last_seen:
                    del self._last_seen[agent_name]

                log.info("Agent '%s' successfully removed from registry", agent_name)
                removed = True
            else:
                log.debug("Attempted to remove non-existent agent '%s' from registry", agent_name)
                removed = False

        # Call callback OUTSIDE the lock to avoid deadlock
        if removed and self._on_agent_removed:
            try:
                self._on_agent_removed(agent_name)
            except Exception as e:
                log.error(f"Error in agent removed callback for {agent_name}: {e}", exc_info=True)

        return removed

    def clear(self):
        """Clears all registered agents."""
        with self._lock:
            self._agents.clear()
            self._last_seen.clear()
