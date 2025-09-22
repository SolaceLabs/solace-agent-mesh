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
from ..services.project_service import ProjectService

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
)
from ....gateway.http_sse.dependencies import get_project_service
from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)
from ..services.project_service import GLOBAL_PROJECT_USER_ID
from datetime import datetime, timezone

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()


async def _inject_project_context(
    project_id: str,
    message_text: str,
    user_id: str,
    session_id: str,
    project_service: ProjectService,
    component: "WebUIBackendComponent",
    log_prefix: str,
) -> str:
    """
    Helper function to inject project context and copy artifacts to session.
    Returns the modified message text with project context injected.
    """
    if not project_id or not message_text:
        return message_text
    
    try:
        project = project_service.get_project(project_id, user_id)
        if not project:
            return message_text
            
        # 1. Inject project context (system prompt, description)
        context_parts = []
        if project.system_prompt and project.system_prompt.strip():
            context_parts.append(project.system_prompt.strip())
        if project.description and project.description.strip():
            context_parts.append(f"Project Context: {project.description.strip()}")
        
        modified_message_text = message_text
        if context_parts:
            project_context = "\n\n".join(context_parts) + "\n\n"
            modified_message_text = project_context + message_text
            log.info("%sInjected project context for project: %s", log_prefix, project_id)

        # 2. Copy project artifacts to session
        artifact_service = component.get_shared_artifact_service()
        if artifact_service:
            try:
                source_user_id = GLOBAL_PROJECT_USER_ID if project.is_global else project.user_id
                project_artifacts_session_id = f"project-{project.id}"
                
                log.info("%sChecking for artifacts in project %s (storage session: %s)", log_prefix, project.id, project_artifacts_session_id)
                
                project_artifacts = await get_artifact_info_list(
                    artifact_service=artifact_service,
                    app_name=project_service.app_name,
                    user_id=source_user_id,
                    session_id=project_artifacts_session_id,
                )

                if project_artifacts:
                    log.info("%sFound %d artifacts to copy from project %s.", log_prefix, len(project_artifacts), project.id)
                    for artifact_info in project_artifacts:
                        # Load artifact content from project storage
                        loaded_artifact = await load_artifact_content_or_metadata(
                            artifact_service=artifact_service,
                            app_name=project_service.app_name,
                            user_id=source_user_id,
                            session_id=project_artifacts_session_id,
                            filename=artifact_info.filename,
                            return_raw_bytes=True,
                            version="latest"
                        )
                        
                        # Load the full metadata separately
                        loaded_metadata = await load_artifact_content_or_metadata(
                            artifact_service=artifact_service,
                            app_name=project_service.app_name,
                            user_id=source_user_id,
                            session_id=project_artifacts_session_id,
                            filename=artifact_info.filename,
                            load_metadata_only=True,
                            version="latest"
                        )
                        
                        # Save a copy to the current chat session
                        if loaded_artifact.get("status") == "success":
                            full_metadata = loaded_metadata.get("metadata", {}) if loaded_metadata.get("status") == "success" else {}
                            
                            await save_artifact_with_metadata(
                                artifact_service=artifact_service,
                                app_name=project_service.app_name,
                                user_id=user_id,
                                session_id=session_id,
                                filename=artifact_info.filename,
                                content_bytes=loaded_artifact.get("raw_bytes"),
                                mime_type=loaded_artifact.get("mime_type"),
                                metadata_dict=full_metadata,
                                timestamp=datetime.now(timezone.utc),
                            )
                    log.info("%sFinished copying %d artifacts to session %s.", log_prefix, len(project_artifacts), session_id)
                else:
                    log.info("%sNo artifacts found in project %s to copy.", log_prefix, project.id)

            except Exception as e:
                log.warning("%sFailed to copy project artifacts to session: %s", log_prefix, e)
                # Do not fail the entire request, just log the warning
                
        return modified_message_text
        
    except Exception as e:
        log.warning("%sFailed to inject project context: %s", log_prefix, e)
        # Continue without injection - don't fail the request
        return message_text


