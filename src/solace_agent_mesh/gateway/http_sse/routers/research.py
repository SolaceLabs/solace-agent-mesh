"""
API Router for deep research plan verification responses.

Handles user responses to research plan verification requests
(start, cancel, edit steps) from the frontend.
"""

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel, Field

from ..dependencies import (
    get_user_id,
)
from solace_agent_mesh.shared.utils.types import UserId

router = APIRouter()
log = logging.getLogger(__name__)


class PlanResponsePayload(BaseModel):
    """Data model for the research plan response payload."""

    plan_id: str = Field(..., alias="planId", description="The unique plan verification ID")
    action: Literal["start", "cancel"] = Field(
        ..., description="User action: 'start' to proceed or 'cancel' to abort"
    )
    steps: Optional[List[str]] = Field(
        None, description="Optionally modified plan steps (if user edited them)"
    )


@router.post("/research/plan-response", tags=["Research"])
async def submit_plan_response(
    request: FastAPIRequest,
    payload: PlanResponsePayload,
    user_id: UserId = Depends(get_user_id),
):
    """
    Receive user's response to a research plan verification request.

    The frontend sends this when the user clicks Start, Cancel, or edits
    the plan steps. The response is stored in the shared cache for the
    deep research tool to pick up via polling.

    Args:
        payload: The plan response with action and optional modified steps
        user_id: The authenticated user ID
    """
    log_prefix = "[POST /api/v1/research/plan-response] "
    log.info(
        "%sUser %s responded to plan %s with action: %s",
        log_prefix,
        user_id,
        payload.plan_id,
        payload.action,
    )

    # Access the gateway component's cache service
    from ..dependencies import sac_component_instance

    if not sac_component_instance:
        log.error("%sNo component instance available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway component not initialized",
        )

    cache_service = getattr(sac_component_instance, "cache_service", None)
    if not cache_service:
        log.error("%sNo cache service available on component", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not available",
        )

    # Store the response in cache for the deep research tool to pick up
    cache_key = f"deep_research_plan_{payload.plan_id}"
    response_data = {
        "action": payload.action,
        "steps": payload.steps,
        "user_id": str(user_id),
    }

    try:
        cache_service.add_data(
            key=cache_key,
            value=response_data,
            expiry=120,  # 2 minute expiry (generous buffer)
            component=sac_component_instance,
        )
        log.info(
            "%sStored plan response in cache: key=%s, action=%s",
            log_prefix,
            cache_key,
            payload.action,
        )
    except Exception as e:
        log.error("%sError storing plan response in cache: %s", log_prefix, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store plan response",
        )

    return {"status": "ok", "plan_id": payload.plan_id, "action": payload.action}
