"""
API Router for starter card suggestions.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ....common.agent_registry import AgentRegistry
from ..dependencies import get_agent_registry, get_starter_suggestions_service
from ..services.starter_suggestions_service import StarterSuggestionsService

log = logging.getLogger(__name__)

router = APIRouter()

# URI for the SAM tools extension in agent capabilities
TOOLS_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools"


def _extract_agent_data(agent_registry: AgentRegistry) -> list[dict[str, Any]]:
    """
    Extract simplified agent data from the registry for the suggestions service.

    Returns a list of dicts with keys: name, description, tools.
    """
    agent_names = agent_registry.get_agent_names()
    agents_data = []

    for name in agent_names:
        agent = agent_registry.get_agent(name)
        if not agent:
            continue

        tools = []
        if agent.capabilities and agent.capabilities.extensions:
            for ext in agent.capabilities.extensions:
                if ext.uri == TOOLS_EXTENSION_URI and ext.params:
                    for tool in ext.params.get("tools", []):
                        if isinstance(tool, dict):
                            tools.append(
                                {
                                    "name": tool.get("name", ""),
                                    "description": tool.get("description", ""),
                                }
                            )

        agents_data.append(
            {
                "name": agent.name,
                "description": agent.description or "",
                "tools": tools,
            }
        )

    return agents_data


@router.get("/starter-suggestions")
async def get_starter_suggestions(
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    service: StarterSuggestionsService = Depends(get_starter_suggestions_service),
) -> dict[str, Any]:
    """
    Get LLM-generated starter card suggestions based on available agents.

    Returns contextual suggestions tailored to the available agent capabilities.
    Results are cached server-side to avoid repeated LLM calls.
    """
    log_prefix = "[GET /api/v1/starter-suggestions] "
    log.info("%sRequest received.", log_prefix)

    try:
        agents_data = _extract_agent_data(agent_registry)
        log.info(
            "%sExtracted data for %d agents.", log_prefix, len(agents_data)
        )

        suggestions = await service.generate_suggestions(agents_data)

        return {"categories": suggestions}

    except Exception as e:
        log.exception(
            "%sError generating starter suggestions: %s", log_prefix, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error generating starter suggestions.",
        ) from e