async def _submit_task(
    request: FastAPIRequest,
    payload: Union[SendMessageRequest, SendStreamingMessageRequest],
    session_manager: SessionManager,
    component: "WebUIBackendComponent",
    project_service: ProjectService,
    is_streaming: bool,
):
    """Helper to submit a task, handling both streaming and non-streaming cases."""
    log_prefix = f"[POST /api/v1/message:{'stream' if is_streaming else 'send'}] "

    agent_name = None
    project_id = None
    if payload.params and payload.params.message and payload.params.message.metadata:
        agent_name = payload.params.message.metadata.get("agent_name")
        project_id = payload.params.message.metadata.get("project_id")

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
        
        # Use session ID from frontend request (contextId) instead of cookie-based session
        # Handle various falsy values: None, empty string, whitespace-only string
        log.info("%s[DEBUG] payload.params.message: %s", log_prefix, payload.params.message)
        log.info("%s[DEBUG] hasattr context_id: %s", log_prefix, hasattr(payload.params.message, 'context_id'))
        if hasattr(payload.params.message, 'context_id'):
            log.info("%s[DEBUG] context_id value: %s", log_prefix, payload.params.message.context_id)
        
        frontend_session_id = None
        if hasattr(payload.params.message, 'context_id') and payload.params.message.context_id:
            context_id = payload.params.message.context_id
            if isinstance(context_id, str) and context_id.strip():
                frontend_session_id = context_id.strip()
                log.info("%s[DEBUG] Extracted frontend_session_id: %s", log_prefix, frontend_session_id)
        
        if frontend_session_id:
            session_id = frontend_session_id
            log.info("%sUsing session ID from frontend request: %s", log_prefix, session_id)
        else:
            # Create new session when frontend doesn't provide one (None, empty, or whitespace-only)
            session_id = session_manager.create_new_session_id(request)
            log.info("%sNo valid session ID from frontend, created new session: %s", log_prefix, session_id)

        log.info(
            "%sUsing ClientID: %s, SessionID: %s", log_prefix, client_id, session_id
        )

        # Store message in persistence layer if available
        user_id = user_identity.get("id")
        from ....gateway.http_sse.dependencies import SessionLocal
        if is_streaming and SessionLocal is not None:
            try:
                from ....gateway.http_sse.dependencies import create_session_service_with_transaction
                from ....gateway.http_sse.shared.enums import SenderType
                
                with create_session_service_with_transaction() as (session_service, db):
                    existing_session = session_service.get_session(session_id, user_id)
                    session_was_created = False
                    if not existing_session:
                        log.info("%sCreating new session in database: %s", log_prefix, session_id)
                        try:
                            session_service.create_session(
                                user_id=user_id,
                                agent_id=agent_name,
                                name=None,
                                session_id=session_id,
                                project_id=project_id if project_id else None
                            )
                            session_was_created = True
                        except Exception as create_error:
                            log.warning("%sSession creation failed, checking if session exists: %s", log_prefix, create_error)
                            existing_session = session_service.get_session(session_id, user_id)
                            if not existing_session:
                                raise create_error
                            log.info("%sSession was created by another request: %s", log_prefix, session_id)
                    
                    message_text = ""
                    if payload.params and payload.params.message:
                        parts = a2a.get_parts_from_message(payload.params.message)
                        for part in parts:
                            if hasattr(part, 'text'):
                                message_text = part.text
                                break
                    
                    # Project context injection only for the first message (when session was just created)
                    if project_id and message_text and session_was_created:
                        message_text = await _inject_project_context(
                            project_id=project_id,
                            message_text=message_text,
                            user_id=user_id,
                            session_id=session_id,
                            project_service=project_service,
                            component=component,
                            log_prefix=log_prefix,
                        )
                    
                    message_domain = session_service.add_message_to_session(
                        session_id=session_id,
                        user_id=user_id,
                        message=message_text or "Task submitted",
                        sender_type=SenderType.USER,
                        sender_name=user_id or "user",
                        agent_id=agent_name,
                    )
                    
                    if message_domain:
                        log.info("%sMessage stored in session %s", log_prefix, session_id)
                    else:
                        log.warning("%sFailed to store message in session %s", log_prefix, session_id)
            except Exception as e:
                log.error("%sFailed to store message in session service: %s", log_prefix, e)
        else:
            log.debug("%sNo persistence available or non-streaming - skipping message storage", log_prefix)

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
    project_service: ProjectService = Depends(get_project_service),
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
        project_service=project_service,
        is_streaming=False,
    )


@router.post("/message:stream", response_model=SendStreamingMessageSuccessResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    payload: SendStreamingMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService = Depends(get_project_service),
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
        project_service=project_service,
        is_streaming=True,
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
