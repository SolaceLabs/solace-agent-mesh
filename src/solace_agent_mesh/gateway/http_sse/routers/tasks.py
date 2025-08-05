"""
API Router for submitting tasks to A2A agents.
"""

from fastapi import (
    APIRouter,
    Depends,
    Form,
    File,
    HTTPException,
    Request as FastAPIRequest,
    status,
    UploadFile,
)
from pydantic import BaseModel, Field
from typing import List, Optional

from solace_ai_connector.common.log import log

from ....gateway.http_sse.session_manager import SessionManager
from ....gateway.http_sse.services.task_service import TaskService


from ....common.types import (
    JSONRPCResponse,
    InternalError,
    InvalidRequestError,
)
from ....gateway.http_sse.dependencies import (
    get_sac_component,
    get_session_manager,
    get_user_id,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent


router = APIRouter()


class TaskRequest(BaseModel):
    agent_name: str = Field(..., description="The name of the target A2A agent.")
    message: str = Field(..., description="The user's message or prompt.")
    files: List[UploadFile] = Field([], description="A list of files to be uploaded.")


@router.post("/send", response_model=JSONRPCResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: List[UploadFile] = File([]),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_id: str = Depends(get_user_id),
):
    """
    Submits a non-streaming task request to the specified agent.
    This corresponds to the A2A `tasks/send` method.
    """
    log_prefix = "[POST /api/v1/tasks/send] "
    log.info("%sReceived request for agent: %s", log_prefix, agent_name)

    try:
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
        (
            target_agent,
            a2a_parts,
            external_request_context,
        ) = await component._translate_external_input(external_event_data)

        # The user identity is already resolved by the `get_current_user` dependency.
        user_identity = {"id": user_id}
        log.info(
            "%sAuthenticated user identity: %s",
            log_prefix,
            user_identity.get("id", "unknown"),
        )
        task_id = await component.submit_a2a_task(
            target_agent_name=target_agent,
            a2a_parts=a2a_parts,
            user_identity=user_identity,
            external_request_context=external_request_context,
            is_streaming=False,
        )

        log.info(
            "%sNon-streaming task submitted successfully. TaskID: %s",
            log_prefix,
            task_id,
        )

        return JSONRPCResponse(result={"taskId": task_id})

    except InvalidRequestError as e:
        log.warning("%sInvalid request: %s", log_prefix, e.message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.model_dump(exclude_none=True),
        )
    except Exception as e:
        log.exception("%sUnexpected error processing task: %s", log_prefix, e)
        error_resp = InternalError(message=f"Failed to process task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


from ..database.persistence_service import PersistenceService


from ..dependencies import get_persistence_service


@router.post("/subscribe", response_model=JSONRPCResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: List[UploadFile] = File([]),
    session_id: Optional[str] = Form(None),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_id: str = Depends(get_user_id),
    persistence_service: PersistenceService = Depends(get_persistence_service),
):
    """
    Submits a streaming task request (`tasks/sendSubscribe`) to the specified agent.
    """
    log_prefix = "[POST /api/v1/tasks/subscribe] "
    log.info("%sReceived streaming request for agent: %s", log_prefix, agent_name)

    try:
        client_id = session_manager.get_a2a_client_id(request)

        # If session_id is not provided by the client, create a new one.
        if not session_id:
            log.info("%sNo session_id provided, creating a new one.", log_prefix)
            session_id = session_manager.start_new_a2a_session(request)

        persistence_service.store_chat_message(
            session_id=session_id,
            message={
                "content": message,
                "sender_type": "user",
                "sender_name": user_id,
            },
            user_id=user_id,
            agent_id=agent_name,
        )

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
        (
            target_agent,
            a2a_parts,
            external_request_context,
        ) = await component._translate_external_input(external_event_data)

        # The user identity is already resolved by the `get_current_user` dependency.
        user_identity = {"id": user_id}
        log.info(
            "%sAuthenticated user identity: %s",
            log_prefix,
            user_identity.get("id", "unknown"),
        )
        task_id = await component.submit_a2a_task(
            target_agent_name=target_agent,
            a2a_parts=a2a_parts,
            user_identity=user_identity,
            external_request_context=external_request_context,
            is_streaming=True,
        )

        log.info(
            "%sStreaming task submitted successfully. TaskID: %s", log_prefix, task_id
        )

        return JSONRPCResponse(result={"taskId": task_id, "sessionId": session_id})

    except InvalidRequestError as e:
        log.warning("%sInvalid request: %s", log_prefix, e.message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.model_dump(exclude_none=True),
        )
    except Exception as e:
        log.exception("%sUnexpected error processing task: %s", log_prefix, e)
        error_resp = InternalError(message=f"Failed to process task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.post("/cancel", response_model=JSONRPCResponse)
async def cancel_agent_task(
    request: FastAPIRequest,
    task_id: str = Form(...),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Sends a cancellation request for a specific task.
    """
    log_prefix = f"[POST /api/v1/tasks/cancel] TaskID: {task_id} "
    log.info("%sReceived cancellation request.", log_prefix)

    try:
        client_id = session_manager.get_a2a_client_id(request)
        await component.cancel_a2a_task(task_id, client_id)
        log.info("%sCancellation request sent successfully.", log_prefix)
        return JSONRPCResponse(
            result={"message": f"Cancellation request sent for task {task_id}"}
        )
    except Exception as e:
        log.exception("%sUnexpected error sending cancellation: %s", log_prefix, e)
        error_resp = InternalError(message="Unexpected server error: %s" % e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )
