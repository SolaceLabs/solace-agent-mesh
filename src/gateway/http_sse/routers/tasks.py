"""
API Router for submitting and managing tasks to agents.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request as FastAPIRequest,
    status,
    Form,
    File,
    UploadFile,
)
from pydantic import BaseModel, Field
from typing import List

from solace_ai_connector.common.log import log

from ....gateway.http_sse.session_manager import SessionManager
from ....gateway.http_sse.services.task_service import TaskService

from ....common.types import (
    JSONRPCResponse,
    InternalError,
    InvalidRequestError,
)

from ....gateway.http_sse.dependencies import (
    get_session_manager,
    get_sac_component,
    get_task_service,
)
from ....gateway.http_sse.routers.users import get_current_user

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()


class CancelTaskApiPayload(BaseModel):
    """Request body for the task cancellation endpoint."""

    agent_name: str = Field(
        ..., description="The name of the agent currently handling the task."
    )
    task_id: str = Field(..., description="The ID of the task to cancel.")


@router.post("/send", response_model=JSONRPCResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: List[UploadFile] = File([]),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Submits a non-streaming task request to the specified agent.
    Accepts multipart/form-data.
    """
    log_prefix = "[POST /api/v1/tasks/send] "
    log.info("%sReceived request for agent: %s", log_prefix, agent_name)

    try:
        user_identity = await component.authenticate_and_enrich_user(request)
        if user_identity is None:
            log.warning("%sUser authentication failed. Denying request.", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication failed or identity not found.",
            )
        log.info(
            "%sAuthenticated user identity: %s",
            log_prefix,
            user_identity.get("id", "unknown"),
        )

        client_id = session_manager.get_a2a_client_id(request)
        session_id = session_manager.ensure_a2a_session(request)

        log.info(
            "%sUsing ClientID: %s, SessionID: %s", log_prefix, client_id, session_id
        )

        external_event_data = {
            "agent_name": agent_name,
            "message": message,
            "files": files,
            "client_id": client_id,
            "a2a_session_id": session_id,
        }

        target_agent, a2a_parts, external_req_ctx = (
            await component._translate_external_input(external_event_data)
        )

        task_id = await component.submit_a2a_task(
            target_agent_name=target_agent,
            a2a_parts=a2a_parts,
            external_request_context=external_req_ctx,
            user_identity=user_identity,
            is_streaming=False,
        )

        log.info("%sTask submitted successfully. TaskID: %s", log_prefix, task_id)

        return JSONRPCResponse(result={"taskId": task_id})

    except InvalidRequestError as e:
        log.warning("%sInvalid request: %s", log_prefix, e.message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.model_dump(exclude_none=True),
        )
    except PermissionError as pe:
        log.warning("%sPermission denied: %s", log_prefix, str(pe))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except InternalError as e:
        log.error(
            "%sInternal error submitting task: %s", log_prefix, e.message, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.model_dump(exclude_none=True),
        )
    except Exception as e:
        log.exception("%sUnexpected error submitting task: %s", log_prefix, e)
        error_resp = InternalError(message="Unexpected server error: %s" % e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.post("/subscribe", response_model=JSONRPCResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: List[UploadFile] = File([]),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user: dict = Depends(get_current_user),
):
    """
    Submits a streaming task request (`tasks/sendSubscribe`) to the specified agent.
    Accepts multipart/form-data.
    The client should subsequently connect to the SSE endpoint using the returned taskId.
    """
    log_prefix = "[POST /api/v1/tasks/subscribe] "
    log.info("%sReceived streaming request for agent: %s", log_prefix, agent_name)

    try:
        user_identity = await component.authenticate_and_enrich_user(request)
        if user_identity is None:
            log.warning("%sUser authentication failed. Denying request.", log_prefix)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication failed or identity not found.",
            )
        log.info(
            "%sAuthenticated user identity: %s",
            log_prefix,
            user_identity.get("id", "unknown"),
        )

        client_id = session_manager.get_a2a_client_id(request)
        session_id = session_manager.ensure_a2a_session(request)

        log.info(
            "%sUsing ClientID: %s, SessionID: %s", log_prefix, client_id, session_id
        )

        external_event_data = {
            "agent_name": agent_name,
            "message": message,
            "files": files,
            "client_id": client_id,
            "a2a_session_id": session_id,
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
        )

        log.info(
            "%sStreaming task submitted successfully. TaskID: %s", log_prefix, task_id
        )

        return JSONRPCResponse(result={"taskId": task_id})

    except InvalidRequestError as e:
        log.warning("%sInvalid request: %s", log_prefix, e.message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.model_dump(exclude_none=True),
        )
    except PermissionError as pe:
        log.warning("%sPermission denied: %s", log_prefix, str(pe))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except InternalError as e:
        log.error(
            "%sInternal error submitting streaming task: %s",
            log_prefix,
            e.message,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.model_dump(exclude_none=True),
        )
    except Exception as e:
        log.exception("%sUnexpected error submitting streaming task: %s", log_prefix, e)
        error_resp = InternalError(message="Unexpected server error: %s" % e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.post("/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_agent_task(
    request: FastAPIRequest,
    payload: CancelTaskApiPayload,
    session_manager: SessionManager = Depends(get_session_manager),
    task_service: TaskService = Depends(get_task_service),
):
    """
    Sends a cancellation request for a specific task to the specified agent.
    Returns 202 Accepted, as cancellation is asynchronous.
    """
    log_prefix = "[POST /api/v1/tasks/cancel][Task:%s] " % payload.task_id
    log.info(
        "%sReceived cancellation request for agent: %s", log_prefix, payload.agent_name
    )

    try:
        client_id = session_manager.get_a2a_client_id(request)

        log.info("%sUsing ClientID: %s", log_prefix, client_id)

        await task_service.cancel_task(
            payload.agent_name, payload.task_id, client_id, client_id
        )

        log.info("%sCancellation request published successfully.", log_prefix)

        return {"message": "Cancellation request sent"}

    except InvalidRequestError as e:
        log.warning(
            "%sInvalid cancellation request: %s", log_prefix, e.message, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.model_dump(exclude_none=True),
        )
    except InternalError as e:
        log.error(
            "%sInternal error sending cancellation: %s",
            log_prefix,
            e.message,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.model_dump(exclude_none=True),
        )
    except Exception as e:
        log.exception("%sUnexpected error sending cancellation: %s", log_prefix, e)
        error_resp = InternalError(message="Unexpected server error: %s" % e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )
