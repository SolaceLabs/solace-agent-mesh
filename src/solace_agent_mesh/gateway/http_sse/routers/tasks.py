"""
API Router for submitting and managing tasks to agents.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request as FastAPIRequest,
    status,
)
from typing import Union

from solace_ai_connector.common.log import log

from ....gateway.http_sse.session_manager import SessionManager
from ....gateway.http_sse.services.task_service import TaskService
from ....gateway.http_sse.services.session_service import SessionService

from a2a.types import (
    CancelTaskRequest,
    SendMessageRequest,
    SendStreamingMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageSuccessResponse,
)
from ....common import a2a

from ....gateway.http_sse.dependencies import (
    get_session_manager,
    get_sac_component,
    get_task_service,
    get_session_business_service,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()


async def _submit_task(
    request: FastAPIRequest,
    payload: Union[SendMessageRequest, SendStreamingMessageRequest],
    session_manager: SessionManager,
    component: "WebUIBackendComponent",
    is_streaming: bool,
    session_service: SessionService | None = None,
):
    """Helper to submit a task, handling both streaming and non-streaming cases."""
    log_prefix = f"[POST /api/v1/message:{'stream' if is_streaming else 'send'}] "

    agent_name = None
    if payload.params and payload.params.message and payload.params.message.metadata:
        agent_name = payload.params.message.metadata.get("agent_name")

    if not agent_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'agent_name' in request payload message metadata.",
        )

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

        # Use session ID from frontend request (contextId per A2A spec) instead of cookie-based session
        # Handle various falsy values: None, empty string, whitespace-only string
        frontend_session_id = None
        if (
            hasattr(payload.params.message, "context_id")
            and payload.params.message.context_id
        ):
            context_id = payload.params.message.context_id
            if isinstance(context_id, str) and context_id.strip():
                frontend_session_id = context_id.strip()

        user_id = user_identity.get("id")
        from ....gateway.http_sse.dependencies import SessionLocal

        if frontend_session_id:
            session_id = frontend_session_id
            log.info(
                "%sUsing session ID from frontend request: %s", log_prefix, session_id
            )
        else:
            # Create new session when frontend doesn't provide one
            session_id = session_manager.create_new_session_id(request)
            log.info(
                "%sNo valid session ID from frontend, created new session: %s",
                log_prefix,
                session_id,
            )

            # Immediately create session in database if persistence is enabled
            # This ensures the session exists before any other operations (like artifact listing)
            if SessionLocal is not None and session_service is not None:
                db = SessionLocal()
                try:
                    session_service.create_session(
                        db=db,
                        user_id=user_id,
                        agent_id=agent_name,
                        session_id=session_id,
                    )
                    db.commit()
                    log.info("%sCreated session in database: %s", log_prefix, session_id)
                except Exception as e:
                    db.rollback()
                    log.warning("%sFailed to create session in database: %s", log_prefix, e)
                finally:
                    db.close()

        log.info(
            "%sUsing ClientID: %s, SessionID: %s", log_prefix, client_id, session_id
        )

        # Store message in persistence layer if available
        if is_streaming and SessionLocal is not None and session_service is not None:
            db = SessionLocal()
            try:
                from ....gateway.http_sse.shared.enums import SenderType

                message_text = ""
                if payload.params and payload.params.message:
                    parts = a2a.get_parts_from_message(payload.params.message)
                    for part in parts:
                        if hasattr(part, "text"):
                            message_text = part.text
                            break

                session_service.add_message_to_session(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    message=message_text or "Task submitted",
                    sender_type=SenderType.USER,
                    sender_name=user_id or "user",
                    agent_id=agent_name,
                )
                db.commit()
            except Exception as e:
                db.rollback()
                log.error(
                    "%sFailed to store message in session service: %s", log_prefix, e
                )
            finally:
                db.close()
        else:
            log.debug(
                "%sNo persistence available or non-streaming - skipping message storage",
                log_prefix,
            )

        # Use the helper to get the unwrapped parts from the incoming message.
        a2a_parts = a2a.get_parts_from_message(payload.params.message)

        external_req_ctx = {
            "app_name_for_artifacts": component.gateway_id,
            "user_id_for_artifacts": client_id,
            "a2a_session_id": session_id,  # This may have been updated by persistence layer
            "user_id_for_a2a": client_id,
            "target_agent_name": agent_name,
        }

        task_id = await component.submit_a2a_task(
            target_agent_name=agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_req_ctx,
            user_identity=user_identity,
            is_streaming=is_streaming,
        )

        log.info("%sTask submitted successfully. TaskID: %s", log_prefix, task_id)

        task_object = a2a.create_initial_task(
            task_id=task_id,
            context_id=session_id,
            agent_name=agent_name,
        )

        if is_streaming:
            # The task_object already contains the contextId from create_initial_task
            return a2a.create_send_streaming_message_success_response(
                result=task_object, request_id=payload.id
            )
        else:
            return a2a.create_send_message_success_response(
                result=task_object, request_id=payload.id
            )

    except PermissionError as pe:
        log.warning("%sPermission denied: %s", log_prefix, str(pe))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except Exception as e:
        log.exception("%sUnexpected error submitting task: %s", log_prefix, e)
        error_resp = a2a.create_internal_error(
            message="Unexpected server error: %s" % e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )


@router.post("/message:send", response_model=SendMessageSuccessResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    payload: SendMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Submits a non-streaming task request to the specified agent.
    Accepts application/json.
    """
    return await _submit_task(
        request=request,
        payload=payload,
        session_manager=session_manager,
        component=component,
        is_streaming=False,
        session_service=None,
    )


@router.post("/message:stream", response_model=SendStreamingMessageSuccessResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    payload: SendStreamingMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Submits a streaming task request to the specified agent.
    Accepts application/json.
    The client should subsequently connect to the SSE endpoint using the returned taskId.
    """
    return await _submit_task(
        request=request,
        payload=payload,
        session_manager=session_manager,
        component=component,
        is_streaming=True,
        session_service=session_service,
    )


@router.post("/tasks/{taskId}:cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_agent_task(
    request: FastAPIRequest,
    taskId: str,
    payload: CancelTaskRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    task_service: TaskService = Depends(get_task_service),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
):
    """
    Sends a cancellation request for a specific task to the specified agent.
    Returns 202 Accepted, as cancellation is asynchronous.
    """
    log_prefix = f"[POST /api/v1/tasks/{taskId}:cancel] "
    log.info("%sReceived cancellation request.", log_prefix)

    if taskId != payload.params.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task ID in URL path does not match task ID in payload.",
        )

    context = component.task_context_manager.get_context(taskId)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active task context found for task ID: {taskId}",
        )

    agent_name = context.get("target_agent_name")
    if not agent_name:
        log.error(
            "%sCould not determine target agent for task %s. Context is missing 'target_agent_name'.",
            log_prefix,
            taskId,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not determine target agent for the task.",
        )

    log.info("%sTarget agent for cancellation is '%s'", log_prefix, agent_name)

    try:
        client_id = session_manager.get_a2a_client_id(request)

        log.info("%sUsing ClientID: %s", log_prefix, client_id)

        await task_service.cancel_task(agent_name, taskId, client_id, client_id)

        log.info("%sCancellation request published successfully.", log_prefix)

        return {"message": "Cancellation request sent"}

    except Exception as e:
        log.exception("%sUnexpected error sending cancellation: %s", log_prefix, e)
        error_resp = a2a.create_internal_error(
            message="Unexpected server error: %s" % e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_resp.model_dump(exclude_none=True),
        )