"""
API Router for agent discovery.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from solace_ai_connector.common.log import log

from ....common.agent_registry import AgentRegistry
from a2a.types import AgentCard
from ..dependencies import get_agent_registry

router = APIRouter()


@router.get("/agentCards", response_model=List[AgentCard])
async def get_discovered_agent_cards(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
):
    """
    Retrieves a list of all currently discovered A2A agents' cards.
    """
    log_prefix = "[GET /api/v1/agentCards] "
    log.info("%sRequest received.", log_prefix)
    try:
        agent_names = agent_registry.get_agent_names()
        agents = [
            agent_registry.get_agent(name)
            for name in agent_names
            if agent_registry.get_agent(name)
        ]

        log.info("%sReturning %d discovered agent cards.", log_prefix, len(agents))
        return agents
    except Exception as e:
        log.exception("%sError retrieving discovered agent cards: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving agent list.",
        )
