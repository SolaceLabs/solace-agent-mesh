"""
API Router for submitting and managing tasks to agents.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import yaml
from a2a.types import (
    CancelTaskRequest,
    SendMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi import Request as FastAPIRequest
from sqlalchemy.orm import Session as DBSession

from ....gateway.http_sse.services.project_service import ProjectService

from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
    save_artifact_with_metadata,
)

from ....common import a2a
from ....gateway.http_sse.dependencies import (
    get_db,
    get_project_service_optional,
    get_sac_component,
    get_session_business_service,
    get_session_manager,
    get_task_repository,
    get_task_service,
    get_user_config,
    get_user_id,
)
from ....gateway.http_sse.repository.entities import Task
from ....gateway.http_sse.repository.interfaces import ITaskRepository
from ....gateway.http_sse.services.session_service import SessionService
from ....gateway.http_sse.services.task_service import TaskService
from ....gateway.http_sse.session_manager import SessionManager
from ....gateway.http_sse.shared.pagination import PaginationParams
from ....gateway.http_sse.shared.types import UserId
from ..utils.stim_utils import create_stim_from_task_data

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()

log = logging.getLogger(__name__)


async def _inject_project_context(
    project_id: str,
    message_text: str,
    user_id: str,
    session_id: str,
    project_service: ProjectService,
    component: "WebUIBackendComponent",
    log_prefix: str,
    inject_full_context: bool = True,
) -> str:
    """
    Helper function to inject project context and copy artifacts to session.

    Args:
        inject_full_context: If True, injects full project context (name, description, instructions).
                           If False, only copies new artifacts without modifying message text.
                           This allows existing sessions to get new project files without
                           re-injecting the full context on every message.

    Returns the modified message text with project context injected (if inject_full_context=True).
    """
    if not project_id or not message_text:
        return message_text

    from ....gateway.http_sse.dependencies import SessionLocal

    if SessionLocal is None:
        log.warning("%sProject context injection skipped: database not configured", log_prefix)
        return message_text

    db = SessionLocal()
    try:
        project = project_service.get_project(db, project_id, user_id)
        if not project:
            return message_text
        
        context_parts = []

        # Only inject full context for new sessions
        if inject_full_context:
            # Start with clear workspace framing
            context_parts.append(f'You are working in the project workspace: "{project.name}"')

            # Add system prompt if exists
            if project.system_prompt and project.system_prompt.strip():
                context_parts.append(f"\n{project.system_prompt.strip()}")

            # Add project description if exists
            if project.description and project.description.strip():
                context_parts.append(f"\nProject Description: {project.description.strip()}")
        
        # Always copy project artifacts to session (for both new and existing sessions)
        # This ensures new project files are available to existing sessions
        artifact_service = component.get_shared_artifact_service()
        if artifact_service:
            try:
                source_user_id = project.user_id
                project_artifacts_session_id = f"project-{project.id}"
                
                log.info("%sChecking for artifacts in project %s (storage session: %s)", log_prefix, project.id, project_artifacts_session_id)
                
                project_artifacts = await get_artifact_info_list(
                    artifact_service=artifact_service,
                    app_name=project_service.app_name,
                    user_id=source_user_id,
                    session_id=project_artifacts_session_id,
                )

                if project_artifacts:
                    log.info("%sFound %d artifacts in project %s to process.", log_prefix, len(project_artifacts), project.id)
                    
                    # Get list of artifacts already in session to avoid re-copying
                    try:
                        session_artifacts = await get_artifact_info_list(
                            artifact_service=artifact_service,
                            app_name=project_service.app_name,
                            user_id=user_id,
                            session_id=session_id,
                        )
                        session_artifact_names = {art.filename for art in session_artifacts}
                        log.debug("%sSession %s currently has %d artifacts", log_prefix, session_id, len(session_artifact_names))
                    except Exception as e:
                        log.warning("%sFailed to get session artifacts, will copy all project artifacts: %s", log_prefix, e)
                        session_artifact_names = set()
                    
                    all_artifact_descriptions = []  # For new sessions - all files
                    new_artifact_descriptions = []  # For existing sessions - only new files
                    artifacts_copied = 0
                    
                    for artifact_info in project_artifacts:
                        # Build description for all artifacts (for new sessions)
                        desc_str = f"- {artifact_info.filename}"
                        if artifact_info.description:
                            desc_str += f": {artifact_info.description}"
                        all_artifact_descriptions.append(desc_str)

                        # Skip if artifact already exists in session (any source)
                        if artifact_info.filename in session_artifact_names:
                            log.debug("%sSkipping artifact %s - already exists in session", log_prefix, artifact_info.filename)
                            continue
                        
                        # Track new artifacts for existing sessions
                        new_artifact_descriptions.append(desc_str)

                        log.info("%sCopying new artifact %s to session %s", log_prefix, artifact_info.filename, session_id)
                        
                        try:
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
                                
                                # Ensure the source is always set for copied project artifacts
                                full_metadata["source"] = "project"

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
                                artifacts_copied += 1
                                log.info("%sSuccessfully copied artifact %s to session", log_prefix, artifact_info.filename)
                            else:
                                log.warning("%sFailed to load artifact %s: %s", log_prefix, artifact_info.filename, loaded_artifact.get("status"))
                        except Exception as e:
                            log.error("%sError copying artifact %s to session: %s", log_prefix, artifact_info.filename, e)
                            # Continue with other artifacts even if one fails

                    # Add artifact descriptions to context
                    if inject_full_context and all_artifact_descriptions:
                        # New session: show all project files
                        artifacts_context = (
                            "\nFiles in Session:\n"
                            "The following files are available in your session and can be viewed using your tools if required:\n"
                            + "\n".join(all_artifact_descriptions)
                        )
                        context_parts.append(artifacts_context)
                    elif not inject_full_context and new_artifact_descriptions:
                        # Existing session: notify about newly added files
                        new_files_context = (
                            "\nNew Files Added to Project:\n"
                            "The following files have been added to the project and are now available in your session:\n"
                            + "\n".join(new_artifact_descriptions)
                        )
                        context_parts.append(new_files_context)
                    
                    if artifacts_copied > 0:
                        log.info("%sCopied %d new artifacts to session %s.", log_prefix, artifacts_copied, session_id)
                    else:
                        log.debug("%sNo new artifacts to copy to session %s.", log_prefix, session_id)
                else:
                    log.info("%sNo artifacts found in project %s to copy.", log_prefix, project.id)

            except Exception as e:
                log.warning("%sFailed to copy project artifacts to session: %s", log_prefix, e)
                # Do not fail the entire request, just log the warning

        # Inject all gathered context into the message, ending with user query
        # Only modify message text if we're injecting full context (new sessions)
        modified_message_text = message_text
        if context_parts:
            project_context = "\n".join(context_parts)
            modified_message_text = f"{project_context}\n\nUSER QUERY:\n{message_text}"
            log.info("%sInjected full project context for project: %s", log_prefix, project_id)
        else:
            log.debug("%sSkipped full context injection for existing session, but ensured new artifacts are copied", log_prefix)
                
        return modified_message_text

    except Exception as e:
        log.warning("%sFailed to inject project context: %s", log_prefix, e)
        # Continue without injection - don't fail the request
        return message_text
    finally:
        db.close()


async def _submit_task(
    request: FastAPIRequest,
    payload: SendMessageRequest | SendStreamingMessageRequest,
    session_manager: SessionManager,
    component: "WebUIBackendComponent",
    project_service: ProjectService | None,
    is_streaming: bool,
    session_service: SessionService | None = None,
):
    """
    Helper to submit a task, handling both streaming and non-streaming cases.

    Also handles project context injection.
    """
    log_prefix = f"[POST /api/v1/message:{'stream' if is_streaming else 'send'}] "

    agent_name = None
    project_id = None
    if payload.params and payload.params.message and payload.params.message.metadata:
        agent_name = payload.params.message.metadata.get("agent_name")
        project_id = payload.params.message.metadata.get("project_id")

    if not agent_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        log.debug(
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

        # If project_id not in metadata, check if session has a project_id in database
        # This handles cases where sessions are moved to projects after creation
        if not project_id and session_service and frontend_session_id:
            if SessionLocal is not None:
                db = SessionLocal()
                try:
                    session_details = session_service.get_session_details(db, frontend_session_id, user_id)
                    if session_details and session_details.project_id:
                        project_id = session_details.project_id
                        log.info("%sFound project_id %s from session database for session %s", log_prefix, project_id, frontend_session_id)
                except Exception as e:
                    log.warning("%sFailed to lookup session project_id: %s", log_prefix, e)
                finally:
                    db.close()

        if frontend_session_id:
            session_id = frontend_session_id
            log.info(
                "%sUsing session ID from frontend request: %s", log_prefix, session_id
            )
        else:
            # Create new session when frontend doesn't provide one
            session_id = session_manager.create_new_session_id(request)
            log.debug(
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
                        project_id=project_id,
                    )
                    db.commit()
                    log.debug(
                        "%sCreated session in database: %s", log_prefix, session_id
                    )
                except Exception as e:
                    db.rollback()
                    log.warning(
                        "%sFailed to create session in database: %s", log_prefix, e
                    )
                finally:
                    db.close()

        log.info(
            "%sUsing ClientID: %s, SessionID: %s", log_prefix, client_id, session_id
        )

        # Extract message text and apply project context injection
        message_text = ""
        if payload.params and payload.params.message:
            parts = a2a.get_parts_from_message(payload.params.message)
            for part in parts:
                if hasattr(part, "text"):
                    message_text = part.text
                    break
        
        # Project context injection - always inject for project sessions to ensure new files are available
        # Skip if project_service is None (persistence disabled)
        modified_message = payload.params.message
        if project_service and project_id and message_text:
            # Inject context for new sessions (includes full context + artifact copy)
            # For existing sessions, only copy new artifacts without re-injecting full context
            should_inject_full_context = not frontend_session_id

            modified_message_text = await _inject_project_context(
                project_id=project_id,
                message_text=message_text,
                user_id=user_id,
                session_id=session_id,
                project_service=project_service,
                component=component,
                log_prefix=log_prefix,
                inject_full_context=should_inject_full_context,
            )

            # Update the message with project context if it was modified
            if modified_message_text != message_text:
                # Create new text part with project context
                new_text_part = a2a.create_text_part(modified_message_text)

                # Get existing parts and replace the first text part with the modified one
                existing_parts = a2a.get_parts_from_message(payload.params.message)
                new_parts = []
                text_part_replaced = False

                for part in existing_parts:
                    if hasattr(part, "text") and not text_part_replaced:
                        new_parts.append(new_text_part)
                        text_part_replaced = True
                    else:
                        new_parts.append(part)

                # If no text part was found, add the new text part at the beginning
                if not text_part_replaced:
                    new_parts.insert(0, new_text_part)

                # Update the message with the new parts
                modified_message = a2a.update_message_parts(payload.params.message, new_parts)

        # Use the helper to get the unwrapped parts from the modified message (with project context if applied).
        a2a_parts = a2a.get_parts_from_message(modified_message)

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


@router.get("/tasks", response_model=list[Task], tags=["Tasks"])
async def search_tasks(
    request: FastAPIRequest,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    query_user_id: str | None = None,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
    user_config: dict = Depends(get_user_config),
    repo: ITaskRepository = Depends(get_task_repository),
):
    """
    Lists and filters historical tasks by date.
    - Regular users can only view their own tasks.
    - Users with the 'tasks:read:all' scope can view any user's tasks by providing `query_user_id`.
    """
    log_prefix = "[GET /api/v1/tasks] "
    log.info("%sRequest from user %s", log_prefix, user_id)

    target_user_id = user_id
    can_query_all = user_config.get("scopes", {}).get("tasks:read:all", False)

    if query_user_id:
        if can_query_all:
            target_user_id = query_user_id
            log.info(
                "%sAdmin user %s is querying for user %s",
                log_prefix,
                user_id,
                target_user_id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to query for other users' tasks.",
            )
    elif can_query_all:
        target_user_id = "*"
        log.info("%sAdmin user %s is querying for all users.", log_prefix, user_id)

    start_time_ms = None
    if start_date:
        try:
            start_time_ms = int(datetime.fromisoformat(start_date).timestamp() * 1000)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 format.",
            )

    end_time_ms = None
    if end_date:
        try:
            end_time_ms = int(datetime.fromisoformat(end_date).timestamp() * 1000)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 format.",
            )

    pagination = PaginationParams(page_number=page, page_size=page_size)

    try:
        tasks = repo.search(
            db,
            user_id=target_user_id,
            start_date=start_time_ms,
            end_date=end_time_ms,
            pagination=pagination,
        )
        return tasks
    except Exception as e:
        log.exception("%sError searching for tasks: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for tasks.",
        )


@router.get("/tasks/{task_id}", tags=["Tasks"])
async def get_task_as_stim_file(
    task_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
    user_config: dict = Depends(get_user_config),
    repo: ITaskRepository = Depends(get_task_repository),
):
    """
    Retrieves the complete event history for a single task and returns it as a `.stim` file.
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)

    try:
        result = repo.find_by_id_with_events(db, task_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID '{task_id}' not found.",
            )

        task, events = result

        can_read_all = user_config.get("scopes", {}).get("tasks:read:all", False)
        if task.user_id != user_id and not can_read_all:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this task.",
            )

        # Format into .stim structure
        stim_data = create_stim_from_task_data(task, events)

        yaml_content = yaml.dump(
            stim_data,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
            default_flow_style=False,
        )

        return Response(
            content=yaml_content,
            media_type="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="{task_id}.stim"'},
        )

    except HTTPException:
        # Re-raise HTTPExceptions (404, 403, etc.) without modification
        raise
    except Exception as e:
        log.exception("%sError retrieving task: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the task.",
        )


@router.post("/message:send", response_model=SendMessageSuccessResponse)
async def send_task_to_agent(
    request: FastAPIRequest,
    payload: SendMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
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
        session_service=None,
    )


@router.post("/message:stream", response_model=SendStreamingMessageSuccessResponse)
async def subscribe_task_from_agent(
    request: FastAPIRequest,
    payload: SendStreamingMessageRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    component: "WebUIBackendComponent" = Depends(get_sac_component),
    project_service: ProjectService | None = Depends(get_project_service_optional),
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
        project_service=project_service,
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
    Returns 404 if the task context is not found.
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
        log.warning(
            "%sNo active task context found for task ID: %s",
            log_prefix,
            taskId,
        )
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
