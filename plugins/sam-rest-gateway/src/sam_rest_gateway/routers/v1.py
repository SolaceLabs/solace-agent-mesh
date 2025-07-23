"""
API Router for the legacy, synchronous v1 endpoints.
"""

import asyncio
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
)

from solace_ai_connector.common.log import log
from ..dependencies import get_sac_component
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import RestGatewayComponent

router = APIRouter()


from fastapi import File, UploadFile
from typing import List


@router.post(
    "/invoke", response_model=Any, summary="Invoke Agent (Synchronous, Deprecated)"
)
async def invoke_task_sync(
    request: Request,
    agent_name: str = Form(...),
    prompt: str = Form(...),
    files: List[UploadFile] = File([]),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Submits a task to an agent and waits synchronously for the result.

    **DEPRECATED**: This endpoint is provided for backward compatibility only.
    It holds the HTTP connection open and is subject to timeouts defined by
    `sync_mode_timeout_seconds`. For new integrations, please use the
    asynchronous v2 API (`/api/v2/tasks`).
    """
    log_prefix = "[POST /api/v1/invoke] "
    log.info("%sReceived synchronous request for agent: %s", log_prefix, agent_name)

    user_identity = await component.authenticate_and_enrich_user(request)
    if not user_identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed."
        )

    external_event_data = {
        "agent_name": agent_name,
        "prompt": prompt,
        "files": files,
        "user_identity": user_identity,
    }

    target_agent, a2a_parts, external_req_ctx = (
        await component._translate_external_input(external_event_data)
    )

    task_id = await component.submit_a2a_task(
        target_agent_name=target_agent,
        a2a_parts=a2a_parts,
        external_request_context=external_req_ctx,
        user_identity=user_identity,
        is_streaming=True,
        api_version="v1",
    )

    log.info(
        "%sTask %s submitted. Waiting for synchronous result...", log_prefix, task_id
    )

    completion_event = asyncio.Event()
    with component.sync_wait_lock:
        component.sync_wait_events[task_id] = {
            "event": completion_event,
            "result": None,
        }

    try:
        timeout = component.get_config("sync_mode_timeout_seconds", 60)
        await asyncio.wait_for(completion_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning(
            "%sTask %s timed out after %d seconds.", log_prefix, task_id, timeout
        )
        with component.sync_wait_lock:
            component.sync_wait_events.pop(task_id, None)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"The agent task did not complete within the {timeout} second timeout.",
        )
    finally:
        with component.sync_wait_lock:
            wait_context = component.sync_wait_events.pop(task_id, None)

    if wait_context and wait_context.get("result"):
        log.info("%sTask %s completed. Returning result.", log_prefix, task_id)
        return wait_context["result"]
    else:
        log.error(
            "%sTask %s event was set, but no result was found.", log_prefix, task_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task finished but result could not be retrieved.",
        )
