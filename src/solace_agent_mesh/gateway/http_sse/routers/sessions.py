import logging
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..dependencies import get_session_business_service, get_db
from ..services.session_service import SessionService
from ..shared.auth_utils import get_current_user
from ..shared.pagination import DataResponse, PaginatedResponse, PaginationParams
from ..shared.response_utils import create_data_response
from .dto.requests.session_requests import (
    GetSessionRequest,
    UpdateSessionRequest,
    MoveSessionRequest,
    SearchSessionsRequest,
)
from .dto.requests.task_requests import SaveTaskRequest
from .dto.responses.session_responses import SessionResponse
from .dto.responses.task_responses import TaskResponse, TaskListResponse

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
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
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

        # Check if task already exists to determine status code
        from ..repository.chat_task_repository import ChatTaskRepository

        task_repo = ChatTaskRepository()
        existing_task = task_repo.find_by_id(db, request.task_id, user_id)
        is_update = existing_task is not None

        # Save the task - pass strings directly
        saved_task = session_service.save_task(
            db=db,
            task_id=request.task_id,
            session_id=session_id,
            user_id=user_id,
            user_message=request.user_message,
            message_bubbles=request.message_bubbles,  # Already a string
            task_metadata=request.task_metadata,  # Already a string
        )

        log.info(
            "Task %s %s successfully for session %s",
            request.task_id,
            "updated" if is_update else "created",
            session_id,
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

# Compression endpoint
from pydantic import BaseModel, Field


class CompressAndBranchRequest(BaseModel):
    """Request model for compressing and branching a session."""
    agent_id: Optional[str] = Field(None, description="Agent ID for the new session", alias="agentId")
    name: Optional[str] = Field(None, max_length=255, description="Custom name for the new session")
    llm_provider: Optional[str] = Field(None, description="LLM provider for compression (e.g., 'openai', 'anthropic', 'gemini')", alias="llmProvider")
    llm_model: Optional[str] = Field(None, description="LLM model for compression (e.g., 'gpt-4o-mini', 'claude-3-5-sonnet-20241022')", alias="llmModel")
    
    class Config:
        populate_by_name = True


class CompressAndBranchResponse(BaseModel):
    """Response model for a compressed and branched session."""
    new_session_id: str = Field(alias="newSessionId")
    parent_session_id: str = Field(alias="parentSessionId")
    summary_task_id: str = Field(alias="summaryTaskId")
    compressed_message_count: int = Field(alias="compressedMessageCount")
    session_name: str = Field(alias="sessionName")
    created_time: int = Field(alias="createdTime")
    
    class Config:
        populate_by_name = True


@router.post("/sessions/{session_id}/compress-and-branch", response_model=CompressAndBranchResponse)
async def compress_and_branch_session(
    session_id: str,
    request: CompressAndBranchRequest = Body(default=CompressAndBranchRequest()),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_business_service),
):
    """
    Compress a session's conversation history and create a new session with the summary.
    
    This implements the "Compress-and-Branch" pattern where:
    - The conversation history is compressed into an LLM-generated summary
    - A new session is created as a child of the current session
    - The summary is added as the first task in the new session
    - The original session remains unchanged for reference
    
    This is useful for:
    - Long conversations that are approaching token limits
    - Starting a new phase of work while preserving context
    - Cleaning up after exploratory conversations
    """
    user_id = user.get("id")
    log.info(
        "User %s attempting to compress and branch session %s",
        user_id,
        session_id,
    )
    
    try:
        if (
            not session_id
            or session_id.strip() == ""
            or session_id in ["null", "undefined"]
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source session not found."
            )
        
        # Compress and branch the session
        new_session, summary_task, compressed_count = await session_service.compress_and_branch_session(
            db=db,
            source_session_id=session_id,
            user_id=user_id,
            agent_id=request.agent_id,
            branch_name=request.name,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
        )
        
        log.info(
            "Successfully compressed and branched session %s to %s (%d messages compressed)",
            session_id,
            new_session.id,
            compressed_count,
        )
        
        return CompressAndBranchResponse(
            newSessionId=new_session.id,
            parentSessionId=session_id,
            summaryTaskId=summary_task["id"],
            compressedMessageCount=compressed_count,
            sessionName=new_session.name or "",
            createdTime=new_session.created_time,
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        log.warning(
            "Validation error compressing and branching session %s: %s",
            session_id,
            e
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        log.error(
            "Error compressing and branching session %s for user %s: %s",
            session_id,
            user_id,
            e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compress and branch session",
        ) from e

