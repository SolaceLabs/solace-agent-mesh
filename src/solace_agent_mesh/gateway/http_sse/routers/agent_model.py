"""
API Router for retrieving agent model configurations.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict

from ....common.agent_registry import AgentRegistry
from ..dependencies import get_agent_registry, get_user_config

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agents/{agent_name}/model")
async def get_agent_model_config(
    agent_name: str,
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    user_config: Dict[str, Any] = Depends(get_user_config),
):
    """
    Retrieves the model configuration for a specific agent.
    
    This endpoint returns the model name (e.g., "openai/vertex-claude-4-5-sonnet")
    that the agent is configured to use. This is useful for determining context
    window limits and other model-specific parameters.
    
    Args:
        agent_name: The name of the agent (e.g., "OrchestratorAgent")
        agent_registry: The agent registry dependency
        user_config: The user configuration dependency
        
    Returns:
        A dictionary containing the model configuration with the model name
        
    Raises:
        HTTPException: 404 if agent not found, 403 if access denied, 500 for other errors
    """
    log_prefix = f"[GET /api/v1/agents/{agent_name}/model] "
    log.info("%sRequest received.", log_prefix)
    
    try:
        # Get the agent from the registry
        agent_card = agent_registry.get_agent(agent_name)
        
        if not agent_card:
            log.warning(
                "%sAgent '%s' not found in registry.",
                log_prefix,
                agent_name,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{agent_name}' not found.",
            )
        
        # Check user permissions for this agent
        from ....common.middleware.registry import MiddlewareRegistry
        
        config_resolver = MiddlewareRegistry.get_config_resolver()
        operation_spec = {
            "operation_type": "agent_access",
            "target_agent": agent_name,
        }
        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, {"source": "agent_model_endpoint"}
        )
        
        if not validation_result.get("valid", False):
            log.warning(
                "%sAccess denied for agent '%s'. Required scopes: %s",
                log_prefix,
                agent_name,
                validation_result.get("required_scopes", []),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to agent '{agent_name}'.",
            )
        
        # Extract model configuration from agent card metadata
        # The model configuration is typically stored in the agent card's metadata
        model_name = None
        
        if agent_card.metadata:
            # Try to get model from metadata
            model_name = agent_card.metadata.get("model")
            
            # If model is a dict (full config), extract the model name
            if isinstance(model_name, dict):
                model_name = model_name.get("model") or model_name.get("name")
        
        if not model_name:
            log.warning(
                "%sNo model configuration found for agent '%s'.",
                log_prefix,
                agent_name,
            )
            # Return a response indicating no model config is available
            return {
                "agent_name": agent_name,
                "model": None,
                "message": "No model configuration available for this agent.",
            }
        
        log.info(
            "%sReturning model configuration for agent '%s': %s",
            log_prefix,
            agent_name,
            model_name,
        )
        
        return {
            "agentName": agent_name,
            "model": model_name,
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        log.exception(
            "%sError retrieving model configuration for agent '%s': %s",
            log_prefix,
            agent_name,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving agent model configuration.",
        )