"""
REST API router for scheduled tasks management.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from ..dependencies import get_db, get_config_resolver, get_user_config, get_agent_registry
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
    SchedulePreviewRequest,
    SchedulePreviewResponse,
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
    scheduler_service = getattr(component, 'scheduler_service', None)
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not initialized. Enable scheduler_service in gateway configuration."
        )
    return scheduler_service


# --- Task Builder Chat ---

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
    """AI-assisted task builder chat endpoint."""
    user_id = user.get("id")
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
        log.error("Error in task builder chat: %s", e, exc_info=True)
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
        log.error("Error getting task builder greeting: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task builder greeting"
        ) from e


# --- Preview Endpoint (Phase 3.2) ---

@router.post("/preview", response_model=SchedulePreviewResponse)
async def preview_schedule(
    request: SchedulePreviewRequest,
    user: dict = Depends(get_current_user),
):
    """Preview next execution times for a schedule expression. Stateless — no DB needed."""
    import pytz

    try:
        tz = pytz.timezone(request.timezone)
        now = datetime.now(tz)
        next_times = []

        if request.schedule_type == "cron":
            if not croniter.is_valid(request.schedule_expression):
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {request.schedule_expression}")
            cron = croniter(request.schedule_expression, now)
            for _ in range(request.count):
                next_time = cron.get_next(datetime)
                next_times.append(next_time.isoformat())

        elif request.schedule_type == "interval":
            expr = request.schedule_expression.strip().lower()
            if expr.endswith("s"):
                seconds = int(expr[:-1])
            elif expr.endswith("m"):
                seconds = int(expr[:-1]) * 60
            elif expr.endswith("h"):
                seconds = int(expr[:-1]) * 3600
            elif expr.endswith("d"):
                seconds = int(expr[:-1]) * 86400
            else:
                seconds = int(expr)

            current = now
            for _ in range(request.count):
                from datetime import timedelta
                current = current + timedelta(seconds=seconds)
                next_times.append(current.isoformat())
        else:
            raise HTTPException(status_code=400, detail=f"Preview not supported for schedule_type: {request.schedule_type}")

        return SchedulePreviewResponse(
            next_times=next_times,
            schedule_type=request.schedule_type,
            schedule_expression=request.schedule_expression,
            timezone=request.timezone,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error previewing schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to preview schedule") from e


# --- CRUD Endpoints ---

@router.post("/", response_model=ScheduledTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    request: CreateScheduledTaskRequest,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    agent_registry=Depends(get_agent_registry),
):
    """Create a new scheduled task."""
    user_id = user.get("id")
    log.info("User %s creating scheduled task: %s", user_id, request.name)

    # Phase 2.2: Block namespace-level tasks for non-admin users
    if not request.user_level and "admin" not in user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create namespace-level tasks"
        )

    # Phase 2.1: RBAC - Validate target agent access
    if request.target_agent_name:
        agent = agent_registry.get_agent(request.target_agent_name)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target agent '{request.target_agent_name}' not found in registry"
            )
        operation_spec = {
            "operation_type": "agent_access",
            "target_agent": request.target_agent_name,
        }
        validation_result = config_resolver.validate_operation_config(
            user_config, operation_spec, {"source": "scheduled_tasks_endpoint"}
        )
        if not validation_result.get("valid", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to target agent '{request.target_agent_name}'"
            )

    try:
        repo = ScheduledTaskRepository()

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
            "target_type": request.target_type,
            "task_message": [part.dict() for part in request.task_message],
            "task_metadata": request.task_metadata,
            "enabled": request.enabled,
            "max_retries": request.max_retries,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
            "notification_config": request.notification_config.dict() if request.notification_config else None,
            "source": "ui",
            "created_at": now_epoch_ms(),
            "updated_at": now_epoch_ms(),
        }

        task = repo.create_task(db, task_data)
        db.commit()

        if task.enabled and await scheduler_service.is_leader():
            try:
                await scheduler_service._schedule_task(task)
            except Exception as e:
                log.error("Failed to schedule task %s: %s", task.id, e)

        return ScheduledTaskResponse.from_orm(task)

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        db.rollback()
        log.error("Error creating scheduled task: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create scheduled task") from e


@router.get("/", response_model=ScheduledTaskListResponse)
async def list_scheduled_tasks(
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    enabled_only: bool = Query(default=False, alias="enabledOnly"),
    include_namespace_tasks: bool = Query(default=True, alias="includeNamespaceTasks"),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """List scheduled tasks for the current user."""
    user_id = user.get("id")
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
        log.error("Error listing scheduled tasks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list scheduled tasks") from e


@router.get("/executions/recent", response_model=ExecutionListResponse)
async def get_recent_executions(
    limit: int = Query(default=50, ge=1, le=100),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Get recent executions across all tasks."""
    user_id = user.get("id")
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
        log.error("Error fetching recent executions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent executions") from e


