"""
API Router for submitting and managing tasks to agents.
Includes background task status endpoints.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import yaml
from a2a.types import (
    CancelTaskRequest,
    SendMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ....gateway.http_sse.services.project_service import ProjectService

from ....agent.utils.artifact_helpers import (
    get_artifact_info_list,
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
from ....gateway.http_sse.repository.task_repository import TaskRepository
from ....gateway.http_sse.services.session_service import SessionService
from ....gateway.http_sse.services.task_service import TaskService
from ....gateway.http_sse.session_manager import SessionManager
from solace_agent_mesh.shared.api.pagination import PaginationParams
from solace_agent_mesh.shared.utils.types import UserId
from ..utils.stim_utils import create_stim_from_task_data

if TYPE_CHECKING:
    from ....gateway.http_sse.component import WebUIBackendComponent

router = APIRouter()

log = logging.getLogger(__name__)


# Background Task Status Models and Endpoints
class TaskStatusResponse(BaseModel):
    """Response model for task status queries."""
    task: Task
    is_running: bool
    is_background: bool
    can_reconnect: bool


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, tags=["Tasks"])
async def get_task_status(
    task_id: str,
    db: DBSession = Depends(get_db),
):
    """
    Get the current status of a task.
    Used by frontend to check if a background task is still running.
    
    Args:
        task_id: The task ID to query
        
    Returns:
        Task status information including whether it's running and can be reconnected to
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}/status] "
    log.debug("%sQuerying task status", log_prefix)
    
    repo = TaskRepository()
    task = repo.find_by_id(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Determine if task is still running
    is_running = task.status in [None, "running", "pending"] and task.end_time is None
    
    # Check if it's a background task
    is_background = task.background_execution_enabled or False
    
    # Can reconnect if it's a background task and still running
    can_reconnect = is_background and is_running
    
    log.info(
        "%sTask status: running=%s, background=%s, can_reconnect=%s",
        log_prefix,
        is_running,
        is_background,
        can_reconnect,
    )
    
    return TaskStatusResponse(
        task=task,
        is_running=is_running,
        is_background=is_background,
        can_reconnect=can_reconnect
    )


@router.get("/tasks/background/active", tags=["Tasks"])
async def get_active_background_tasks(
    user_id: str = Query(..., description="User ID to filter tasks"),
    db: DBSession = Depends(get_db),
):
    """
    Get all active background tasks for a user.
    Used by frontend on session load to detect running background tasks.
    
    Args:
        user_id: The user ID to filter by
        
    Returns:
        List of active background tasks
    """
    log_prefix = "[GET /api/v1/tasks/background/active] "
    log.debug("%sQuerying active background tasks for user %s", log_prefix, user_id)
    
    repo = TaskRepository()
    
    # Get all background tasks
    all_background_tasks = repo.find_background_tasks_by_status(db, status=None)
    
    # Filter by user and running status
    active_tasks = [
        task for task in all_background_tasks
        if task.user_id == user_id
        and task.status in [None, "running", "pending"]
        and task.end_time is None
    ]
    
    log.info("%sFound %d active background tasks for user %s", log_prefix, len(active_tasks), user_id)
    
    return {
        "tasks": active_tasks,
        "count": len(active_tasks)
    }


# =============================================================================
# Project Context Injection Helper
# =============================================================================


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
    from ..utils.artifact_copy_utils import copy_project_artifacts_to_session

    if SessionLocal is None:
        log.warning(
            "%sProject context injection skipped: database not configured", log_prefix
        )
        return message_text

    db = SessionLocal()
    artifact_service = None

    try:
        project = project_service.get_project(db, project_id, user_id)
        if not project:
            return message_text

        context_parts = []

        # Only inject full context for new sessions
        if inject_full_context:
            # Start with clear workspace framing
            context_parts.append(
                f'You are working in the project workspace: "{project.name}"'
            )

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
                artifacts_copied, new_artifact_names = await copy_project_artifacts_to_session(
                    project_id=project_id,
                    user_id=user_id,
                    session_id=session_id,
                    project_service=project_service,
                    component=component,
                    db=db,
                    log_prefix=log_prefix,
                )

                # Get artifact descriptions for context injection
                if artifacts_copied > 0 or inject_full_context:
                    source_user_id = project.user_id
                    project_artifacts_session_id = f"project-{project.id}"

                    project_artifacts = await get_artifact_info_list(
                        artifact_service=artifact_service,
                        app_name=project_service.app_name,
                        user_id=source_user_id,
                        session_id=project_artifacts_session_id,
                    )

                    if project_artifacts:
                        # For new sessions - all files
                        all_artifact_descriptions = []
                        # For existing sessions - only new files
                        new_artifact_descriptions = []

                        for artifact_info in project_artifacts:
                            # Build description for all artifacts (for new sessions)
                            desc_str = f"- {artifact_info.filename}"
                            if artifact_info.description:
                                desc_str += f": {artifact_info.description}"
                            all_artifact_descriptions.append(desc_str)

                            # Track new artifacts for existing sessions
                            if artifact_info.filename in new_artifact_names:
                                new_artifact_descriptions.append(desc_str)

                        # Add artifact descriptions to context
                        files_added_header = (
                            "\nNew Files Added to Session:\n"
                            "The following files have been added to your session (in addition to any files already present):\n"
                        )

                        if inject_full_context and all_artifact_descriptions:
                            # New session: show all project files
                            artifacts_context = files_added_header + "\n".join(all_artifact_descriptions)
                            context_parts.append(artifacts_context)
                        elif not inject_full_context and new_artifact_descriptions:
                            # Existing session: notify about newly added files
                            new_files_context = files_added_header + "\n".join(new_artifact_descriptions)
                            context_parts.append(new_files_context)

            except Exception as e:
                log.warning(
                    "%sFailed to copy project artifacts to session: %s", log_prefix, e
                )
                # Do not fail the entire request, just log the warning

        # Inject all gathered context into the message, ending with user query
        # Only modify message text if we're injecting full context (new sessions)
        modified_message_text = message_text
        if context_parts:
            project_context = "\n".join(context_parts)
            modified_message_text = f"{project_context}\n\nUSER QUERY:\n{message_text}"
            log.debug("%sInjected full project context for project: %s", log_prefix, project_id)
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
                    session_details = session_service.get_session_details(
                        db, frontend_session_id, user_id
                    )
                    if session_details and session_details.project_id:
                        project_id = session_details.project_id
                        log.info(
                            "%sFound project_id %s from session database for session %s",
                            log_prefix,
                            project_id,
                            frontend_session_id,
                        )
                except Exception as e:
                    log.warning(
                        "%sFailed to lookup session project_id: %s", log_prefix, e
                    )
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
            # Determine if we should inject full context:
            should_inject_full_context = not frontend_session_id

            # Check if there are artifacts with pending project context
            if frontend_session_id and not should_inject_full_context:
                from ..utils.artifact_copy_utils import has_pending_project_context
                from ....gateway.http_sse.dependencies import SessionLocal

                artifact_service = component.get_shared_artifact_service()
                if artifact_service and SessionLocal:
                    db = SessionLocal()
                    try:
                        has_pending = await has_pending_project_context(
                            user_id=client_id,
                            session_id=session_id,
                            artifact_service=artifact_service,
                            app_name=component.gateway_id,
                            db=db,
                        )
                        if has_pending:
                            should_inject_full_context = True
                            log.info(
                                "%sDetected pending project context for session %s, will inject full context",
                                log_prefix,
                                session_id,
                            )
                    finally:
                        db.close()

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
                modified_message = a2a.update_message_parts(
                    payload.params.message, new_parts
                )

        # Use the helper to get the unwrapped parts from the modified message (with project context if applied).
        a2a_parts = a2a.get_parts_from_message(modified_message)

        external_req_ctx = {
            "app_name_for_artifacts": component.gateway_id,
            "user_id_for_artifacts": client_id,
            "a2a_session_id": session_id,  # This may have been updated by persistence layer
            "user_id_for_a2a": client_id,
            "target_agent_name": agent_name,
        }

        # Extract additional metadata from the message (e.g., background execution settings)
        # This metadata will be passed through to the A2A message for the task logger
        additional_metadata = {}
        if payload.params and payload.params.message and payload.params.message.metadata:
            msg_metadata = payload.params.message.metadata
            # Pass through background execution settings
            if msg_metadata.get("backgroundExecutionEnabled"):
                additional_metadata["backgroundExecutionEnabled"] = msg_metadata.get("backgroundExecutionEnabled")
            if msg_metadata.get("maxExecutionTimeMs"):
                additional_metadata["maxExecutionTimeMs"] = msg_metadata.get("maxExecutionTimeMs")

        task_id = await component.submit_a2a_task(
            target_agent_name=agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_req_ctx,
            user_identity=user_identity,
            is_streaming=is_streaming,
            metadata=additional_metadata if additional_metadata else None,
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


@router.get("/tasks/{task_id}/events", tags=["Tasks"])
async def get_task_events(
    task_id: str,
    request: FastAPIRequest,
    db: DBSession = Depends(get_db),
    user_id: UserId = Depends(get_user_id),
    user_config: dict = Depends(get_user_config),
    repo: ITaskRepository = Depends(get_task_repository),
):
    """
    Retrieves the complete event history for a task and all its child tasks as JSON.
    Returns events in the same format as the SSE stream for workflow visualization.
    Recursively loads all descendant tasks to enable full workflow rendering.
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}/events] "
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

        # Transform task events into A2AEventSSEPayload format for the frontend
        # Need to reconstruct the SSE structure from stored data
        formatted_events = []
        
        for event in events:
            # event.payload contains the raw A2A JSON-RPC message
            # event.created_time is epoch milliseconds
            # event.direction is simplified (request, response, status, error, etc)

            # Convert timestamp from epoch milliseconds to ISO 8601
            from datetime import datetime, timezone
            timestamp_dt = datetime.fromtimestamp(event.created_time / 1000, tz=timezone.utc)
            timestamp_iso = timestamp_dt.isoformat()

            # Extract metadata from payload using similar logic to SSE component
            payload = event.payload
            message_id = payload.get("id")
            source_entity = "unknown"
            target_entity = "unknown"
            method = "N/A"

            # Parse based on direction
            if event.direction == "request":
                # It's a request - extract target from message metadata
                method = payload.get("method", "N/A")
                if "params" in payload and "message" in payload.get("params", {}):
                    message = payload["params"]["message"]
                    if isinstance(message, dict) and "metadata" in message:
                        target_entity = message["metadata"].get("agent_name", "unknown")
            elif event.direction in ["status", "response", "error"]:
                # It's a response - extract source from result metadata
                if "result" in payload:
                    result = payload["result"]
                    if isinstance(result, dict):
                        # Check for agent_name in metadata
                        if "metadata" in result:
                            source_entity = result["metadata"].get("agent_name", "unknown")
                        # For status updates, check the message inside
                        if "message" in result:
                            message = result["message"]
                            if isinstance(message, dict) and "metadata" in message:
                                if source_entity == "unknown":
                                    source_entity = message["metadata"].get("agent_name", "unknown")

            # Map stored direction to SSE direction format
            direction_map = {
                "request": "request",
                "response": "task",
                "status": "status-update",
                "error": "error_response",
            }
            sse_direction = direction_map.get(event.direction, event.direction)

            # Build the A2AEventSSEPayload structure
            formatted_event = {
                "event_type": "a2a_message",
                "timestamp": timestamp_iso,
                "solace_topic": event.topic,
                "direction": sse_direction,
                "source_entity": source_entity,
                "target_entity": target_entity,
                "message_id": message_id,
                "task_id": task_id,
                "payload_summary": {
                    "method": method,
                    "params_preview": None,
                },
                "full_payload": payload,
            }
            formatted_events.append(formatted_event)

        # Use database-level query to get all related tasks efficiently
        related_task_ids = repo.find_all_by_parent_chain(db, task_id)
        log.info(
            "%sFound %d related tasks for task_id %s",
            log_prefix,
            len(related_task_ids),
            task_id,
        )

        # Load and format all related tasks
        all_tasks = {}
        all_tasks[task_id] = {
            "events": formatted_events,
            "initial_request_text": task.initial_request_text or "",
        }

        # Load remaining related tasks
        for tid in related_task_ids:
            if tid == task_id:
                continue  # Already loaded

            task_result = repo.find_by_id_with_events(db, tid)
            if not task_result:
                continue

            related_task, related_events = task_result

            # Check permissions for each related task
            if related_task.user_id != user_id and not can_read_all:
                log.warning(
                    "%sSkipping related task %s due to permission check",
                    log_prefix,
                    tid,
                )
                continue

            # Format events for this related task
            related_formatted_events = []
            
            for event in related_events:
                from datetime import datetime, timezone

                timestamp_dt = datetime.fromtimestamp(
                    event.created_time / 1000, tz=timezone.utc
                )
                timestamp_iso = timestamp_dt.isoformat()
                payload = event.payload
                message_id = payload.get("id")
                source_entity = "unknown"
                target_entity = "unknown"
                method = "N/A"

                if event.direction == "request":
                    method = payload.get("method", "N/A")
                    if "params" in payload and "message" in payload.get("params", {}):
                        message = payload["params"]["message"]
                        if isinstance(message, dict) and "metadata" in message:
                            target_entity = message["metadata"].get(
                                "agent_name", "unknown"
                            )
                elif event.direction in ["status", "response", "error"]:
                    if "result" in payload:
                        result = payload["result"]
                        if isinstance(result, dict):
                            if "metadata" in result:
                                source_entity = result["metadata"].get(
                                    "agent_name", "unknown"
                                )
                            if "message" in result:
                                message = result["message"]
                                if isinstance(message, dict) and "metadata" in message:
                                    if source_entity == "unknown":
                                        source_entity = message["metadata"].get(
                                            "agent_name", "unknown"
                                        )

                direction_map = {
                    "request": "request",
                    "response": "task",
                    "status": "status-update",
                    "error": "error_response",
                }
                sse_direction = direction_map.get(event.direction, event.direction)

                formatted_event = {
                    "event_type": "a2a_message",
                    "timestamp": timestamp_iso,
                    "solace_topic": event.topic,
                    "direction": sse_direction,
                    "source_entity": source_entity,
                    "target_entity": target_entity,
                    "message_id": message_id,
                    "task_id": tid,
                    "payload_summary": {"method": method, "params_preview": None},
                    "full_payload": payload,
                }
                related_formatted_events.append(formatted_event)

            all_tasks[tid] = {
                "events": related_formatted_events,
                "initial_request_text": related_task.initial_request_text or "",
            }

        # Return all tasks (parent + children) for the frontend to process
        return {"tasks": all_tasks}

    except HTTPException:
        # Re-raise HTTPExceptions (404, 403, etc.) without modification
        raise
    except Exception as e:
        log.exception("%sError retrieving task events: %s", log_prefix, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the task events.",
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
    Retrieves the complete event history for a task and all its child tasks, returning it as a `.stim` file.
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}] "
    log.info("%sRequest from user %s", log_prefix, user_id)

    try:
        # Find all related task IDs (parent chain + all children)
        related_task_ids = repo.find_all_by_parent_chain(db, task_id)

        if not related_task_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID '{task_id}' not found.",
            )

        # Load all tasks and their events
        tasks_dict = {}
        events_dict = {}
        can_read_all = user_config.get("scopes", {}).get("tasks:read:all", False)

        for tid in related_task_ids:
            result = repo.find_by_id_with_events(db, tid)
            if result:
                task, events = result

                # Check permissions for each task
                if task.user_id != user_id and not can_read_all:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to view this task.",
                    )

                tasks_dict[tid] = task
                events_dict[tid] = events

        if task_id not in tasks_dict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID '{task_id}' not found.",
            )

        # Determine the root task (the one without a parent)
        root_task_id = task_id
        for tid, task in tasks_dict.items():
            if task.parent_task_id is None:
                root_task_id = tid
                break

        # Format into .stim structure with all tasks
        from ..utils.stim_utils import create_stim_from_task_hierarchy
        stim_data = create_stim_from_task_hierarchy(tasks_dict, events_dict, root_task_id)

        yaml_content = yaml.dump(
            stim_data,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
            default_flow_style=False,
        )

        return Response(
            content=yaml_content,
            media_type="application/yaml",
            headers={"Content-Disposition": f'attachment; filename="{root_task_id}.stim"'},
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
    db: DBSession = Depends(get_db),
):
    """
    Sends a cancellation request for a specific task to the specified agent.
    Also sends cancellation requests to all active child tasks (e.g., workflows).
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

        # Send cancel to the original target agent
        await task_service.cancel_task(agent_name, taskId, client_id, client_id)
        log.info("%sCancellation request sent to original target '%s'", log_prefix, agent_name)

        # Also send cancel requests to all active child tasks (e.g., workflows)
        # This ensures that when an orchestrator delegates to a workflow, the workflow
        # also receives the cancellation request
        if not db:
            log.warning("%sDatabase session not available, skipping child task cancellation", log_prefix)
            log.info("%sCancellation request(s) published successfully.", log_prefix)
            return {"message": "Cancellation request sent"}

        try:
            repo = TaskRepository()
            log.info("%sLooking up active child tasks for parent task '%s'", log_prefix, taskId)
            
            # Find children by parent_task_id column
            active_children = repo.find_active_children(db, taskId)
            log.info("%sfind_active_children returned %d children: %s", log_prefix, len(active_children), active_children)
            
            if not active_children:
                log.debug("%sNo active child tasks found", log_prefix)
                log.info("%sCancellation request(s) published successfully.", log_prefix)
                return {"message": "Cancellation request sent"}

            log.info(
                "%sFound %d active child task(s) to cancel: %s",
                log_prefix,
                len(active_children),
                [child_id for child_id, _ in active_children],
            )
            
            for child_task_id, child_agent_name in active_children:
                if child_agent_name:
                    try:
                        await task_service.cancel_task(
                            child_agent_name, child_task_id, client_id, client_id
                        )
                        log.info(
                            "%sCancellation request sent to child task '%s' (agent: '%s')",
                            log_prefix,
                            child_task_id,
                            child_agent_name,
                        )
                    except Exception as child_err:
                        log.warning(
                            "%sFailed to send cancellation to child task '%s': %s",
                            log_prefix,
                            child_task_id,
                            child_err,
                        )
                else:
                    log.warning(
                        "%sCould not determine target agent for child task '%s', skipping",
                        log_prefix,
                        child_task_id,
                    )
        except Exception as db_err:
            # Don't fail the main cancellation if child lookup fails
            log.warning(
                "%sFailed to look up child tasks for cancellation: %s",
                log_prefix,
                db_err,
            )

        log.info("%sCancellation request(s) published successfully.", log_prefix)

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
