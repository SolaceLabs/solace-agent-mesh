"""
API Router for the modern, asynchronous v2 endpoints.
"""

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
    Response,
    File,
    UploadFile,
)
from typing import List
from pydantic import BaseModel
from typing import Any

from solace_ai_connector.common.log import log
from ..dependencies import get_sac_component
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..component import RestGatewayComponent

router = APIRouter()


class TaskResponse(BaseModel):
    taskId: str


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a Task Asynchronously",
)
async def submit_task(
    request: Request,
    agent_name: str = Form(...),
    prompt: str = Form(...),
    files: List[UploadFile] = File([]),
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Submits a task to an agent asynchronously.

    The gateway immediately returns a `taskId`. The client must then poll the
    `GET /api/v2/tasks/{taskId}` endpoint to check the status and retrieve the
    final result.
    """
    log_prefix = "[POST /api/v2/tasks] "
    log.info("%sReceived request for agent: %s", log_prefix, agent_name)

    user_identity = await component.authenticate_and_enrich_user(request)
    if not user_identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed."
        )

    try:
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
            api_version="v2",
        )

        log.info("%sTask submitted successfully. TaskID: %s", log_prefix, task_id)
        return TaskResponse(taskId=task_id)

    except Exception as e:
        log.exception("%sUnexpected error submitting task: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected server error: {e}",
        )


@router.get("/tasks/{taskId}", response_model=Any, summary="Poll for Task Result")
async def get_task_result(
    taskId: str,
    component: "RestGatewayComponent" = Depends(get_sac_component),
):
    """
    Polls for the result of a previously submitted task.

    - **Returns 202 Accepted**: If the task is still processing.
    - **Returns 200 OK**: If the task is complete. The body will contain the final `Task` object, which includes the status, result, and any generated artifacts.
    """
    log_prefix = f"[GET /api/v2/tasks/{taskId}] "
    log.info("%sPolling for task result.", log_prefix)

    result = component.result_cache.get(taskId)

    if result:
        log.info("%sFound completed task result in cache.", log_prefix)
        component.result_cache.delete(taskId)
        return result
    else:
        log.info("%sTask not yet complete. Returning 202.", log_prefix)
        return Response(status_code=status.HTTP_202_ACCEPTED)
