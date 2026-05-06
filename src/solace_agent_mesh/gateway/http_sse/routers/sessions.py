import asyncio
import json
import logging
import re
import time
import uuid
from typing import Optional, TYPE_CHECKING
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ....common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_in_string,
)
from ....common.utils.embeds.types import ResolutionMode
from ....common.utils.templates import resolve_template_blocks_in_string
from ..dependencies import get_session_business_service, get_db, get_title_generation_service, get_shared_artifact_service, get_sac_component, get_config_resolver, get_user_config, get_adk_session_service
from ..services.session_service import SessionService
from solace_agent_mesh.shared.api.auth_utils import get_current_user
from solace_agent_mesh.shared.api.pagination import DataResponse, PaginatedResponse, PaginationParams
from solace_agent_mesh.shared.api.response_utils import create_data_response
from .dto.requests.session_requests import (
    GetSessionRequest,
    UpdateSessionRequest,
    MoveSessionRequest,
    SearchSessionsRequest,
)
from .dto.requests.task_requests import SaveTaskRequest
from .dto.responses.session_responses import SessionResponse
from .dto.responses.task_responses import TaskResponse, TaskListResponse

if TYPE_CHECKING:
    from ..services.title_generation_service import TitleGenerationService

log = logging.getLogger(__name__)

router = APIRouter()

SESSION_NOT_FOUND_MSG = "Session not found."


def _enrich_scheduler_sessions_with_task_info(db: Session, session_responses: list[SessionResponse]) -> None:
    """For sessions created by the scheduler, attach scheduled_task_id + name.

    Scheduler-created sessions use ids of the form ``scheduled_<execution_id>``
    (see SchedulerService._submit_task_to_agent_mesh). We extract the execution
    id, batch-query the executions + tasks tables, and fill in the response
    fields so the UI can link each card back to its originating schedule.

    Single query regardless of how many sessions are in the page; no-op if
    the page has no scheduler sessions.
    """
    scheduler_sessions = [s for s in session_responses if s.source == "scheduler" and s.id.startswith("scheduled_")]
    if not scheduler_sessions:
        return

    execution_ids = [s.id[len("scheduled_"):] for s in scheduler_sessions]

    from ..repository.models import ScheduledTaskExecutionModel, ScheduledTaskModel
    rows = (
        db.query(
            ScheduledTaskExecutionModel.id,
            ScheduledTaskExecutionModel.scheduled_task_id,
            ScheduledTaskModel.name,
        )
        .join(ScheduledTaskModel, ScheduledTaskModel.id == ScheduledTaskExecutionModel.scheduled_task_id)
        .filter(ScheduledTaskExecutionModel.id.in_(execution_ids))
        .all()
    )
    by_execution = {row[0]: (row[1], row[2]) for row in rows}

    for session in scheduler_sessions:
        exec_id = session.id[len("scheduled_"):]
        mapping = by_execution.get(exec_id)
        if mapping:
            session.scheduled_task_id, session.scheduled_task_name = mapping


@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def get_all_sessions(
    project_id: Optional[str] = Query(default=None, alias="project_id"),
    source: Optional[str] = Query(default=None, description="Filter by source: chat, scheduler, or omit for all"),
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
):
    _VALID_SOURCES = {"chat", "scheduler"}
    if source is not None and source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source filter: {source}. Must be one of: {', '.join(sorted(_VALID_SOURCES))}",
        )

    # Require scheduling permission to list scheduler sessions
    if source == "scheduler":
        operation_spec = {"operation_type": "scheduling"}
        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, {"source": "sessions_endpoint"}
        )
        if not validation_result.get("valid", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view scheduler sessions",
            )

    user_id = user.get("id")
    log_msg = f"User '{user_id}' is listing sessions with pagination (page={page_number}, size={page_size})"
    if project_id:
        log_msg += f" filtered by project_id={project_id}"
    if source:
        log_msg += f" filtered by source={source}"
    log.info(log_msg)

    try:
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        paginated_response = session_service.get_user_sessions(db, user_id, pagination, project_id=project_id, source=source)

        session_responses = []
        for session_domain in paginated_response.data:
            session_response = SessionResponse(
                id=session_domain.id,
                user_id=session_domain.user_id,
                name=session_domain.name,
                agent_id=session_domain.agent_id,
                project_id=session_domain.project_id,
                project_name=session_domain.project_name,
                source=session_domain.source,
                has_running_background_task=session_domain.has_running_background_task,
                created_time=session_domain.created_time,
                updated_time=session_domain.updated_time,
                last_viewed_at=session_domain.last_viewed_at,
            )
            session_responses.append(session_response)

        _enrich_scheduler_sessions_with_task_info(db, session_responses)

        return PaginatedResponse(data=session_responses, meta=paginated_response.meta)

    except Exception as e:
        log.error("Error fetching sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions",
        ) from e


