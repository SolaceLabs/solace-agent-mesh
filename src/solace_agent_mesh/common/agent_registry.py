"""
Manages discovered A2A agents.
Consolidated from src/tools/common/agent_registry.py and src/tools/a2a_cli_client/agent_registry.py.
"""

import threading
import time
from typing import Dict, List, Optional

from a2a.types import AgentCard


class AgentRegistry:
    """Stores and manages discovered AgentCards with health tracking."""

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._last_seen: Dict[str, float] = {}  # Timestamp of last agent card received
        self._retry_counts: Dict[str, int] = {}  # Track retry attempts
        self._lock = threading.Lock()

    def add_or_update_agent(self, agent_card: AgentCard):
        """Adds a new agent or updates an existing one."""
        from solace_ai_connector.common.log import log
        
        if not agent_card or not agent_card.name:
            log.warning("Attempted to register agent with invalid agent card or missing name")
            return False

        with self._lock:
            is_new = agent_card.name not in self._agents
            current_time = time.time()
            
            # Store the agent information
            self._agents[agent_card.name] = agent_card
            self._last_seen[agent_card.name] = current_time
            
            # Get previous retry count for logging (if any)
            previous_retry_count = self._retry_counts.get(agent_card.name, 0)
            
            # Reset retry count on update
            self._retry_counts[agent_card.name] = 0
            
            if is_new:
                log.info(
                    "AGENT REGISTRATION: New agent '%s' registered in registry. "
                    "Timestamp: %s",
                    agent_card.name,
                    current_time
                )
                
                # Log agent capabilities at debug level
                if hasattr(agent_card, 'capabilities') and agent_card.capabilities:
                    log.debug(
                        "Agent '%s' capabilities: %s",
                        agent_card.name,
                        agent_card.capabilities.model_dump() if hasattr(agent_card.capabilities, 'model_dump') else str(agent_card.capabilities)
                    )
            else:
                if previous_retry_count > 0:
                    log.info(
                        "AGENT HEALTH RECOVERY: Agent '%s' has reconnected. "
                        "Previous retry count: %d, now reset to 0. "
                        "Timestamp: %s",
                        agent_card.name,
                        previous_retry_count,
                        current_time
                    )
                else:
                    log.debug(
                        "Agent '%s' heartbeat received. Last seen timestamp updated to %s",
                        agent_card.name,
                        current_time
                    )
                    
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
            
    def increment_retry_count(self, agent_name: str) -> int:
        """Increments and returns the retry count for an agent."""
        from solace_ai_connector.common.log import log
        
        with self._lock:
            if agent_name in self._retry_counts:
                self._retry_counts[agent_name] += 1
                current_count = self._retry_counts[agent_name]
                
                # Get the last seen timestamp for logging
                last_seen_time = self._last_seen.get(agent_name)
                current_time = time.time()
                time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else "unknown"
                
                # Log the retry count increment with severity based on count
                if current_count >= 20:
                    log.warning(
                        "AGENT HEALTH CRITICAL: Agent '%s' retry count increased to %d/%d. "
                        "Last seen: %s seconds ago",
                        agent_name,
                        current_count,
                        30,  # Default max retries
                        time_since_last_seen
                    )
                elif current_count >= 10:
                    log.warning(
                        "AGENT HEALTH WARNING: Agent '%s' retry count increased to %d/%d. "
                        "Last seen: %s seconds ago",
                        agent_name,
                        current_count,
                        30,  # Default max retries
                        time_since_last_seen
                    )
                else:
                    log.info(
                        "AGENT HEALTH CHECK: Agent '%s' retry count increased to %d/%d. "
                        "Last seen: %s seconds ago",
                        agent_name,
                        current_count,
                        30,  # Default max retries
                        time_since_last_seen
                    )
                
                return current_count
            
            log.debug("Attempted to increment retry count for non-existent agent '%s'", agent_name)
            return 0
            
    def remove_agent(self, agent_name: str) -> bool:
        """Removes an agent from the registry."""
        from solace_ai_connector.common.log import log
        
        with self._lock:
            if agent_name in self._agents:
                # Get agent details before removal for logging
                last_seen_time = self._last_seen.get(agent_name)
                retry_count = self._retry_counts.get(agent_name)
                current_time = time.time()
                time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else "unknown"
                
                # Log detailed information about the agent being removed
                log.warning(
                    "AGENT DE-REGISTRATION: Removing agent '%s' from registry. "
                    "Last seen: %s seconds ago, Final retry count: %d",
                    agent_name,
                    time_since_last_seen,
                    retry_count or 0
                )
                
                # Remove the agent from all tracking dictionaries
                del self._agents[agent_name]
                if agent_name in self._last_seen:
                    del self._last_seen[agent_name]
                if agent_name in self._retry_counts:
                    del self._retry_counts[agent_name]
                
                log.info("Agent '%s' successfully removed from registry", agent_name)
                return True
            else:
                log.debug("Attempted to remove non-existent agent '%s' from registry", agent_name)
                return False

    def clear(self):
        """Clears all registered agents."""
        with self._lock:
            self._agents.clear()
            self._last_seen.clear()
            self._retry_counts.clear()
