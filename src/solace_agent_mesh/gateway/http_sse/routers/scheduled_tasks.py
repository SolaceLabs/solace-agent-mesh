"""
REST API router for scheduled tasks management.
"""

import logging
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from ..dependencies import get_db
from ..repository.scheduled_task_repository import ScheduledTaskRepository
from ..shared.auth_utils import get_current_user
from ..shared.pagination import PaginationParams
from ..shared import now_epoch_ms
from .dto.scheduled_task_dto import (
    CreateScheduledTaskRequest,
    UpdateScheduledTaskRequest,
    ScheduledTaskResponse,
    ScheduledTaskListResponse,
    ExecutionResponse,
    ExecutionListResponse,
    SchedulerStatusResponse,
    TaskActionResponse,
)
from ..services.task_builder_assistant import TaskBuilderAssistant, TaskBuilderResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])

TASK_NOT_FOUND_MSG = "Scheduled task not found"
UNAUTHORIZED_MSG = "Not authorized to access this task"


def get_scheduler_service():
    """Dependency to get scheduler service from component."""
    from ..dependencies import get_sac_component
    
    component = get_sac_component()
    
    # Get scheduler service from component
    scheduler_service = getattr(component, 'scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not initialized. Enable scheduler_service in gateway configuration."
        )
    
    return scheduler_service


# DTOs for task builder chat
class TaskBuilderChatRequest(BaseModel):
    """Request for task builder chat interaction."""
    message: str
    conversation_history: List[Dict[str, str]] = []
    current_task: Dict[str, Any] = {}
    available_agents: List[str] = []


class TaskBuilderChatResponse(BaseModel):
    """Response from task builder chat."""
    message: str
    task_updates: Dict[str, Any] = {}
    confidence: float
    ready_to_save: bool


def get_task_builder_assistant(
    db: DBSession = Depends(get_db),
) -> TaskBuilderAssistant:
    """Dependency to get task builder assistant."""
    from ..dependencies import get_sac_component
    
    component = get_sac_component()
    
    # Get model config from component
    model_config = getattr(component, 'model_config', None)
    if not model_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model configuration not available"
        )
    
    return TaskBuilderAssistant(db=db, model_config=model_config)


@router.post("/builder/chat", response_model=TaskBuilderChatResponse)
async def task_builder_chat(
    request: TaskBuilderChatRequest,
    user: dict = Depends(get_current_user),
    assistant: TaskBuilderAssistant = Depends(get_task_builder_assistant),
):
    """
    AI-assisted task builder chat endpoint.
    
    Processes user messages and returns task configuration updates.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} interacting with task builder")
    
    try:
        response = await assistant.process_message(
            user_message=request.message,
            conversation_history=request.conversation_history,
            current_task=request.current_task,
            user_id=user_id,
            available_agents=request.available_agents if request.available_agents else None,
        )
        
        return TaskBuilderChatResponse(
            message=response.message,
            task_updates=response.task_updates,
            confidence=response.confidence,
            ready_to_save=response.ready_to_save,
        )
        
    except Exception as e:
        log.error(f"Error in task builder chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process task builder message"
        ) from e


@router.get("/builder/greeting", response_model=TaskBuilderChatResponse)
async def get_task_builder_greeting(
    assistant: TaskBuilderAssistant = Depends(get_task_builder_assistant),
):
    """Get initial greeting message for task builder."""
    try:
        response = assistant.get_initial_greeting()
        
        return TaskBuilderChatResponse(
            message=response.message,
            task_updates=response.task_updates,
            confidence=response.confidence,
            ready_to_save=response.ready_to_save,
        )
        
    except Exception as e:
        log.error(f"Error getting task builder greeting: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task builder greeting"
        ) from e


@router.post("/", response_model=ScheduledTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    request: CreateScheduledTaskRequest,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """
    Create a new scheduled task.
    
    The task will be automatically scheduled if enabled=True.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} creating scheduled task: {request.name}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Prepare task data
        task_data = {
            "id": str(uuid.uuid4()),
            "name": request.name,
            "description": request.description,
            "namespace": scheduler_service.namespace,
            "user_id": user_id if request.user_level else None,
            "created_by": user_id,
            "schedule_type": request.schedule_type,
            "schedule_expression": request.schedule_expression,
            "timezone": request.timezone,
            "target_agent_name": request.target_agent_name,
            "task_message": [part.dict() for part in request.task_message],
            "task_metadata": request.task_metadata,
            "enabled": request.enabled,
            "max_retries": request.max_retries,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
            "notification_config": request.notification_config.dict() if request.notification_config else None,
            "created_at": now_epoch_ms(),
            "updated_at": now_epoch_ms(),
        }
        
        # Create task in database
        task = repo.create_task(db, task_data)
        db.commit()
        
        # If enabled and this instance is leader, schedule it
        if task.enabled and await scheduler_service.is_leader():
            try:
                await scheduler_service._schedule_task(task)
            except Exception as e:
                log.error(f"Failed to schedule task {task.id}: {e}")
                # Task is created but not scheduled - leader will pick it up on next load
        
        log.info(f"Created scheduled task {task.id}")
        
        return ScheduledTaskResponse.from_orm(task)
        
    except Exception as e:
        db.rollback()
        log.error(f"Error creating scheduled task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scheduled task"
        ) from e


