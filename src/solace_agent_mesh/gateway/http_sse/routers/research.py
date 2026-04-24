"""
API Router for deep research plan verification responses.

Handles user responses to research plan verification requests (start, cancel,
edit steps) from the frontend by publishing a fire-and-forget control signal
on the SAM event bus. The deep-research tool running on the target agent has
an ``asyncio.Future`` waiting in its plan-waiter registry keyed by ``plan_id``;
the agent's event handler resolves that future when the signal arrives.

The endpoint returns ``202 Accepted`` as soon as the signal is published; the
frontend relies on the existing SSE stream (research progress, or a stale
signal if the plan is no longer being awaited) for the actual outcome.
"""

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from solace_agent_mesh.common.a2a.protocol import get_sam_events_topic
from solace_agent_mesh.shared.utils.types import UserId

from ..dependencies import get_user_id

router = APIRouter()
log = logging.getLogger(__name__)


class PlanResponsePayload(BaseModel):
    """Data model for the research plan response payload."""

    plan_id: str = Field(..., alias="planId", description="The unique plan verification ID")
    agent_name: str = Field(
        ...,
        alias="agentName",
        description=(
            "Name of the agent running the deep-research tool. Echoed from the "
            "plan signal; the gateway uses it to route the control message to "
            "the correct agent (important when research is delegated to a peer)."
        ),
    )
    action: Literal["start", "cancel"] = Field(
        ..., description="User action: 'start' to proceed or 'cancel' to abort"
    )
    steps: Optional[List[str]] = Field(
        None, description="Optionally modified plan steps (if user edited them)"
    )


@router.post(
    "/research/plan-response",
    tags=["Research"],
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_plan_response(
    payload: PlanResponsePayload,
    user_id: UserId = Depends(get_user_id),
):
    """
    Publish the user's plan response as a control signal on the SAM event bus.

    Returns 202 immediately - confirmation of the actual outcome (research
    starting, or the plan being stale/timed out) comes through the existing
    SSE stream.
    """
    log_prefix = "[POST /api/v1/research/plan-response] "

    # Defence-in-depth: get_user_id should never return empty for an
    # authenticated request, but a blank user_id would let one user's
    # response attempt to claim another user's plan on misconfiguration.
    if not user_id:
        log.error("%sMissing user_id on authenticated request", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not available",
        )

    from ..dependencies import sac_component_instance

    if not sac_component_instance:
        log.error("%sNo component instance available", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway component not initialized",
        )

    publish = getattr(sac_component_instance, "publish_a2a", None)
    if not callable(publish):
        log.error("%sGateway component does not support publish_a2a", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway publish transport not available",
        )

    namespace = sac_component_instance.get_config("namespace")
    if not namespace:
        log.error("%sGateway component has no namespace configured", log_prefix)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway namespace not configured",
        )

    topic = get_sam_events_topic(namespace, "deep_research", "plan_response")
    event_payload = {
        "event_type": "plan_response",
        "source_component": f"{sac_component_instance.gateway_id}_gateway"
        if hasattr(sac_component_instance, "gateway_id")
        else "http_sse_gateway",
        "data": {
            "plan_id": payload.plan_id,
            "agent_name": payload.agent_name,
            "user_id": str(user_id),
            "action": payload.action,
            "steps": payload.steps,
        },
    }

    log.info(
        "%sUser %s responded to plan %s (agent=%s) with action: %s",
        log_prefix,
        user_id,
        payload.plan_id,
        payload.agent_name,
        payload.action,
    )

    try:
        publish(topic=topic, payload=event_payload, user_properties={
            "clientId": getattr(sac_component_instance, "gateway_id", "http_sse_gateway"),
            "userId": str(user_id),
        })
    except Exception as e:
        log.error("%sFailed to publish plan response: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish plan response",
        )

    return {"status": "accepted", "plan_id": payload.plan_id, "action": payload.action}
