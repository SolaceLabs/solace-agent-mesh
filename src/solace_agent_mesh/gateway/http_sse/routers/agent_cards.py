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

# URI for the SAM tools extension in agent capabilities
TOOLS_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools"


def _filter_tools_by_user_scopes(
    tools: List[Dict[str, Any]],
    user_config: Dict[str, Any],
    config_resolver: Any,
    agent_name: str,
    log_prefix: str,
) -> List[Dict[str, Any]]:
    """
    Filter tools based on user's scopes.

    Args:
        tools: List of tool dictionaries from the agent card extension
        user_config: User configuration including scopes
        config_resolver: Config resolver for scope validation
        agent_name: Name of the agent (for logging)
        log_prefix: Logging prefix

    Returns:
        List of tools the user has access to
    """
    if not tools:
        return tools

    filtered_tools = []
    for tool in tools:
        # A2A spec uses camelCase for JSON serialization (requiredScopes)
        tool_scopes = tool.get("requiredScopes", [])
        if not tool_scopes:
            # No scopes required, tool is accessible to all
            filtered_tools.append(tool)
            continue

        # Validate tool access using config resolver
        operation_spec = {
            "operation_type": "tool_access",
            "target_agent": agent_name,
            "target_tool": tool.get("name"),
            "required_scopes": tool_scopes,
        }
        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, {"source": "agent_cards_endpoint"}
        )
        if validation_result.get("valid", False):
            filtered_tools.append(tool)
        else:
            log.debug(
                "%sTool '%s' in agent '%s' filtered out. Required scopes: %s",
                log_prefix,
                tool.get("name"),
                agent_name,
                tool_scopes,
            )

    return filtered_tools


def _filter_agent_tools(
    agent: AgentCard,
    user_config: Dict[str, Any],
    config_resolver: Any,
    log_prefix: str,
) -> AgentCard:
    """
    Filter tools within an agent card based on user's scopes.

    Args:
        agent: The agent card to filter
        user_config: User configuration including scopes
        config_resolver: Config resolver for scope validation
        log_prefix: Logging prefix

    Returns:
        Agent card with filtered tools
    """
    if not agent.capabilities or not agent.capabilities.extensions:
        return agent

    # Find the tools extension
    tools_ext_index = None
    for i, ext in enumerate(agent.capabilities.extensions):
        if ext.uri == TOOLS_EXTENSION_URI:
            tools_ext_index = i
            break

    if tools_ext_index is None:
        return agent

    tools_ext = agent.capabilities.extensions[tools_ext_index]
    tools = tools_ext.params.get("tools", []) if tools_ext.params else []

    if not tools:
        return agent

    # Filter tools by user scopes
    filtered_tools = _filter_tools_by_user_scopes(
        tools, user_config, config_resolver, agent.name, log_prefix
    )

    # If no tools were filtered out, return the original agent
    if len(filtered_tools) == len(tools):
        return agent

    # Create a modified copy of the agent with filtered tools
    # Use model_copy (Pydantic v2) or copy (Pydantic v1) for deep copy
    try:
        agent_copy = agent.model_copy(deep=True)
    except AttributeError:
        # Fallback for older Pydantic versions
        agent_copy = agent.copy(deep=True)

    # Update the tools in the copy
    agent_copy.capabilities.extensions[tools_ext_index].params["tools"] = filtered_tools

    log.debug(
        "%sFiltered tools for agent '%s': %d/%d tools accessible",
        log_prefix,
        agent.name,
        len(filtered_tools),
        len(tools),
    )

    return agent_copy


@router.get("/agentCards", response_model=List[AgentCard])
async def get_discovered_agent_cards(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    user_config: Dict[str, Any] = Depends(get_user_config),
):
    """
    Retrieves a list of discovered A2A agents filtered by user permissions.

    Agents are filtered based on the user's agent:*:delegate scopes to ensure
    users only see agents they have permission to access. Additionally, tools
    within each agent are filtered based on their required_scopes to ensure
    users only see tools they have permission to use.
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
            "%sReturning %d/%d agents after agent-level filtering.",
            log_prefix,
            len(filtered_agents),
            len(all_agents),
        )

        # Filter tools within each agent based on user's scopes
        agents_with_filtered_tools = [
            _filter_agent_tools(agent, user_config, config_resolver, log_prefix)
            for agent in filtered_agents
        ]

        return agents_with_filtered_tools
    except Exception as e:
        log.exception("%sError retrieving discovered agent cards: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving agent list.",
        )
