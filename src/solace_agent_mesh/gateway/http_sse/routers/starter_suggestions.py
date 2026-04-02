"""
API Router for starter card suggestions.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ....common.agent_registry import AgentRegistry
from ....shared.api import get_current_user
from ..dependencies import get_agent_registry, get_starter_suggestions_service
from ..services.starter_suggestions_service import (
    StarterSuggestionsService,
    extract_agent_data,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/starter-suggestions")
async def get_starter_suggestions(
    user: dict = Depends(get_current_user),
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
        agents_data = extract_agent_data(agent_registry)
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