@router.get("/sessions/search", response_model=PaginatedResponse[SessionResponse])
async def search_sessions(
    query: str = Query(..., min_length=1, description="Search query"),
    project_id: Optional[str] = Query(default=None, alias="projectId"),
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Search sessions by name/title only.
    """
    user_id = user.get("id")
    log.info(
        "User %s searching sessions with query '%s' (page=%d, size=%d)",
        user_id,
        query,
        page_number,
        page_size,
    )

    try:
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        paginated_response = session_service.search_sessions(
            db, user_id, query, pagination, project_id=project_id
        )

        session_responses = []
        for session_domain in paginated_response.data:
            session_response = SessionResponse(
                id=session_domain.id,
                user_id=session_domain.user_id,
                name=session_domain.name,
                agent_id=session_domain.agent_id,
                project_id=session_domain.project_id,
                project_name=session_domain.project_name,
                source=session_domain.source,
                has_running_background_task=session_domain.has_running_background_task,
                created_time=session_domain.created_time,
                updated_time=session_domain.updated_time,
                last_viewed_at=session_domain.last_viewed_at,
            )
            session_responses.append(session_response)

        return PaginatedResponse(data=session_responses, meta=paginated_response.meta)

    except ValueError as e:
        log.warning("Validation error searching sessions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        log.error("Error searching sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search sessions",
        ) from e


@router.get("/sessions/{session_id}", response_model=DataResponse[SessionResponse])
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        request_dto = GetSessionRequest(session_id=session_id, user_id=user_id)

        session_domain = session_service.get_session_details(
            db=db, session_id=request_dto.session_id, user_id=request_dto.user_id
        )

        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        log.info("User %s authorized. Fetching session_id: %s", user_id, session_id)

        session_response = SessionResponse(
            id=session_domain.id,
            user_id=session_domain.user_id,
            name=session_domain.name,
            agent_id=session_domain.agent_id,
            project_id=session_domain.project_id,
            created_time=session_domain.created_time,
            updated_time=session_domain.updated_time,
        )

        return create_data_response(session_response)

    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session",
        ) from e


@router.post("/sessions/{session_id}/chat-tasks", response_model=TaskResponse)
async def save_task(
    session_id: str,
    request: SaveTaskRequest,
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
    artifact_service = Depends(get_shared_artifact_service),
    component = Depends(get_sac_component),
):
    """
    Save a complete task interaction (upsert).
    Creates a new task or updates an existing one.
    """
    user_id = user.get("id")
    log.debug(
        "User %s attempting to save task %s for session %s",
        user_id,
        request.task_id,
        session_id,
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )
        
        # Resolve embeds in message_bubbles before saving
        message_bubbles = request.message_bubbles
        if artifact_service and message_bubbles and '«' in message_bubbles:
            try:
                # Parse the message bubbles JSON
                bubbles = json.loads(message_bubbles)
                resolved_bubbles = []
                
                gateway_id = component.gateway_id if component else "webui"
                
                for bubble in bubbles:
                    if isinstance(bubble, dict):
                        # Resolve embeds in the text field
                        text = bubble.get("text", "")
                        if text and '«' in text:
                            embed_eval_context = {
                                "artifact_service": artifact_service,
                                "session_context": {
                                    "app_name": gateway_id,
                                    "user_id": user_id,
                                    "session_id": session_id,
                                },
                            }
                            embed_eval_config = {
                                "gateway_max_artifact_resolve_size_bytes": 1024 * 1024,  # 1MB limit
                                "gateway_recursive_embed_depth": 3,
                            }
                            
                            resolved_text, _, signals = await resolve_embeds_in_string(
                                text=text,
                                context=embed_eval_context,
                                resolver_func=evaluate_embed,
                                types_to_resolve=LATE_EMBED_TYPES,
                                resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
                                log_identifier=f"[SaveTask:{request.task_id}]",
                                config=embed_eval_config,
                            )
                            
                            # Resolve template blocks (template_liquid)
                            if '«««template' in resolved_text:
                                resolved_text = await resolve_template_blocks_in_string(
                                    text=resolved_text,
                                    artifact_service=artifact_service,
                                    session_context={
                                        "app_name": gateway_id,
                                        "user_id": user_id,
                                        "session_id": session_id,
                                    },
                                    log_identifier=f"[SaveTask:{request.task_id}][TemplateResolve]",
                                )
                            
                            # Strip status_update embeds (they're for real-time display only)
                            status_update_pattern = r'«status_update:[^»]+»\n?'
                            resolved_text = re.sub(status_update_pattern, '', resolved_text)
                            
                            # Strip any remaining template blocks that weren't resolved
                            template_block_pattern = r'«««template(?:_liquid)?:[^\n]+\n(?:(?!»»»).)*?»»»'
                            resolved_text = re.sub(template_block_pattern, '', resolved_text, flags=re.DOTALL)
                            
                            bubble["text"] = resolved_text
                            
                            # Also resolve embeds and templates in parts if they contain text
                            parts = bubble.get("parts", [])
                            resolved_parts = []
                            for part in parts:
                                if isinstance(part, dict) and part.get("kind") == "text":
                                    part_text = part.get("text", "")
                                    if part_text and '«' in part_text:
                                        resolved_part_text, _, _ = await resolve_embeds_in_string(
                                            text=part_text,
                                            context=embed_eval_context,
                                            resolver_func=evaluate_embed,
                                            types_to_resolve=LATE_EMBED_TYPES,
                                            resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER,
                                            log_identifier=f"[SaveTask:{request.task_id}]",
                                            config=embed_eval_config,
                                        )
                                        # Resolve template blocks in parts
                                        if '«««template' in resolved_part_text:
                                            resolved_part_text = await resolve_template_blocks_in_string(
                                                text=resolved_part_text,
                                                artifact_service=artifact_service,
                                                session_context={
                                                    "app_name": gateway_id,
                                                    "user_id": user_id,
                                                    "session_id": session_id,
                                                },
                                                log_identifier=f"[SaveTask:{request.task_id}][TemplateResolve]",
                                            )
                                        part["text"] = resolved_part_text
                                resolved_parts.append(part)
                            bubble["parts"] = resolved_parts
                    
                    resolved_bubbles.append(bubble)
                
                message_bubbles = json.dumps(resolved_bubbles)
                log.debug("Resolved embeds in message_bubbles for task %s", request.task_id)
            except Exception as e:
                log.warning(
                    "Failed to resolve embeds in message_bubbles for task %s: %s. Saving as-is.",
                    request.task_id,
                    e,
                )
        
        from ..dependencies import SessionLocal
        if SessionLocal is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Session management requires database configuration.",
            )
        
        db = SessionLocal()
        is_update = False
        saved_task = None
        
        try:
            # Check if task already exists to determine status code
            from ..repository.chat_task_repository import ChatTaskRepository
            task_repo = ChatTaskRepository()
            existing_task = task_repo.find_by_id(db, request.task_id, user_id)
            is_update = existing_task is not None

            # Save the task - pass strings directly
            # Use the resolved message_bubbles if embeds were resolved, otherwise use the original
            saved_task = session_service.save_task(
                db=db,
                task_id=request.task_id,
                session_id=session_id,
                user_id=user_id,
                user_message=request.user_message,
                message_bubbles=message_bubbles,  # Use resolved message_bubbles
                task_metadata=request.task_metadata,  # Already a string
            )
            
            # Guard against None return from save_task
            if saved_task is None:
                raise ValueError(
                    f"save_task returned None for task_id={request.task_id}"
                )
            
            # Commit the transaction immediately after DB operations
            db.commit()
            
            log.info(
                "Task %s %s successfully for session %s",
                request.task_id,
                "updated" if is_update else "created",
                session_id,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # Clear SSE event buffer for this task (implicit cleanup)
        # This is done AFTER the DB transaction is committed
        try:
            log.debug(
                "[BufferCleanup] Task %s: Starting cleanup. component=%s, sse_manager=%s",
                request.task_id,
                component is not None,
                component.sse_manager is not None if component else False,
            )
            if component and component.sse_manager:
                persistent_buffer = component.sse_manager.get_persistent_buffer()
                log.debug(
                    "[BufferCleanup] Task %s: persistent_buffer=%s, is_enabled=%s",
                    request.task_id,
                    persistent_buffer is not None,
                    persistent_buffer.is_enabled() if persistent_buffer else False,
                )
                if persistent_buffer and persistent_buffer.is_enabled():
                    deleted_count = persistent_buffer.delete_events_for_task(request.task_id)
                    if deleted_count > 0:
                        log.info(
                            "[BufferCleanup] Task %s: Cleared %d buffered SSE events after chat_task save",
                            request.task_id,
                            deleted_count,
                        )
                else:
                    log.debug(
                        "[BufferCleanup] Task %s: Buffer disabled or not available, skipping cleanup",
                        request.task_id,
                    )
            else:
                log.debug(
                    "[BufferCleanup] Task %s: No component or sse_manager available",
                    request.task_id,
                )
        except Exception as buffer_error:
            # Non-critical - buffer will be cleaned up by retention policy
            log.warning(
                "[BufferCleanup] Task %s: Failed to clear buffer: %s",
                request.task_id,
                buffer_error,
            )

        # Convert to response DTO
        response = TaskResponse(
            task_id=saved_task.id,
            session_id=saved_task.session_id,
            user_message=saved_task.user_message,
            message_bubbles=saved_task.message_bubbles,
            task_metadata=saved_task.task_metadata,
            created_time=saved_task.created_time,
            updated_time=saved_task.updated_time,
        )

        return response

    except ValueError as e:
        log.warning("Validation error saving task %s: %s", request.task_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error saving task %s for session %s for user %s: %s",
            request.task_id,
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save task",
        ) from e


@router.get("/sessions/{session_id}/chat-tasks", response_model=TaskListResponse)
async def get_session_tasks(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Get all tasks for a session.
    Returns tasks in chronological order.
    """
    user_id = user.get("id")
    log.info(
        "User %s attempting to fetch tasks for session_id: %s", user_id, session_id
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        # Get tasks from service
        tasks = session_service.get_session_tasks(
            db=db, session_id=session_id, user_id=user_id
        )

        log.info(
            "User %s authorized. Fetched %d tasks for session_id: %s",
            user_id,
            len(tasks),
            session_id,
        )

        # Convert to response DTOs
        task_responses = []
        for task in tasks:
            task_response = TaskResponse(
                task_id=task.id,
                session_id=task.session_id,
                user_message=task.user_message,
                message_bubbles=task.message_bubbles,
                task_metadata=task.task_metadata,
                created_time=task.created_time,
                updated_time=task.updated_time,
            )
            task_responses.append(task_response)

        return TaskListResponse(tasks=task_responses)

    except ValueError as e:
        log.warning("Validation error fetching tasks for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching tasks for session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session tasks",
        ) from e


@router.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Get session message history.
    Loads from chat_tasks and flattens message_bubbles for backward compatibility.
    """
    user_id = user.get("id")
    log.info(
        "User %s attempting to fetch history for session_id: %s", user_id, session_id
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        # Use task-based message retrieval (returns list of dicts)
        messages = session_service.get_session_messages_from_tasks(
            db=db, session_id=session_id, user_id=user_id
        )

        log.info(
            "User %s authorized. Fetched %d messages for session_id: %s",
            user_id,
            len(messages),
            session_id,
        )

        # Convert snake_case to camelCase for backwards compatibility
        camel_case_messages = []
        for msg in messages:
            camel_msg = {
                "id": msg["id"],
                "sessionId": msg["session_id"],
                "message": msg["message"],
                "senderType": msg["sender_type"],
                "senderName": msg["sender_name"],
                "messageType": msg["message_type"],
                "createdTime": msg["created_time"],
            }
            camel_case_messages.append(camel_msg)

        return camel_case_messages

    except ValueError as e:
        log.warning(
            "Validation error fetching history for session %s: %s", session_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "Error fetching history for session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session history",
        ) from e


@router.get("/sessions/{session_id}/events/unconsumed")
async def get_session_unconsumed_events(
    session_id: str,
    include_events: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Check for unconsumed buffered SSE events for a session.
    
    This endpoint is used by the frontend to determine if there are
    any buffered events that need to be replayed when switching to a session.
    
    In the unified event buffer architecture:
    1. Frontend switches to a session
    2. Frontend calls this endpoint with include_events=true to get all buffered events in one request
    3. Frontend replays events through handleSseMessage
    4. Frontend saves to chat_tasks (which implicitly cleans up buffer)
    
    Query Parameters:
        include_events: If true, include the actual event data in the response.
                       This enables batched retrieval to avoid N+1 queries.
    
    Returns:
        JSON object with:
        - has_events: boolean indicating if there are unconsumed events
        - task_ids: list of task IDs with unconsumed events
        - events_by_task: (only if include_events=true) dict mapping task_id to list of events
    """
    user_id = user.get("id")
    log.info(
        "User %s checking for unconsumed events in session %s (include_events=%s)",
        user_id, session_id, include_events
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        # Verify user owns this session
        session_domain = session_service.get_session_details(
            db=db, session_id=session_id, user_id=user_id
        )
        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        # Get the SSE manager to access the persistent buffer
        from ..dependencies import get_sac_component
        from ..component import WebUIBackendComponent
        
        component: WebUIBackendComponent = get_sac_component()
        
        if component is None:
            log.warning("WebUI backend component not available")
            return {"has_events": False, "task_ids": [], "events_by_task": {} if include_events else None}
        
        sse_manager = component.sse_manager
        persistent_buffer = sse_manager.get_persistent_buffer() if sse_manager else None
        if persistent_buffer is None:
            log.debug("Persistent buffer not available")
            return {"has_events": False, "task_ids": [], "events_by_task": {} if include_events else None}
        
        # Get unconsumed events for this session (already grouped by task_id)
        unconsumed_by_task = persistent_buffer.get_unconsumed_events_for_session(session_id)
        
        task_ids = list(unconsumed_by_task.keys())
        has_events = len(task_ids) > 0
        
        log.info(
            "Session %s has %d tasks with unconsumed events: %s",
            session_id,
            len(task_ids),
            task_ids
        )
        
        response = {
            "has_events": has_events,
            "task_ids": task_ids,
            "session_id": session_id
        }
        
        # Include actual events if requested (enables batched retrieval)
        if include_events:
            # Convert events to the format expected by frontend
            # Format matches the per-task endpoint: {events_buffered: bool, events: [...]}
            events_by_task = {}
            for task_id, events in unconsumed_by_task.items():
                events_by_task[task_id] = {
                    "events_buffered": len(events) > 0,
                    "events": [
                        {
                            "sequence": event.get("event_sequence", 0),
                            "event_type": event.get("event_type", "message"),
                            "data": event.get("event_data", {}),
                        }
                        for event in events
                    ]
                }
            response["events_by_task"] = events_by_task
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        log.exception(
            "Error checking unconsumed events for session %s, user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check unconsumed events",
        ) from e


@router.post("/sessions/{session_id}/viewed", status_code=status.HTTP_200_OK)
async def mark_session_viewed(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """Record that the user has viewed this session.

    Sets ``last_viewed_at`` to the server's current epoch-ms without touching
    ``updated_time``. Used by the UI to clear the "unseen updates" dot.
    """
    user_id = user.get("id")

    if not session_id or session_id.strip() == "" or session_id in ["null", "undefined"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
        )

    try:
        viewed_at = session_service.mark_session_viewed(
            db=db, session_id=session_id, user_id=user_id
        )
        if viewed_at is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )
        return {"lastViewedAt": viewed_at}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        log.error(
            "Error marking session %s viewed for user %s: %s", session_id, user_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark session viewed",
        ) from e


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session_name(
    session_id: str,
    name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log.info("User %s attempting to update session %s", user_id, session_id)

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        request_dto = UpdateSessionRequest(
            session_id=session_id, user_id=user_id, name=name
        )

        updated_domain = session_service.update_session_name(
            db=db,
            session_id=request_dto.session_id,
            user_id=request_dto.user_id,
            name=request_dto.name,
        )

        if not updated_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        log.info("Session %s updated successfully", session_id)

        return SessionResponse(
            id=updated_domain.id,
            user_id=updated_domain.user_id,
            name=updated_domain.name,
            agent_id=updated_domain.agent_id,
            project_id=updated_domain.project_id,
            created_time=updated_domain.created_time,
            updated_time=updated_domain.updated_time,
        )

    except HTTPException:
        raise
    except ValidationError as e:
        log.warning("Pydantic validation error updating session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except ValueError as e:
        log.warning("Validation error updating session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        log.error(
            "Error updating session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session",
        ) from e


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Soft delete a session (marks as deleted without removing from database).
    """
    user_id = user.get("id")
    log.info("User %s attempting to soft delete session %s", user_id, session_id)

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        deleted = session_service.delete_session_with_notifications(
            db=db, session_id=session_id, user_id=user_id
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        log.info("Session %s soft deleted successfully", session_id)

    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error deleting session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        log.error(
            "Error deleting session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session",
        ) from e


@router.patch("/sessions/{session_id}/project", response_model=SessionResponse)
async def move_session_to_project(
    session_id: str,
    request: MoveSessionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Move a session to a different project or remove from project.
    When moving to a project, artifacts from that project are immediately copied to the session.
    """
    user_id = user.get("id")
    log.info(
        "User %s attempting to move session %s to project %s",
        user_id,
        session_id,
        request.project_id,
    )

    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        updated_session = await session_service.move_session_to_project(
            db=db,
            session_id=session_id,
            user_id=user_id,
            new_project_id=request.project_id,
        )

        if not updated_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )

        log.info(
            "Session %s moved to project %s successfully",
            session_id,
            request.project_id or "None",
        )

        return SessionResponse(
            id=updated_session.id,
            user_id=updated_session.user_id,
            name=updated_session.name,
            agent_id=updated_session.agent_id,
            project_id=updated_session.project_id,
            created_time=updated_session.created_time,
            updated_time=updated_session.updated_time,
        )

    except HTTPException:
        raise
    except ValueError as e:
        log.warning("Validation error moving session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        log.error(
            "Error moving session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to move session",
        ) from e


@router.post("/sessions/{session_id}/generate-title", status_code=status.HTTP_202_ACCEPTED)
async def trigger_title_generation(
    session_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
    title_service: "TitleGenerationService" = Depends(get_title_generation_service),
):
    """
    Trigger asynchronous title generation for a chat session.
    Accepts the user message and agent response directly to avoid database timing issues.
    Returns immediately (202 Accepted) while title is generated in background.
    
    If the session already has a meaningful title (not "New Chat"), the request is
    silently accepted but no generation occurs. This handles browser refresh scenarios
    where the frontend's in-memory tracking is lost.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} triggering async title generation for session {session_id}")
    
    try:
        # Extract messages from request body
        user_message = request_body.get("userMessage", "")
        agent_response = request_body.get("agentResponse", "")
        force_regenerate = request_body.get("force", False)
        
        log.info(f"Received messages - User: {len(user_message)} chars, Agent: {len(agent_response)} chars, Force: {force_regenerate}")

        # Validate session exists and belongs to user
        session_domain = session_service.get_session_details(
            db=db, session_id=session_id, user_id=user_id
        )

        if not session_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_MSG
            )
        
        # Check if session already has a meaningful title (not "New Chat")
        # This handles browser refresh scenarios where frontend tracking is lost
        current_title = session_domain.name
        if not force_regenerate and current_title and current_title.strip() and current_title.strip() != "New Chat":
            log.debug(f"Session {session_id} already has title, skipping generation")
            return {"message": "Title already exists", "skipped": True}
        
        # Validate we have both messages
        if not user_message or not agent_response:
            log.warning(f"Missing messages for title generation - User: {bool(user_message)}, Agent: {bool(agent_response)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Both user message and agent response are required for title generation",
            )

        # Create callback to update session name when title is generated
        async def update_session_callback(generated_title: str):
            """Callback to update session name after title generation."""
            from ..dependencies import SessionLocal
            if SessionLocal is None:
                log.error("Cannot update session name: database not configured")
                return
            
            callback_db = SessionLocal()
            try:
                session_service.update_session_name(
                    db=callback_db,
                    session_id=session_id,
                    user_id=user_id,
                    name=generated_title,
                )
                callback_db.commit()
                log.info(f"Session name updated to '{generated_title}' for session {session_id}")
            except Exception as e:
                callback_db.rollback()
                log.error(f"Failed to update session name in callback: {e}")
            finally:
                callback_db.close()

        # Create background task using asyncio to ensure it runs
        loop = asyncio.get_event_loop()
        
        # Schedule the task in the event loop with callback
        loop.create_task(
            title_service._generate_and_update_title(
                session_id=session_id,
                user_message=user_message,
                agent_response=agent_response,
                user_id=user_id,
                update_callback=update_session_callback,
            )
        )

        log.info(f"Async title generation task scheduled for session {session_id}")

        return {"message": "Title generation started"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error triggering title generation for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger title generation",
        ) from e


# =============================================================================
# Context Usage & Manual Compaction Endpoints
# =============================================================================

# Fallback model used for token counting when neither the request nor the
# component config specifies a model.  Callers should prefer the component's
# configured model (component.model_config) over this constant.
DEFAULT_MODEL = "claude-sonnet-4-5"


class ContextUsageResponse(BaseModel):
    """Response model for session context window usage."""
    session_id: str = Field(alias="sessionId")
    current_context_tokens: int = Field(alias="currentContextTokens")
    prompt_tokens: int = Field(alias="promptTokens")
    completion_tokens: int = Field(alias="completionTokens")
    cached_tokens: int = Field(default=0, alias="cachedTokens")
    max_input_tokens: Optional[int] = Field(default=None, alias="maxInputTokens")
    usage_percentage: float = Field(alias="usagePercentage")
    model: str
    total_events: int = Field(alias="totalEvents")
    total_messages: int = Field(default=0, alias="totalMessages")
    total_tasks: int = Field(default=0, alias="totalTasks")
    has_compaction: bool = Field(alias="hasCompaction")

    model_config = {"populate_by_name": True}


class CompactSessionRequest(BaseModel):
    """Request model for manual session compaction."""
    model: Optional[str] = Field(None, description="LLM model name for token counting and summarization")
    compaction_percentage: float = Field(
        default=0.25,
        ge=0.1,
        le=0.9,
        description="Percentage of conversation to compact (0.1 - 0.9)",
    )


class CompactSessionResponse(BaseModel):
    """Response model for session compaction."""
    events_compacted: int = Field(alias="eventsCompacted")
    summary: str
    remaining_events: int = Field(alias="remainingEvents")
    remaining_tokens: int = Field(alias="remainingTokens")

    model_config = {"populate_by_name": True}


def _lookup_configured_context_limit(db: Session, model_name: str) -> Optional[int]:
    """Resolve the admin-configured context window for a model name.

    Matches against `model_configurations.model_name` first (the raw string the
    agent reports in `token_usage_details.by_model`), then `alias`. Returns the
    first non-null `max_input_tokens` — multiple rows can share a `model_name`
    (several aliases pointing at the same underlying model), so rows with a
    NULL limit must not shadow rows that have one configured.

    Only resolves in community-standalone deployments where the gateway DB
    and the platform DB are the same. In enterprise deployments the two DBs
    are separate, this table isn't reachable from the gateway session, and
    the client composes the limit from `/api/v1/platform/models` instead.
    """
    try:
        from ....services.platform.models.model_configuration import ModelConfiguration
    except ImportError:
        return None
    try:
        row = (
            db.query(ModelConfiguration.max_input_tokens)
            .filter(ModelConfiguration.model_name == model_name)
            .filter(ModelConfiguration.max_input_tokens.isnot(None))
            .first()
        )
        if row:
            return row[0]
        row = (
            db.query(ModelConfiguration.max_input_tokens)
            .filter(ModelConfiguration.alias == model_name)
            .filter(ModelConfiguration.max_input_tokens.isnot(None))
            .first()
        )
        if row:
            return row[0]
    except SQLAlchemyError as e:
        # Expected in enterprise (table lives in the platform DB) — logged at
        # WARN the first time per process so it is visible but not noisy.
        _warn_missing_model_configurations_once(e)
    return None


_model_configurations_warn_logged = False


def _warn_missing_model_configurations_once(exc: Exception) -> None:
    global _model_configurations_warn_logged
    if _model_configurations_warn_logged:
        log.debug("ModelConfiguration lookup unavailable: %s", exc)
        return
    _model_configurations_warn_logged = True
    log.warning(
        "model_configurations not reachable from the gateway DB — falling back. "
        "In enterprise this is expected; the UI composes the limit from the "
        "platform service. Underlying error: %s",
        exc,
    )


def _get_model_context_limit(
    model_name: str,
    db: Optional[Session] = None,
    stamped: Optional[int] = None,
) -> Optional[int]:
    """Get model context window limit.

    Resolution order:
      1. Admin-configured value in `model_configurations.max_input_tokens`
         (matched by `model_name` then `alias`), when a DB session is provided.
      2. Stamped value recorded by the agent in `token_usage_details.by_model`
         (sourced from the agent's shared_config.yaml `max_input_tokens`).
      3. LiteLLM's registry — try the full name, then strip any provider prefix
         (e.g. "openai/gpt-4o" → "gpt-4o").
      4. None — lets the frontend hide the indicator rather than show a wrong
         denominator.
    """
    if db is not None:
        configured = _lookup_configured_context_limit(db, model_name)
        if configured:
            return configured

    if stamped:
        return stamped

    from litellm import get_model_info

    def _try_lookup(name: str) -> Optional[int]:
        try:
            info = get_model_info(name)
            return info.get("max_input_tokens")
        except Exception:
            log.warning("Failed to lookup model info for '%s'", name, exc_info=True)
            return None

    result = _try_lookup(model_name)
    if result is not None:
        return result

    if "/" in model_name:
        bare_name = model_name.rsplit("/", 1)[-1]
        result = _try_lookup(bare_name)
        if result is not None:
            log.debug("Resolved max_input_tokens for %s via bare name %s", model_name, bare_name)
            return result

    log.debug("Could not determine max_input_tokens for model %s", model_name)
    return None


@router.get(
    "/sessions/{session_id}/context-usage",
    response_model=ContextUsageResponse,
    response_model_by_alias=True,
)
async def get_session_context_usage(
    session_id: str,
    model: Optional[str] = None,
    agent_name: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
    component=Depends(get_sac_component),
):
    """
    Get context window usage for a session.

    Returns the current token count, model context limit, and usage percentage.
    Uses the gateway's own tasks and chat_tasks tables as the source of truth
    for token data (LLM-reported totals from completed tasks).
    """
    user_id = user.get("id")

    try:
        # Validate session exists and belongs to user
        gateway_session = session_service.get_session_details(db, session_id, user_id)
        if not gateway_session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Resolve the model to use for context limit lookup:
        # 1. Explicit model from request query param
        # 2. Model configured on the gateway component
        # 3. Hardcoded fallback constant
        component_model = None
        if hasattr(component, "model_config") and isinstance(component.model_config, dict):
            component_model = component.model_config.get("model")
        resolved_default_model = component_model or DEFAULT_MODEL
        effective_model = model or resolved_default_model

        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0

        from ..repository.models import ChatTaskModel, TaskEventModel, TaskModel
        from sqlalchemy import desc

        # Exclude manual-compaction rows — they're system notifications (the
        # accordion), not user/agent exchanges, and would skew the task and
        # message counts shown in the chat panel.
        chat_task_count = (
            db.query(ChatTaskModel)
            .filter(
                ChatTaskModel.session_id == session_id,
                ChatTaskModel.user_id == user_id,
                ~ChatTaskModel.id.like("manual-compaction-%"),
            )
            .count()
        )
        total_tasks = chat_task_count
        total_messages = chat_task_count * 2

        # Peer subtasks (a2a_subtask_*) share this gateway session_id for
        # observability but represent a different agent's internal work. Their
        # token counts must not feed the current-agent context indicator, and
        # their later start_time would otherwise trick the agent-switch filter
        # below into treating the peer as the "current agent" whenever a peer
        # completion is the most-recent row in the session.
        completed_tasks = (
            db.query(TaskModel)
            .filter(
                TaskModel.session_id == session_id,
                TaskModel.user_id == user_id,
                TaskModel.total_input_tokens.isnot(None),
                ~TaskModel.id.like("a2a_subtask_%"),
            )
            .order_by(desc(TaskModel.start_time))
            .all()
        )

        # Filter tasks to the session's active agent — ADK sessions are keyed by
        # (app_name, user_id, session_id), so switching agents mid-session starts a
        # fresh context window. Tokens accumulated under the previous agent must not
        # leak into the new agent's indicator.
        if completed_tasks:
            task_ids = [t.id for t in completed_tasks]
            request_events = (
                db.query(TaskEventModel)
                .filter(
                    TaskEventModel.task_id.in_(task_ids),
                    TaskEventModel.direction == "request",
                )
                .order_by(TaskEventModel.task_id, TaskEventModel.created_time.asc())
                .all()
            )
            first_request_by_task: dict[str, TaskEventModel] = {}
            for ev in request_events:
                first_request_by_task.setdefault(ev.task_id, ev)

            def _task_agent(task_id: str) -> Optional[str]:
                ev = first_request_by_task.get(task_id)
                if not ev or not ev.payload:
                    return None
                try:
                    metadata = ev.payload.get("params", {}).get("message", {}).get("metadata", {})
                    return metadata.get("workflow_name") or metadata.get("agent_name")
                except AttributeError:
                    return None

            # Find the most recent real (non-compaction) task's agent — that's the
            # ADK session currently active for this gateway session.
            current_agent: Optional[str] = None
            for t in completed_tasks:
                if (t.id or "").startswith("compaction-cost-"):
                    continue
                current_agent = _task_agent(t.id)
                if current_agent:
                    break
            if current_agent is None:
                current_agent = gateway_session.agent_id

            if current_agent:
                # Compaction-cost rows are synthetic (no task events, no agent
                # metadata) and belong to the session, not a specific agent — keep
                # them so their token usage contributes to the cumulative totals.
                completed_tasks = [
                    t
                    for t in completed_tasks
                    if t.id.startswith("compaction-cost-") or _task_agent(t.id) == current_agent
                ]

        current_tokens = 0

        if completed_tasks:
            latest = completed_tasks[0]
            # promptTokens = cumulative input across ALL completed tasks
            prompt_tokens = sum(t.total_input_tokens or 0 for t in completed_tasks)
            # completionTokens = cumulative output across ALL completed tasks
            completion_tokens = sum(t.total_output_tokens or 0 for t in completed_tasks)

            # If the most recent row is a synthetic compaction-cost row, the
            # authoritative post-compaction context size is stored in its
            # ``token_usage_details.post_compaction_remaining_tokens``. Model
            # / cached-tokens metadata comes from the latest REAL task to
            # avoid reading stubbed fields on the synthetic row.
            real_latest = next(
                (t for t in completed_tasks if not (t.id or "").startswith("compaction-cost-")),
                latest,
            )
            if (latest.id or "").startswith("compaction-cost-"):
                details = latest.token_usage_details or {}
                current_tokens = int(details.get("post_compaction_remaining_tokens") or 0)
            else:
                # Context window occupancy = the last agent LLM call's prompt
                # tokens, not the cumulative sum across turns. total_input_tokens
                # inflates with every peer delegation (each follow-up turn adds
                # the full growing context to the sum) and doesn't reflect what
                # actually fills the window. Fall back to total_input_tokens
                # only for historical rows written before last_input_tokens was
                # tracked.
                details = latest.token_usage_details or {}
                last_input = details.get("last_input_tokens")
                current_tokens = int(last_input) if last_input else (latest.total_input_tokens or 0)

            cached_tokens = real_latest.total_cached_input_tokens or 0

            # Prefer the model actually used by the latest task over the gateway's
            # own model config — the agent may run a different model than the
            # gateway (and different agents in the same session may differ).
            # Query-param `model` still wins (explicit caller override).
            if not model:
                by_model = (real_latest.token_usage_details or {}).get("by_model") or {}
                valid_entries = [kv for kv in by_model.items() if isinstance(kv[1], dict)]
                if valid_entries:
                    dominant = max(valid_entries, key=lambda kv: kv[1].get("input_tokens", 0))
                    effective_model = dominant[0]

        stamped_limit: Optional[int] = None
        if completed_tasks:
            real_latest_for_limit = next(
                (t for t in completed_tasks if not (t.id or "").startswith("compaction-cost-")),
                completed_tasks[0],
            )
            by_model = (real_latest_for_limit.token_usage_details or {}).get("by_model") or {}
            entry = by_model.get(effective_model)
            if isinstance(entry, dict):
                raw = entry.get("max_input_tokens")
                try:
                    stamped_limit = int(raw) if raw else None
                except (TypeError, ValueError):
                    stamped_limit = None

        max_input_tokens = _get_model_context_limit(effective_model, db=db, stamped=stamped_limit)
        usage_pct = (
            min(100.0, round((current_tokens / max_input_tokens) * 100, 1))
            if max_input_tokens and current_tokens > 0
            else 0.0
        )

        return ContextUsageResponse(
            sessionId=session_id,
            currentContextTokens=current_tokens,
            promptTokens=prompt_tokens,
            completionTokens=completion_tokens,
            cachedTokens=cached_tokens,
            maxInputTokens=max_input_tokens,
            usagePercentage=usage_pct,
            model=effective_model,
            totalEvents=0,
            totalMessages=total_messages,
            totalTasks=total_tasks,
            hasCompaction=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error getting context usage for session %s: %s", session_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get context usage",
        )


async def _publish_and_await_compaction(
    component,
    session_id: str,
    user_id: str,
    app_name: str,
    compaction_percentage: float,
) -> dict:
    """Publish a session.compact_request and await the matching response.

    Returns the raw ``result`` dict on success. Raises ``HTTPException`` on
    publish failure or timeout. Always cleans up the correlation entry on
    failure paths.
    """
    correlation_id = uuid.uuid4().hex
    future = component.register_compaction_future(
        correlation_id, expected_agent_id=app_name
    )

    published = component.sam_events.publish_session_compact_request(
        session_id=session_id,
        user_id=user_id,
        agent_id=app_name,
        gateway_id=component.gateway_id,
        correlation_id=correlation_id,
        compaction_percentage=compaction_percentage,
    )
    if not published:
        component._compaction_futures.pop(correlation_id, None)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish compaction request.",
        )

    try:
        result = await asyncio.wait_for(future, timeout=60.0)
    except asyncio.TimeoutError:
        component._compaction_futures.pop(correlation_id, None)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Compaction request timed out. The agent may be unavailable.",
        )

    result["_correlation_id"] = correlation_id
    return result


def _map_compaction_error(session_id: str, result: dict) -> None:
    """Translate an unsuccessful compaction ``result`` into an HTTPException.

    The agent's raw ``error_message`` is logged for diagnostics but never
    returned to the client — we map it to a canned user-facing message to
    avoid leaking internal details.
    """
    error_msg = result.get("error_message", "Compaction failed")
    log.info("Compaction unsuccessful for session %s: %s", session_id, error_msg)
    lowered = error_msg.lower() if isinstance(error_msg, str) else ""
    if "not enough" in lowered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough conversation history to compress yet.",
        )
    if "not found" in lowered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no conversation history to compress.",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to compress session",
    )


def _persist_compaction_cost_task(
    db: Session,
    session_id: str,
    user_id: str,
    correlation_id: str,
    result: dict,
) -> None:
    """Persist a synthetic ``compaction-cost-*`` TaskModel row.

    Rolls the summarizer's own LLM token usage into the session's cumulative
    prompt/completion counters AND records the post-compaction context window
    size on the synthetic row (under ``token_usage_details``), never by
    overwriting the real task's historical ``total_input_tokens`` (which
    analytics/billing depend on). The reader derives ``currentContextTokens``
    from this synthetic row when it is the most recent row in the session.
    """
    from ..repository.models import TaskModel
    from sqlalchemy import desc

    comp_in = int(result.get("compaction_prompt_tokens") or 0)
    comp_out = int(result.get("compaction_completion_tokens") or 0)
    remaining_tokens = result.get("remaining_tokens")
    if not (comp_in or comp_out or remaining_tokens is not None):
        return

    latest_task = (
        db.query(TaskModel)
        .filter(
            TaskModel.session_id == session_id,
            TaskModel.user_id == user_id,
            TaskModel.total_input_tokens.isnot(None),
        )
        .order_by(desc(TaskModel.start_time))
        .first()
    )
    if latest_task is None:
        return

    try:
        details: dict = {}
        if remaining_tokens is not None:
            details["post_compaction_remaining_tokens"] = int(remaining_tokens)
        # Place the synthetic row just AFTER the latest real task so the
        # reader picks it up as "latest" for context-size purposes (sum()
        # over input tokens still includes compaction cost).
        synthetic_start = max(
            (latest_task.start_time or 0) + 1,
            int(time.time() * 1000),
        )
        synthetic_task = TaskModel(
            id=f"compaction-cost-{correlation_id}",
            user_id=user_id,
            session_id=session_id,
            start_time=synthetic_start,
            end_time=synthetic_start,
            status="completed",
            total_input_tokens=comp_in,
            total_output_tokens=comp_out,
            token_usage_details=details or None,
        )
        db.add(synthetic_task)
        db.commit()
    except Exception as synth_err:
        db.rollback()
        log.warning(
            "Failed to persist compaction token usage for session %s: %s",
            session_id,
            synth_err,
        )


def _persist_compaction_notification(
    session_service: SessionService,
    db: Session,
    session_id: str,
    user_id: str,
    correlation_id: str,
    summary: str,
) -> None:
    """Persist a compaction_notification chat task for session reload.

    Matches the auto-compaction path (which persists via the A2A task-event
    pipeline). Manual compaction runs outside any task context, so we
    synthesize a chat task directly here.
    """
    if not summary:
        return
    try:
        message_id = f"manual-compaction-{correlation_id}"
        bubble = {
            "id": message_id,
            "type": "agent",
            "text": "",
            "parts": [
                {
                    "kind": "data",
                    "data": {
                        "type": "compaction_notification",
                        "summary": summary,
                        "is_background": False,
                    },
                }
            ],
        }
        session_service.save_task(
            db=db,
            task_id=message_id,
            session_id=session_id,
            user_id=user_id,
            user_message=None,
            message_bubbles=json.dumps([bubble]),
        )
    except Exception as save_err:
        log.warning(
            "Failed to persist manual compaction notification for session %s: %s",
            session_id,
            save_err,
        )


@router.post(
    "/sessions/{session_id}/compact",
    response_model=CompactSessionResponse,
    response_model_by_alias=True,
)
async def compact_session(
    session_id: str,
    request: CompactSessionRequest = Body(default=CompactSessionRequest()),
    agent_name: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
    component=Depends(get_sac_component),
):
    """
    Manually compact a session's conversation history.

    Publishes a session.compact_request SAM event to the agent, which performs
    the actual compaction using its own services (FilteringSessionService,
    SessionCompactionState lock, LLM summarization). The gateway waits for
    a session.compact_response event with the results.
    """
    user_id = user.get("id")

    try:
        gateway_session = session_service.get_session_details(db, session_id, user_id)
        if not gateway_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        app_name = agent_name or gateway_session.agent_id
        if not app_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No agent associated with this session. Provide agent_name parameter.",
            )

        result = await _publish_and_await_compaction(
            component, session_id, user_id, app_name, request.compaction_percentage
        )
        correlation_id = result.pop("_correlation_id")

        if not result.get("success"):
            _map_compaction_error(session_id, result)

        _persist_compaction_cost_task(db, session_id, user_id, correlation_id, result)
        _persist_compaction_notification(
            session_service,
            db,
            session_id,
            user_id,
            correlation_id,
            result.get("summary") or "",
        )

        return CompactSessionResponse(
            eventsCompacted=result.get("events_compacted", 0),
            summary=result.get("summary", ""),
            remainingEvents=result.get("remaining_events", 0),
            remainingTokens=result.get("remaining_tokens", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error compacting session %s: %s", session_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compact session",
        )
