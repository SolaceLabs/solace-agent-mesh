from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, Form, HTTPException
from fastapi import Request as FastAPIRequest
from fastapi import UploadFile, status
from solace_ai_connector.common.log import log

from a2a.types import InternalError, InvalidRequestError, JSONRPCResponse
from .....common import a2a
from ...dependencies import (
    get_sac_component,
    get_session_manager,
    get_user_id,
)
from ...session_manager import SessionManager
from ...shared.enums import SenderType
from ..dto.requests.task_requests import (
    CancelTaskRequest,
    ProcessedTaskRequest,
    TaskFilesInfo,
)

if TYPE_CHECKING:
    from ...component import WebUIBackendComponent

router = APIRouter()


@router.post("/send", response_model=JSONRPCResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: list[UploadFile] = File([]),
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
        task_files = []
        for file in files:
            if file.filename:
                task_files.append(
                    TaskFilesInfo(
                        filename=file.filename,
                        content_type=file.content_type or "application/octet-stream",
                        size=0,  # We'd need to read the file to get size
                    )
                )

        request_dto = ProcessedTaskRequest(
            agent_name=agent_name, message=message, user_id=user_id, files=task_files
        )

        # Continue with existing logic
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
        error_resp = a2a.create_internal_error(message=f"Failed to process task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.post("/subscribe", response_model=JSONRPCResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    agent_name: str = Form(...),
    message: str = Form(...),
    files: list[UploadFile] = File([]),
    session_id: str | None = Form(None),
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    user_id: str = Depends(get_user_id),
):
    """
    Submits a streaming task request (`tasks/sendSubscribe`) to the specified agent.
    """
    log_prefix = "[POST /api/v1/tasks/subscribe] "
    log.info("%sReceived streaming request for agent: %s", log_prefix, agent_name)

    try:
        task_files = []
        for file in files:
            if file.filename:
                task_files.append(
                    TaskFilesInfo(
                        filename=file.filename,
                        content_type=file.content_type or "application/octet-stream",
                        size=0,
                    )
                )

        request_dto = ProcessedTaskRequest(
            agent_name=agent_name,
            message=message,
            user_id=user_id,
            session_id=session_id,
            files=task_files,
        )

        client_id = session_manager.get_a2a_client_id(request)

        # If session_id is not provided by the client, create a new one.
        if not session_id:
            log.info("%sNo session_id provided, creating a new one.", log_prefix)
            session_id = session_manager.start_new_a2a_session(request)

        # Store message only if persistence is available
        if hasattr(component, "persistence_service") and component.persistence_service:
            try:
                from ...dependencies import get_session_service
                session_service = get_session_service(component)
                message_domain = session_service.add_message_to_session(
                    session_id=session_id,
                    user_id=user_id,
                    message=message,
                    sender_type=SenderType.USER,
                    sender_name=user_id,
                    agent_id=agent_name,
                )
                # Use the actual session ID from the message (may be different if session was recreated)
                if message_domain:
                    session_id = message_domain.session_id
            except ValueError as e:
                # Handle business domain validation errors
                log.warning("Validation error in session service: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
                )
            except Exception as e:
                log.error("Failed to store message in session service: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to store message",
                )
        else:
            log.debug("%sNo persistence available - skipping message storage", log_prefix)

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
    except HTTPException:
        # Re-raise HTTPExceptions (like 422 validation errors) without modification
        raise
    except Exception as e:
        log.exception("%sUnexpected error processing task: %s", log_prefix, e)
        error_resp = a2a.create_internal_error(message=f"Failed to process task: {e}")
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
    user_id: str = Depends(get_user_id),
):
    """
    Sends a cancellation request for a specific task.
    """
    log_prefix = f"[POST /api/v1/tasks/cancel] TaskID: {task_id} "
    log.info("%sReceived cancellation request.", log_prefix)

    try:
        request_dto = CancelTaskRequest(task_id=task_id, user_id=user_id)

        client_id = session_manager.get_a2a_client_id(request)
        await component.cancel_a2a_task(task_id, client_id)
        log.info("%sCancellation request sent successfully.", log_prefix)
        return JSONRPCResponse(
            result={"message": f"Cancellation request sent for task {task_id}"}
        )
    except Exception as e:
        log.exception("%sUnexpected error sending cancellation: %s", log_prefix, e)
        error_resp = a2a.create_internal_error(message="Unexpected server error: %s" % e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )
