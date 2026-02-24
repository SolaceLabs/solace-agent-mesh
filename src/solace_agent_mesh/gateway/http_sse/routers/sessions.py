import asyncio
import json
import logging
import re
from typing import Optional, TYPE_CHECKING
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ....common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_in_string,
)
from ....common.utils.embeds.types import ResolutionMode
from ....common.utils.templates import resolve_template_blocks_in_string
from ..dependencies import get_session_business_service, get_db, get_title_generation_service, get_shared_artifact_service, get_sac_component
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


@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def get_all_sessions(
    project_id: Optional[str] = Query(default=None, alias="project_id"),
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    user_id = user.get("id")
    log_msg = f"User '{user_id}' is listing sessions with pagination (page={page_number}, size={page_size})"
    if project_id:
        log_msg += f" filtered by project_id={project_id}"
    log.info(log_msg)

    try:
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        paginated_response = session_service.get_user_sessions(db, user_id, pagination, project_id=project_id)

        session_responses = []
        for session_domain in paginated_response.data:
            session_response = SessionResponse(
                id=session_domain.id,
                user_id=session_domain.user_id,
                name=session_domain.name,
                agent_id=session_domain.agent_id,
                project_id=session_domain.project_id,
                project_name=session_domain.project_name,
                has_running_background_task=session_domain.has_running_background_task,
                created_time=session_domain.created_time,
                updated_time=session_domain.updated_time,
            )
            session_responses.append(session_response)

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
                has_running_background_task=session_domain.has_running_background_task,
                created_time=session_domain.created_time,
                updated_time=session_domain.updated_time,
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
            
            # Commit the transaction immediately after DB operations
            db.commit()
            
            log.info(
                "Task %s %s successfully for session %s",
                request.task_id,
                "updated" if is_update else "created",
                session_id,
            )
        except Exception as db_error:
            db.rollback()
            raise db_error
        finally:
            db.close()

        # ============================================================
        # PHASE 3: Post-commit cleanup (non-critical, no DB needed)
        # ============================================================
        
        # Clear SSE event buffer for this task (implicit cleanup)
        # This is done AFTER the DB transaction is committed
        try:
            from ..dependencies import get_sac_component
            cleanup_component = get_sac_component()
            log.debug(
                "[BufferCleanup] Task %s: Starting cleanup. component=%s, sse_manager=%s",
                request.task_id,
                cleanup_component is not None,
                cleanup_component.sse_manager is not None if cleanup_component else False,
            )
            if cleanup_component and cleanup_component.sse_manager:
                persistent_buffer = cleanup_component.sse_manager.get_persistent_buffer()
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



