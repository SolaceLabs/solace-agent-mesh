"""
REST API router for scheduled tasks management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel, Field

from ..dependencies import get_db, get_config_resolver, get_user_config, get_agent_registry
from ..shared.auth_utils import get_current_user
from ..shared.pagination import PaginationParams
from ..shared import parse_interval_to_seconds
from ..services.scheduled_task_service import ScheduledTaskService
from .dto.scheduled_task_dto import (
    CreateScheduledTaskRequest,
    UpdateScheduledTaskRequest,
    ScheduledTaskResponse,
    ScheduledTaskListResponse,
    ExecutionResponse,
    ExecutionListResponse,
    LastExecutionSummary,
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


def _check_task_ownership(task, user_id: str, user: dict) -> None:
    """Verify the requesting user owns the task or is an admin for namespace tasks."""
    if task.user_id and task.user_id != user_id:
        raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)
    elif not task.user_id and "admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Only administrators can modify namespace-level tasks")


def _row_to_summary(row) -> LastExecutionSummary:
    """Convert a ScheduledTaskExecutionModel row into a LastExecutionSummary DTO."""
    duration_ms = None
    if row.started_at and row.completed_at:
        duration_ms = row.completed_at - row.started_at
    status_value = row.status.value if hasattr(row.status, "value") else str(row.status)
    trigger = getattr(row, "trigger_type", None)
    trigger_value = trigger.value if hasattr(trigger, "value") else (trigger or "scheduled")
    return LastExecutionSummary(
        id=row.id,
        status=status_value,
        scheduled_for=row.scheduled_for,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=duration_ms,
        error_message=row.error_message,
        trigger_type=trigger_value,
    )


_TERMINAL_EXECUTION_STATUSES_CACHE = None


def _terminal_execution_statuses():
    """Lazy-loaded terminal status list. Import-deferred to avoid a circular
    dependency between the router module and the repository models."""
    global _TERMINAL_EXECUTION_STATUSES_CACHE
    if _TERMINAL_EXECUTION_STATUSES_CACHE is None:
        from ..repository.models import ExecutionStatus

        _TERMINAL_EXECUTION_STATUSES_CACHE = [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.SKIPPED,
        ]
    return _TERMINAL_EXECUTION_STATUSES_CACHE


def _fetch_last_and_completed_executions(
    db: DBSession, task_ids: list[str]
) -> tuple[dict[str, LastExecutionSummary], dict[str, LastExecutionSummary]]:
    """Fetch, in a single round-trip, two maps keyed by task_id:

    * the most recent execution per task regardless of status (drives the
      list card's running/active pill); and
    * the most recent *terminal* execution per task (drives the "Succeeded N
      min ago" line, which must stay visible while a new run is in flight).

    Previously two separate ``SELECT``s did this; the combined version uses a
    single aggregate subquery with a CASE-filtered MAX so we can derive both
    in one query and split the maps in Python.
    """
    if not task_ids:
        return {}, {}

    from ..repository.models import ScheduledTaskExecutionModel
    from sqlalchemy import case, func, or_

    terminal = _terminal_execution_statuses()

    # Per-task aggregate: max scheduled_for overall + max scheduled_for
    # restricted to terminal statuses. NULL terminal-max means the task has
    # only in-flight executions, which we handle below.
    agg = (
        db.query(
            ScheduledTaskExecutionModel.scheduled_task_id.label("tid"),
            func.max(ScheduledTaskExecutionModel.scheduled_for).label("max_any"),
            func.max(
                case(
                    (
                        ScheduledTaskExecutionModel.status.in_(terminal),
                        ScheduledTaskExecutionModel.scheduled_for,
                    ),
                    else_=None,
                )
            ).label("max_terminal"),
        )
        .filter(ScheduledTaskExecutionModel.scheduled_task_id.in_(task_ids))
        .group_by(ScheduledTaskExecutionModel.scheduled_task_id)
        .subquery()
    )

    # Fetch every execution row whose scheduled_for matches *either* max for
    # its task. Deterministic ordering (started_at DESC nullslast, id DESC)
    # guarantees first-wins when multiple rows share the same scheduled_for.
    query = (
        db.query(ScheduledTaskExecutionModel, agg.c.max_any, agg.c.max_terminal)
        .join(agg, ScheduledTaskExecutionModel.scheduled_task_id == agg.c.tid)
        .filter(
            or_(
                ScheduledTaskExecutionModel.scheduled_for == agg.c.max_any,
                ScheduledTaskExecutionModel.scheduled_for == agg.c.max_terminal,
            )
        )
        .order_by(
            ScheduledTaskExecutionModel.started_at.desc().nullslast(),
            ScheduledTaskExecutionModel.id.desc(),
        )
    )

    last_by_task: dict[str, LastExecutionSummary] = {}
    last_completed_by_task: dict[str, LastExecutionSummary] = {}
    terminal_set = set(terminal)
    for row, max_any, max_terminal in query.all():
        tid = row.scheduled_task_id
        if row.scheduled_for == max_any and tid not in last_by_task:
            last_by_task[tid] = _row_to_summary(row)
        if (
            max_terminal is not None
            and row.scheduled_for == max_terminal
            and row.status in terminal_set
            and tid not in last_completed_by_task
        ):
            last_completed_by_task[tid] = _row_to_summary(row)

    return last_by_task, last_completed_by_task




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


def get_task_service(
    scheduler_service=Depends(get_scheduler_service),
) -> ScheduledTaskService:
    """Dependency to get the scheduled task CRUD service."""
    return ScheduledTaskService(scheduler_service=scheduler_service)


def _validate_scheduling_permission(user_config: dict, config_resolver) -> None:
    """Check that the user has scheduling permission. Raises 403 if not."""
    operation_spec = {"operation_type": "scheduling"}
    validation_result = config_resolver.validate_operation_config(
        user_config, operation_spec, {"source": "scheduled_tasks_endpoint"}
    )
    if not validation_result.get("valid", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to use the task scheduler",
        )


# --- Task Builder Chat ---

class AgentRef(BaseModel):
    """A reference to an available agent passed in the chat context.

    The assistant uses name + optional display_name + description to decide
    which agents to suggest; nothing else is read. `extra="ignore"` keeps the
    payload tolerant of unrelated keys the frontend may send.
    """
    name: str = Field(..., max_length=256)
    display_name: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=2000)

    model_config = {"extra": "ignore"}


class TaskBuilderChatRequest(BaseModel):
    """Request for task builder chat interaction."""
    message: str = Field(..., max_length=5000)
    conversation_history: List[Dict[str, str]] = Field(default=[], max_length=50)
    current_task: Dict[str, Any] = {}
    # Each entry may be a bare agent name (legacy callers) or a full AgentRef.
    # The assistant tolerates both via its own input sanitization.
    available_agents: List[Union[str, AgentRef]] = Field(default_factory=list, max_length=200)


class TaskBuilderChatResponse(BaseModel):
    """Response from task builder chat."""
    message: str
    task_updates: Dict[str, Any] = {}
    confidence: float
    ready_to_save: bool
    inline_component: Optional[Dict[str, Any]] = None


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
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    assistant: TaskBuilderAssistant = Depends(get_task_builder_assistant),
):
    """AI-assisted task builder chat endpoint."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        # Normalize AgentRef instances into the dict-or-str shape the assistant
        # already handles — keeps the typing strict at the router boundary
        # without forcing the assistant to know about Pydantic models.
        normalized_agents = [
            agent if isinstance(agent, str) else agent.model_dump(exclude_none=True)
            for agent in request.available_agents
        ] or None

        response = await assistant.process_message(
            user_message=request.message,
            conversation_history=request.conversation_history,
            current_task=request.current_task,
            user_id=user_id,
            available_agents=normalized_agents,
        )
        return TaskBuilderChatResponse(
            message=response.message,
            task_updates=response.task_updates,
            confidence=response.confidence,
            ready_to_save=response.ready_to_save,
            inline_component=response.inline_component.model_dump() if response.inline_component else None,
        )
    except Exception as e:
        log.error("Error in task builder chat: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process task builder message"
        ) from e


class ValidateConflictRequest(BaseModel):
    """Request to check whether task instructions conflict with the configured schedule."""
    instructions: str = Field(..., max_length=5000)
    schedule_type: str = Field(..., max_length=50)
    schedule_expression: str = Field(..., max_length=200)
    timezone: str = Field("UTC", max_length=100)
    target_agent: Optional[str] = Field(None, max_length=128)


class ValidateConflictResponse(BaseModel):
    """Outcome of the conflict check. `affected_fields` is a subset of {instructions, schedule}."""
    conflict: bool
    reason: Optional[str] = None
    affected_fields: List[str] = Field(default_factory=list)


@router.post("/builder/validate-conflict", response_model=ValidateConflictResponse)
async def validate_task_conflict(
    request: ValidateConflictRequest,
    user: dict = Depends(get_current_user),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    agent_registry=Depends(get_agent_registry),
    assistant: TaskBuilderAssistant = Depends(get_task_builder_assistant),
):
    """Check if task instructions semantically conflict with the schedule (LLM-backed).
    On any error, returns conflict=False so a flaky LLM doesn't block saves."""
    _validate_scheduling_permission(user_config, config_resolver)
    try:
        # Pass the current agent registry snapshot so the assistant can drop
        # target_agent values the caller doesn't actually have access to.
        try:
            available_agent_names = list(agent_registry.get_agent_names())
        except Exception:
            log.debug("Could not enumerate agent registry for conflict validation", exc_info=True)
            available_agent_names = None

        result = await assistant.validate_conflict(
            instructions=request.instructions,
            schedule_type=request.schedule_type,
            schedule_expression=request.schedule_expression,
            timezone=request.timezone,
            target_agent=request.target_agent,
            available_agent_names=available_agent_names,
        )
        return ValidateConflictResponse(
            conflict=result.conflict,
            reason=result.reason,
            affected_fields=result.affected_fields,
        )
    except Exception:
        # The assistant already logs at its own except handler; avoid a
        # duplicate log line at the router layer. Fail open — better to let the
        # user save than block them on a flaky LLM.
        return ValidateConflictResponse(conflict=False)


@router.get("/builder/greeting", response_model=TaskBuilderChatResponse)
async def get_task_builder_greeting(
    user: dict = Depends(get_current_user),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    assistant: TaskBuilderAssistant = Depends(get_task_builder_assistant),
):
    """Get initial greeting message for task builder."""
    _validate_scheduling_permission(user_config, config_resolver)
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


# --- Preview Endpoint ---

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
            seconds = parse_interval_to_seconds(request.schedule_expression)
            current = now
            for _ in range(request.count):
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
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    agent_registry=Depends(get_agent_registry),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Create a new scheduled task."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    log.info("User %s creating scheduled task: %s", user_id, request.name)

    if not request.user_level and "admin" not in user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create namespace-level tasks"
        )

    # RBAC - Validate target agent access
    target_agent = request.target_agent_name or "OrchestratorAgent"
    agent = agent_registry.get_agent(target_agent)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent '{target_agent}' not found in registry"
        )
    operation_spec = {"operation_type": "agent_access", "target_agent": target_agent}
    validation_result = config_resolver.validate_operation_config(
        user_config, operation_spec, {"source": "scheduled_tasks_endpoint"}
    )
    if not validation_result.get("valid", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to target agent '{target_agent}'"
        )

    try:
        request_data = {
            "name": request.name,
            "description": request.description,
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
        }

        task = task_service.create_task(
            db, request_data,
            namespace=task_service.namespace,
            user_id=user_id,
            user_level=request.user_level,
        )

        if task.enabled:
            try:
                # Interval schedules without a specific start time fire their
                # series from "now" on creation, so users get immediate feedback
                # instead of waiting a full interval for the first run. Cron and
                # one-time schedules keep their declared timing.
                fire_now = task.schedule_type == "interval"
                await task_service.schedule_task(task, fire_immediately=fire_now)
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
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """List scheduled tasks for the current user."""
    user_id = user.get("id")
    try:
        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        tasks, total = task_service.list_tasks(
            db,
            namespace=task_service.namespace,
            user_id=user_id,
            include_namespace_tasks=include_namespace_tasks,
            enabled_only=enabled_only,
            pagination=pagination,
        )

        task_ids = [t.id for t in tasks]
        last_by_task, last_completed_by_task = _fetch_last_and_completed_executions(db, task_ids)
        return ScheduledTaskListResponse(
            tasks=[
                ScheduledTaskResponse.from_orm(
                    t,
                    last_execution=last_by_task.get(t.id),
                    last_completed_execution=last_completed_by_task.get(t.id),
                )
                for t in tasks
            ],
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
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Get recent executions across all tasks."""
    user_id = user.get("id")
    try:
        executions = task_service.get_recent_executions(
            db,
            namespace=task_service.namespace,
            user_id=user_id,
            limit=limit,
        )
        execution_responses = [ExecutionResponse.from_orm(ex) for ex in executions]
        return ExecutionListResponse(
            executions=execution_responses,
            total=len(execution_responses),
            skip=0,
            limit=limit,
        )
    except Exception as e:
        log.error("Error fetching recent executions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent executions") from e


@router.get("/executions/by-a2a-task/{a2a_task_id}", response_model=ExecutionResponse)
async def get_execution_by_a2a_task_id(
    a2a_task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Look up a scheduled task execution by its A2A task ID."""
    try:
        execution = task_service.get_execution_by_a2a_task_id(db, a2a_task_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found for this A2A task ID")

        task = task_service.get_task(db, execution.scheduled_task_id)
        if not task or task.created_by != user.get("id"):
            raise HTTPException(status_code=404, detail="Execution not found for this A2A task ID")

        return ExecutionResponse.from_orm(execution)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching execution by A2A task ID: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch execution") from e


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Fetch a single execution by id, scoped to the caller's owned tasks."""
    user_id = user.get("id")
    try:
        execution = task_service.get_execution(db, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        task = task_service.get_task(db, execution.scheduled_task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail="Execution not found")
        _check_task_ownership(task, user_id, user)

        return ExecutionResponse.from_orm(execution)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching execution %s: %s", execution_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch execution") from e


@router.delete("/executions/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    execution_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Hard-delete a single execution from a task's history."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")

    # Pre-commit phase: ownership checks + lookup. Rolled back on failure so a
    # half-loaded session doesn't leave dirty state behind. The commit lives
    # inside task_service.delete_execution; once it returns, the transaction is
    # already closed and any later failure must NOT issue a rollback (it would
    # operate on a fresh implicit transaction and mask the real error).
    try:
        execution = task_service.get_execution(db, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        task = task_service.get_task(db, execution.scheduled_task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail="Execution not found")
        _check_task_ownership(task, user_id, user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error preparing execution delete %s: %s", execution_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete execution") from e

    try:
        deleted = task_service.delete_execution(db, execution_id)
    except Exception as e:
        log.error("Error deleting execution %s: %s", execution_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete execution") from e

    if not deleted:
        raise HTTPException(status_code=404, detail="Execution not found")


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
        return SchedulerStatusResponse(**scheduler_service.get_status())
    except Exception as e:
        log.error("Error fetching scheduler status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch scheduler status") from e


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Get details of a specific scheduled task."""
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        last_map, last_completed_map = _fetch_last_and_completed_executions(db, [task.id])
        last = last_map.get(task.id)
        last_completed = last_completed_map.get(task.id)
        return ScheduledTaskResponse.from_orm(task, last_execution=last, last_completed_execution=last_completed)
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
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    agent_registry=Depends(get_agent_registry),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Update a scheduled task."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        existing_task = task_service.get_task(db, task_id, user_id=user_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        _check_task_ownership(existing_task, user_id, user)

        # Config-sourced tasks are read-only except enable/disable
        if existing_task.source == "config":
            update_fields = {k for k, v in request.dict(exclude_none=True).items()}
            if not update_fields.issubset({"enabled"}):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Config-sourced tasks can only be enabled/disabled via the UI"
                )

        # RBAC - Validate target agent access if being changed
        if request.target_agent_name is not None:
            agent = agent_registry.get_agent(request.target_agent_name)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target agent '{request.target_agent_name}' not found in registry"
                )
            operation_spec = {"operation_type": "agent_access", "target_agent": request.target_agent_name}
            validation_result = config_resolver.validate_operation_config(
                user_config, operation_spec, {"source": "scheduled_tasks_endpoint"}
            )
            if not validation_result.get("valid", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to target agent '{request.target_agent_name}'"
                )

        update_data = request.dict(exclude_none=True)

        if "task_message" in update_data and request.task_message is not None:
            update_data["task_message"] = [part.dict() for part in request.task_message]
        if "notification_config" in update_data and request.notification_config:
            update_data["notification_config"] = request.notification_config.dict()

        updated_task = await task_service.update_and_reschedule(db, task_id, update_data)
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
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Soft delete a scheduled task."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        _check_task_ownership(task, user_id, user)

        deleted = task_service.delete_task(db, task_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)

        try:
            await task_service.unschedule_task(task_id)
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
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Enable a scheduled task."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        _check_task_ownership(task, user_id, user)

        enabled_task = task_service.enable_task(db, task_id)
        if enabled_task:
            try:
                await task_service.schedule_task(enabled_task)
            except Exception as e:
                log.error("Failed to schedule task %s: %s", task_id, e)

        return TaskActionResponse(success=True, message="Task enabled successfully", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error enabling scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enable scheduled task") from e


@router.post("/{task_id}/run", response_model=TaskActionResponse)
async def run_scheduled_task_now(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    task_service: ScheduledTaskService = Depends(get_task_service),
    scheduler_service=Depends(get_scheduler_service),
):
    """Manually trigger a scheduled task ("Run Now").

    Rejects with 409 if an execution is already in-flight for this task.
    Disabled tasks may still be run so users can verify behaviour before
    enabling. Does not shift the task's next_run_at.
    """
    from ..services.scheduler.scheduler_service import TaskAlreadyRunningError, TaskNotFoundError

    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        _check_task_ownership(task, user_id, user)

        try:
            await scheduler_service.trigger_task_now(task_id, triggered_by=user_id)
        except TaskNotFoundError as e:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG) from e
        except TaskAlreadyRunningError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task is currently executing; wait for it to finish before running again.",
            ) from e

        return TaskActionResponse(success=True, message="Task triggered", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error running scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run scheduled task") from e


@router.post("/{task_id}/disable", response_model=TaskActionResponse)
async def disable_scheduled_task(
    task_id: str,
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    user_config: dict = Depends(get_user_config),
    config_resolver=Depends(get_config_resolver),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Disable a scheduled task."""
    _validate_scheduling_permission(user_config, config_resolver)
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        _check_task_ownership(task, user_id, user)

        disabled_task = task_service.disable_task(db, task_id)
        if disabled_task:
            try:
                await task_service.unschedule_task(task_id)
            except Exception as e:
                log.error("Failed to unschedule task %s: %s", task_id, e)

        return TaskActionResponse(success=True, message="Task disabled successfully", task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error("Error disabling scheduled task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to disable scheduled task") from e


@router.get("/{task_id}/executions", response_model=ExecutionListResponse)
async def get_task_executions(
    task_id: str,
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    scheduled_after: Optional[int] = Query(default=None, alias="scheduledAfter", description="Filter to executions whose scheduled_for >= this epoch ms"),
    scheduled_before: Optional[int] = Query(default=None, alias="scheduledBefore", description="Filter to executions whose scheduled_for <= this epoch ms"),
    db: DBSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    task_service: ScheduledTaskService = Depends(get_task_service),
):
    """Get execution history for a scheduled task. Optional `scheduledAfter`
    and `scheduledBefore` (epoch ms) bound the result by `scheduled_for`."""
    user_id = user.get("id")
    try:
        task = task_service.get_task(db, task_id, user_id=user_id)
        if not task:
            raise HTTPException(status_code=404, detail=TASK_NOT_FOUND_MSG)
        if task.user_id and task.user_id != user_id:
            raise HTTPException(status_code=403, detail=UNAUTHORIZED_MSG)

        pagination = PaginationParams(page_number=page_number, page_size=page_size)
        executions, total = task_service.get_task_executions(
            db, task_id, pagination, scheduled_after=scheduled_after, scheduled_before=scheduled_before
        )

        return ExecutionListResponse(
            executions=[ExecutionResponse.from_orm(ex) for ex in executions],
            total=total,
            skip=pagination.offset,
            limit=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("Error fetching executions for task %s: %s", task_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch task executions") from e
