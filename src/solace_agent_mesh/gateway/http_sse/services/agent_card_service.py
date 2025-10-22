"""
Service layer for handling agent-related operations, primarily interacting
with the AgentRegistry.
"""

from typing import List, Optional

import logging

log = logging.getLogger(__name__)

from ....common.agent_registry import AgentRegistry
from a2a.types import AgentCard


class AgentCardService:
    """
    Provides methods for accessing information about discovered A2A agents' cards.
    """

    def __init__(self, agent_registry: AgentRegistry):
        """
        Initializes the AgentCardService.

        Args:
            agent_registry: An instance of the shared AgentRegistry.
        """
        if not isinstance(agent_registry, AgentRegistry):
            raise TypeError("agent_registry must be an instance of AgentRegistry")
        self._agent_registry = agent_registry
        log.info("[AgentCardService] Initialized.")

    def get_all_agent_cards(self) -> List[AgentCard]:
        """
        Retrieves all currently discovered and registered agent cards.

        Returns:
            A list of AgentCard objects.
        """
        log_prefix = "[AgentCardService.get_all_agent_cards] "
        log.info("%sRetrieving all agent cards.", log_prefix)
        agent_names = self._agent_registry.get_agent_names()
        agent_cards = []
        for name in agent_names:
            agent_card = self._agent_registry.get_agent(name)
            if agent_card:
                agent_cards.append(agent_card)
            else:
                log.warning(
                    "%sAgent name '%s' found in list but not retrievable from registry.",
                    log_prefix,
                    name,
                )
        log.info("%sRetrieved %d agent cards.", log_prefix, len(agent_cards))
        return agent_cards

    def get_agent_card_by_name(self, agent_name: str) -> Optional[AgentCard]:
        """
        Retrieves a specific agent card by its name.

        Args:
            agent_name: The name of the agent to retrieve.

        Returns:
            The AgentCard object if found, otherwise None.
        """
        log_prefix = "[AgentCardService.get_agent_card_by_name] "
        log.info("%sRetrieving agent card by name '%s'.", log_prefix, agent_name)
        agent_card = self._agent_registry.get_agent(agent_name)
        log.info("%sFound: %s", log_prefix, agent_card is not None)
        return agent_card
