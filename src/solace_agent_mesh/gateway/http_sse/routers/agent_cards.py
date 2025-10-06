"""
API Router for agent discovery and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List

from solace_ai_connector.common.log import log

from ....common.agent_registry import AgentRegistry
from a2a.types import AgentCard
from ..dependencies import get_agent_registry, get_sac_component
from ..component import WebUIBackendComponent

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
        
@router.delete("/agentCards/{agent_name}", response_model=Dict[str, str])
async def deregister_agent(
    agent_name: str,
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    component: WebUIBackendComponent = Depends(get_sac_component),
):
    """
    Manually deregisters an agent from the registry.
    """
    log_prefix = f"[DELETE /api/v1/agentCards/{agent_name}] "
    log.info("%sRequest received to deregister agent: %s", log_prefix, agent_name)
    
    try:
        # Check if the agent exists in the registry
        if not agent_registry.get_agent(agent_name):
            log.warning("%sAgent '%s' not found in registry", log_prefix, agent_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found in registry",
            )
        
        # Call the deregister_agent method in the component
        component._deregister_agent(agent_name)
        
        log.info("%sAgent '%s' successfully deregistered", log_prefix, agent_name)
        return {"status": "success", "message": f"Agent '{agent_name}' deregistered successfully"}
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        log.exception("%sError deregistering agent '%s': %s", log_prefix, agent_name, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error deregistering agent: {str(e)}",
        )