# Phase 3.7: Reverse lookup by A2A task ID
@router.get("/executions/by-a2a-task/{a2a_task_id}", response_model=ExecutionResponse)
async def get_execution_by_a2a_task_id(
    a2a_task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Look up a scheduled task execution by its A2A task ID."""
    try:
        repo = ScheduledTaskRepository()
        execution = repo.find_execution_by_a2a_task_id(db, a2a_task_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found for this A2A task ID")

        # Verify ownership: look up the parent task and check created_by matches the requesting user.
        # Return 404 (not 403) to avoid confirming existence to unauthorized users.
        task = repo.find_by_id(db, execution.scheduled_task_id)
        if not task or task.created_by != user.get("id"):
            raise HTTPException(status_code=404, detail="Execution not found for this A2A task ID")

        return ExecutionResponse.from_orm(execution)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching execution by A2A task ID: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch execution") from e


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Get current scheduler status. Requires admin role."""
    if "admin" not in user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view scheduler status"
        )
    try:
        status_info = {
            "instance_id": getattr(scheduler_service, 'instance_id', 'unknown'),
            "namespace": getattr(scheduler_service, 'namespace', 'unknown'),
            "is_leader": False,
            "active_tasks_count": len(getattr(scheduler_service, 'active_tasks', {})),
            "running_executions_count": len(getattr(scheduler_service, 'running_executions', {})),
            "scheduler_running": getattr(getattr(scheduler_service, 'scheduler', None), 'running', False),
            "leader_info": None,
        }
        return SchedulerStatusResponse(**status_info)
    except Exception as e:
        log.error("Error fetching scheduler status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch scheduler status") from e


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Get details of a specific scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)

        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        return ScheduledTaskResponse.from_orm(task)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch scheduled task") from e


@router.patch("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: str,
    request: UpdateScheduledTaskRequest,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    agent_registry=Depends(get_agent_registry),
):
    """Update a scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()

        existing_task = repo.find_by_id(db, task_id, user_id=user_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        if existing_task.user_id and existing_task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
        elif not existing_task.user_id and "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")

        # Phase 3.5: Config-sourced tasks are read-only except enable/disable
        if existing_task.source == "config":
            allowed_fields = {"enabled"}
            update_fields = {k for k, v in request.dict(exclude_none=True).items()}
            if not update_fields.issubset(allowed_fields):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Config-sourced tasks can only be enabled/disabled via the UI"
                )

        # Phase 2.1: RBAC - Validate target agent access if being changed
        if request.target_agent_name is not None:
            agent = agent_registry.get_agent(request.target_agent_name)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target agent '{request.target_agent_name}' not found in registry"
                )
            operation_spec = {
                "operation_type": "agent_access",
                "target_agent": request.target_agent_name,
            }
            validation_result = config_resolver.validate_operation_config(
                user_config, operation_spec, {"source": "scheduled_tasks_endpoint"}
            )
            if not validation_result.get("valid", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to target agent '{request.target_agent_name}'"
                )

        update_data = request.dict(exclude_none=True)

        if "task_message" in update_data:
            update_data["task_message"] = [part.dict() for part in request.task_message]

        if "notification_config" in update_data and request.notification_config:
            update_data["notification_config"] = request.notification_config.dict()

        updated_task = repo.update_task(db, task_id, update_data)
        db.commit()

        schedule_changed = any(k in update_data for k in ["schedule_type", "schedule_expression", "timezone"])
        if schedule_changed and updated_task.enabled and await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
                await scheduler_service._schedule_task(updated_task)
            except Exception as e:
                log.error("Failed to reschedule task %s: %s", task_id, e)

        return ScheduledTaskResponse.from_orm(updated_task)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error updating scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update scheduled task") from e


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Soft delete a scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()

        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
        elif not task.user_id and "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")

        deleted = repo.soft_delete(db, task_id, user_id)
        db.commit()

        if not deleted:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        if await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
            except Exception as e:
                log.error("Failed to unschedule task %s: %s", task_id, e)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error deleting scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete scheduled task") from e


@router.post("/{task_id}/enable", response_model=TaskActionResponse)
async def enable_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Enable a scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
        elif not task.user_id and "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")

        enabled_task = repo.enable_task(db, task_id)
        db.commit()

        if enabled_task and await scheduler_service.is_leader():
            try:
                await scheduler_service._schedule_task(enabled_task)
            except Exception as e:
                log.error("Failed to schedule task %s: %s", task_id, e)

        return TaskActionResponse(success=True, message="Task enabled successfully", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error enabling scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enable scheduled task") from e


@router.post("/{task_id}/disable", response_model=TaskActionResponse)
async def disable_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Disable a scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
        elif not task.user_id and "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")

        disabled_task = repo.disable_task(db, task_id)
        db.commit()

        if disabled_task and await scheduler_service.is_leader():
            try:
                await scheduler_service._unschedule_task(task_id)
            except Exception as e:
                log.error("Failed to unschedule task %s: %s", task_id, e)

        return TaskActionResponse(success=True, message="Task disabled successfully", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error disabling scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to disable scheduled task") from e


# Phase 3.1: Reactivate endpoint
@router.post("/{task_id}/reactivate", response_model=TaskActionResponse)
async def reactivate_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Reactivate a task that entered error state after consecutive failures."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
        elif not task.user_id and "admin" not in user.get("roles", []):
            raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")

        if task.status != "error":
            raise HTTPException(status_code=400, detail="Task is not in error state")

        update_data = {
            "status": "active",
            "consecutive_failure_count": 0,
        }
        repo.update_task(db, task_id, update_data)
        db.commit()

        # Re-schedule if enabled and leader
        if task.enabled and await scheduler_service.is_leader():
            try:
                refreshed = repo.find_by_id(db, task_id)
                if refreshed:
                    await scheduler_service._schedule_task(refreshed)
            except Exception as e:
                log.error("Failed to reschedule reactivated task %s: %s", task_id, e)

        return TaskActionResponse(success=True, message="Task reactivated successfully", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error reactivating task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reactivate task") from e


@router.get("/{task_id}/executions", response_model=ExecutionListResponse)
async def get_task_executions(
    task_id: str,
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    scheduler_service=Depends(get_scheduler_service),
):
    """Get execution history for a scheduled task."""
    user_id = user.get("id")
    try:
        repo = ScheduledTaskRepository()
        task = repo.find_by_id(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)

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
        log.error("Error fetching executions for task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch task executions") from e
