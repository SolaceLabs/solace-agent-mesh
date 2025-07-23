"""
API Router for agent discovery.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from solace_ai_connector.common.log import log

from ....common.agent_registry import AgentRegistry
from ....common.types import AgentCard
from ....gateway.http_sse.dependencies import get_agent_registry

router = APIRouter()


@router.get("/agents", response_model=List[AgentCard])
async def get_discovered_agents(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
):
    """
    Retrieves a list of all currently discovered A2A agents.
    """
    log_prefix = "[GET /api/v1/agents] "
    log.info("%sRequest received.", log_prefix)
    try:
        agent_names = agent_registry.get_agent_names()
        agents = [
            agent_registry.get_agent(name)
            for name in agent_names
            if agent_registry.get_agent(name)
        ]

        log.info("%sReturning %d discovered agents.", log_prefix, len(agents))
        return agents
    except Exception as e:
        log.exception("%sError retrieving discovered agents: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving agent list.",
        )