@router.get("/", response_model=ScheduledTaskListResponse)
async def list_scheduled_tasks(
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    enabled_only: bool = Query(default=False, alias="enabledOnly"),
    include_namespace_tasks: bool = Query(default=True, alias="includeNamespaceTasks"),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """
    List scheduled tasks for the current user.
    
    By default includes both user-specific and namespace-level tasks.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} listing scheduled tasks (page={page_number}, size={page_size})")
    
    try:
        repo = ScheduledTaskRepository()
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        
        tasks = repo.find_by_namespace(
            db,
            namespace=scheduler_service.namespace,
            user_id=user_id,
            include_namespace_tasks=include_namespace_tasks,
            enabled_only=enabled_only,
            pagination=pagination,
        )
        
        total = repo.count_by_namespace(
            db,
            namespace=scheduler_service.namespace,
            user_id=user_id,
            include_namespace_tasks=include_namespace_tasks,
            enabled_only=enabled_only,
        )
        
        task_responses = [ScheduledTaskResponse.from_orm(task) for task in tasks]
        
        return ScheduledTaskListResponse(
            tasks=task_responses,
            total=total,
            skip=pagination.offset,
            limit=page_size,
        )
        
    except Exception as e:
        log.error(f"Error listing scheduled tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled tasks"
        ) from e


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """Get details of a specific scheduled task."""
    user_id = user.get("id")
    log.info(f"User {user_id} fetching scheduled task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        # Check authorization
        if task.user_id and task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        return ScheduledTaskResponse.from_orm(task)
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching scheduled task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scheduled task"
        ) from e


@router.patch("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: str,
    request: UpdateScheduledTaskRequest,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """
    Update a scheduled task.
    
    If the schedule is changed, the task will be rescheduled automatically.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} updating scheduled task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Check task exists and user has access
        existing_task = repo.find_by_id(db, task_id, user_id=user_id)
        if not existing_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        if existing_task.user_id and existing_task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        # Prepare update data
        update_data = request.dict(exclude_none=True)
        
        # Convert message parts if provided
        if "task_message" in update_data:
            update_data["task_message"] = [part.dict() for part in request.task_message]
        
        # Convert notification config if provided
        if "notification_config" in update_data and request.notification_config:
            update_data["notification_config"] = request.notification_config.dict()
        
        # Update task
        updated_task = repo.update_task(db, task_id, update_data)
        db.commit()
        
        # If schedule changed and task is enabled, reschedule
        schedule_changed = any(k in update_data for k in ["schedule_type", "schedule_expression", "timezone"])
        if schedule_changed and updated_task.enabled and await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
                await scheduler_service._schedule_task(updated_task)
            except Exception as e:
                log.error(f"Failed to reschedule task {task_id}: {e}")
        
        log.info(f"Updated scheduled task {task_id}")
        
        return ScheduledTaskResponse.from_orm(updated_task)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error updating scheduled task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scheduled task"
        ) from e


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """
    Soft delete a scheduled task.
    
    The task will be unscheduled and marked as deleted.
    """
    user_id = user.get("id")
    log.info(f"User {user_id} deleting scheduled task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Check task exists and user has access
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        if task.user_id and task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        # Soft delete
        deleted = repo.soft_delete(db, task_id, user_id)
        db.commit()
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        # Unschedule if leader
        if await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
            except Exception as e:
                log.error(f"Failed to unschedule task {task_id}: {e}")
        
        log.info(f"Deleted scheduled task {task_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error deleting scheduled task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scheduled task"
        ) from e


@router.post("/{task_id}/enable", response_model=TaskActionResponse)
async def enable_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """Enable a scheduled task."""
    user_id = user.get("id")
    log.info(f"User {user_id} enabling scheduled task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Check access
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        if task.user_id and task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        # Enable task
        enabled_task = repo.enable_task(db, task_id)
        db.commit()
        
        # Schedule if leader
        if enabled_task and await scheduler_service.is_leader():
            try:
                await scheduler_service._schedule_task(enabled_task)
            except Exception as e:
                log.error(f"Failed to schedule task {task_id}: {e}")
        
        return TaskActionResponse(
            success=True,
            message="Task enabled successfully",
            task_id=task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error enabling scheduled task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable scheduled task"
        ) from e


@router.post("/{task_id}/disable", response_model=TaskActionResponse)
async def disable_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """Disable a scheduled task."""
    user_id = user.get("id")
    log.info(f"User {user_id} disabling scheduled task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Check access
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        if task.user_id and task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        # Disable task
        disabled_task = repo.disable_task(db, task_id)
        db.commit()
        
        # Unschedule if leader
        if disabled_task and await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
            except Exception as e:
                log.error(f"Failed to unschedule task {task_id}: {e}")
        
        return TaskActionResponse(
            success=True,
            message="Task disabled successfully",
            task_id=task_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"Error disabling scheduled task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable scheduled task"
        ) from e


@router.get("/{task_id}/executions", response_model=ExecutionListResponse)
async def get_task_executions(
    task_id: str,
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """Get execution history for a scheduled task."""
    user_id = user.get("id")
    log.info(f"User {user_id} fetching executions for task {task_id}")
    
    try:
        repo = ScheduledTaskRepository()
        
        # Check task exists and user has access
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=TASK_NOT_FOUND_MSG
            )
        
        if task.user_id and task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MSG
            )
        
        # Get executions
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        executions = repo.find_executions_by_task(db, task_id, pagination)
        total = repo.count_executions_by_task(db, task_id)
        
        execution_responses = [ExecutionResponse.from_orm(exec) for exec in executions]
        
        return ExecutionListResponse(
            executions=execution_responses,
            total=total,
            skip=pagination.offset,
            limit=page_size,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error fetching executions for task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch task executions"
        ) from e


@router.get("/executions/recent", response_model=ExecutionListResponse)
async def get_recent_executions(
    limit: int = Query(default=50, ge=1, le=100),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service = Depends(get_scheduler_service),
):
    """Get recent executions across all tasks."""
    user_id = user.get("id")
    log.info(f"User {user_id} fetching recent executions")
    
    try:
        repo = ScheduledTaskRepository()
        
        executions = repo.find_recent_executions(
            db,
            namespace=scheduler_service.namespace,
            user_id=user_id,
            limit=limit,
        )
        
        execution_responses = [ExecutionResponse.from_orm(exec) for exec in executions]
        
        return ExecutionListResponse(
            executions=execution_responses,
            total=len(execution_responses),
            skip=0,
            limit=limit,
        )
        
    except Exception as e:
        log.error(f"Error fetching recent executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recent executions"
        ) from e


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    scheduler_service = Depends(get_scheduler_service),
):
    """Get current scheduler status."""
    try:
        # Build status dict safely
        status_info = {
            "instance_id": getattr(scheduler_service, 'instance_id', 'unknown'),
            "namespace": getattr(scheduler_service, 'namespace', 'unknown'),
            "is_leader": False,  # Default to false for now
            "active_tasks_count": len(getattr(scheduler_service, 'active_tasks', {})),
            "running_executions_count": len(getattr(scheduler_service, 'running_executions', {})),
            "scheduler_running": getattr(getattr(scheduler_service, 'scheduler', None), 'running', False),
            "leader_info": None,
        }
        return SchedulerStatusResponse(**status_info)
        
    except Exception as e:
        log.error(f"Error fetching scheduler status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch scheduler status: {str(e)}"
        ) from e