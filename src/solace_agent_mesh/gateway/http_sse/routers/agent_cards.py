"""
API Router for agent discovery and management.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict, List

from ....common.agent_registry import AgentRegistry
from ....common.middleware.registry import MiddlewareRegistry
from a2a.types import AgentCard
from ..dependencies import get_agent_registry, get_user_config

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agentCards", response_model=List[AgentCard])
async def get_discovered_agent_cards(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    user_config: Dict[str, Any] = Depends(get_user_config),
):
    """
    Retrieves a list of discovered A2A agents filtered by user permissions.

    Agents are filtered based on the user's agent:*:delegate scopes to ensure
    users only see agents they have permission to access.
    """
    log_prefix = "[GET /api/v1/agentCards] "
    log.info("%sRequest received.", log_prefix)
    try:
        agent_names = agent_registry.get_agent_names()
        all_agents = [
            agent_registry.get_agent(name)
            for name in agent_names
            if agent_registry.get_agent(name)
        ]

        # Filter agents by user's access permissions
        config_resolver = MiddlewareRegistry.get_config_resolver()
        filtered_agents = []

        for agent in all_agents:
            operation_spec = {
                "operation_type": "agent_access",
                "target_agent": agent.name,
            }
            validation_result = config_resolver.validate_operation_config(
                user_config, operation_spec, {"source": "agent_cards_endpoint"}
            )
            if validation_result.get("valid", False):
                filtered_agents.append(agent)
            else:
                log.debug(
                    "%sAgent '%s' filtered out for user. Required scopes: %s",
                    log_prefix,
                    agent.name,
                    validation_result.get("required_scopes", []),
                )

        log.debug(
            "%sReturning %d/%d agents after filtering.",
            log_prefix,
            len(filtered_agents),
            len(all_agents),
        )
        return filtered_agents
    except Exception as e:
        log.exception("%sError retrieving discovered agent cards: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving agent list.",
        )
