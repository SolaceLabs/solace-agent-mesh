"""
Service layer for handling agent-related operations, primarily interacting
with the AgentRegistry.
"""

from typing import List, Optional

from solace_ai_connector.common.log import log

from ....common.agent_registry import AgentRegistry
from ....common.types import AgentCard


class AgentService:
    """
    Provides methods for accessing information about discovered A2A agents.
    """

    def __init__(self, agent_registry: AgentRegistry):
        """
        Initializes the AgentService.

        Args:
            agent_registry: An instance of the shared AgentRegistry.
        """
        if not isinstance(agent_registry, AgentRegistry):
            raise TypeError("agent_registry must be an instance of AgentRegistry")
        self._agent_registry = agent_registry
        log.info("[AgentService] Initialized.")

    def get_all_agents(self) -> List[AgentCard]:
        """
        Retrieves all currently discovered and registered agent cards.

        Returns:
            A list of AgentCard objects.
        """
        log_prefix = "[AgentService.get_all_agents] "
        log.info("%sRetrieving all agents.", log_prefix)
        agent_names = self._agent_registry.get_agent_names()
        agents = []
        for name in agent_names:
            agent = self._agent_registry.get_agent(name)
            if agent:
                agents.append(agent)
            else:
                log.warning(
                    "%sAgent name '%s' found in list but not retrievable from registry.",
                    log_prefix,
                    name,
                )
        log.info("%sRetrieved %d agent cards.", log_prefix, len(agents))
        return agents

    def get_agent_by_name(self, agent_name: str) -> Optional[AgentCard]:
        """
        Retrieves a specific agent card by its name.

        Args:
            agent_name: The name of the agent to retrieve.

        Returns:
            The AgentCard object if found, otherwise None.
        """
        log_prefix = "[AgentService.get_agent_by_name] "
        log.info("%sRetrieving agent by name '%s'.", log_prefix, agent_name)
        agent = self._agent_registry.get_agent(agent_name)
        log.info("%sFound: %s", log_prefix, agent is not None)
        return agent
