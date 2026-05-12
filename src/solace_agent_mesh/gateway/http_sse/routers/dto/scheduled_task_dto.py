"""
Pydantic models for scheduled tasks API.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from croniter import croniter
import pytz

from ...shared import MINIMUM_INTERVAL_SECONDS, is_quartz_weekday_cron, parse_interval_to_seconds


class NotificationChannelConfig(BaseModel):
    """Configuration for a notification channel."""
    type: str = Field(..., description="Channel type: sse, webhook, email, broker_topic")
    config: Dict[str, Any] = Field(..., description="Channel-specific configuration")


class NotificationConfig(BaseModel):
    """Notification configuration for scheduled tasks."""
    channels: List[NotificationChannelConfig] = Field(default_factory=list)
    on_success: bool = Field(default=True, description="Send notifications on success")
    on_failure: bool = Field(default=True, description="Send notifications on failure")
    include_artifacts: bool = Field(default=False, description="Include artifacts in notifications")


class MessagePart(BaseModel):
    """A part of the task message."""
    type: str = Field(..., description="Part type: text or file")
    text: Optional[str] = Field(None, description="Text content (for type=text)")
    uri: Optional[str] = Field(None, description="File URI (for type=file)")


class CreateScheduledTaskRequest(BaseModel):
    """Request to create a new scheduled task."""
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: Optional[str] = Field(None, max_length=1000, description="Task description")

    schedule_type: str = Field(..., description="Schedule type: cron, interval, or one_time")
    schedule_expression: str = Field(..., description="Schedule expression")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")

    target_agent_name: str = Field(..., description="Target agent name")
    target_type: str = Field(default="agent", description="Target type: agent or workflow")
    task_message: List[MessagePart] = Field(..., min_length=1, description="Task message parts")
    task_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional A2A metadata")

    enabled: bool = Field(default=True, description="Enable task immediately")
    max_retries: int = Field(default=0, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=0, description="Delay between retries")
    timeout_seconds: int = Field(default=3600, ge=60, description="Execution timeout")

    notification_config: Optional[NotificationConfig] = Field(None, description="Notification settings")
    user_level: bool = Field(default=True, description="True for user-specific, False for namespace-level")

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text_fields(cls, v):
        """Strip leading/trailing whitespace so ``"Daily Report"`` and
        ``"Daily Report "`` don't appear as two distinct tasks in the UI."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone against pytz.all_timezones."""
        if v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}. Must be a valid IANA timezone.")
        return v

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in ("agent", "workflow"):
            raise ValueError(f"Invalid target_type: {v}. Must be 'agent' or 'workflow'.")
        return v

    @field_validator("schedule_expression")
    @classmethod
    def validate_schedule_expression(cls, v: str, info) -> str:
        """Validate schedule expression based on schedule_type."""
        schedule_type = info.data.get("schedule_type")

        if schedule_type == "cron":
            # Allow Quartz-style day-of-week tokens (`1#2`, `5L`) emitted by
            # the monthly-weekday UI mode; they're translated to APScheduler's
            # programmatic CronTrigger at schedule time. croniter rejects `5L`
            # outright, so we check the Quartz form first.
            if not is_quartz_weekday_cron(v) and not croniter.is_valid(v):
                raise ValueError(f"Invalid cron expression: {v}")
        elif schedule_type == "interval":
            if not v or not v[-1] in "smhd":
                raise ValueError(f"Invalid interval format: {v}. Use format like '30s', '5m', '1h', '1d'")
            try:
                parse_interval_to_seconds(v)
            except ValueError as e:
                raise ValueError(str(e)) from e
        elif schedule_type == "one_time":
            from datetime import datetime
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError(f"Invalid ISO 8601 datetime: {v}")
        else:
            raise ValueError(f"Invalid schedule_type: {schedule_type}")

        return v


class UpdateScheduledTaskRequest(BaseModel):
    """Request to update a scheduled task."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    schedule_type: Optional[str] = None
    schedule_expression: Optional[str] = None
    timezone: Optional[str] = None

    target_agent_name: Optional[str] = None
    target_type: Optional[str] = None
    task_message: Optional[List[MessagePart]] = None
    task_metadata: Optional[Dict[str, Any]] = None

    enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=0)
    timeout_seconds: Optional[int] = Field(None, ge=60)

    notification_config: Optional[NotificationConfig] = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text_fields(cls, v):
        """Strip leading/trailing whitespace so updates can't reintroduce
        ``"Daily Report "`` as a visual duplicate of ``"Daily Report"``."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}. Must be a valid IANA timezone.")
        return v

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("agent", "workflow"):
            raise ValueError(f"Invalid target_type: {v}. Must be 'agent' or 'workflow'.")
        return v

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("cron", "interval", "one_time"):
            raise ValueError(f"Invalid schedule_type: {v}. Must be 'cron', 'interval', or 'one_time'.")
        return v

    @model_validator(mode="after")
    def validate_schedule_expression_matches_type(self):
        """Validate schedule_expression against schedule_type when both are provided."""
        stype = self.schedule_type
        expr = self.schedule_expression
        if expr is not None and stype is not None:
            if stype == "cron":
                if not is_quartz_weekday_cron(expr) and not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
            elif stype == "interval":
                try:
                    parse_interval_to_seconds(expr)
                except ValueError as e:
                    raise ValueError(str(e)) from e
            elif stype == "one_time":
                from datetime import datetime
                try:
                    datetime.fromisoformat(expr)
                except ValueError:
                    raise ValueError(f"Invalid ISO 8601 datetime: {expr}")
        return self


class LastExecutionSummary(BaseModel):
    """Compact summary of the most-recent execution for discoverability on the
    task card — lets the list view answer "did my task work?" at a glance
    without navigating into history."""
    id: str
    status: str
    scheduled_for: int
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    trigger_type: Optional[str] = "scheduled"


class ScheduledTaskResponse(BaseModel):
    """Response model for a scheduled task."""
    id: str
    name: str
    description: Optional[str]

    namespace: str
    user_id: Optional[str]
    created_by: str

    schedule_type: str
    schedule_expression: str
    timezone: str

    target_agent_name: str
    target_type: str
    task_message: List[Dict[str, Any]]
    task_metadata: Optional[Dict[str, Any]]

    enabled: bool
    status: str
    max_retries: int
    retry_delay_seconds: int
    timeout_seconds: int

    source: Optional[str]
    consecutive_failure_count: int
    run_count: int

    notification_config: Optional[Dict[str, Any]]

    created_at: int
    updated_at: int
    next_run_at: Optional[int]
    last_run_at: Optional[int]

    last_execution: Optional[LastExecutionSummary] = None
    # Most recent *terminal* execution. Surfaced separately so cards can keep
    # showing "Succeeded N min ago" even while a new run is in flight (in which
    # case `last_execution` reflects the running one).
    last_completed_execution: Optional[LastExecutionSummary] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj, last_execution: Optional["LastExecutionSummary"] = None, last_completed_execution: Optional["LastExecutionSummary"] = None):
        """Create ScheduledTaskResponse from ORM model, computing status."""
        data = {
            'id': obj.id,
            'name': obj.name,
            'description': obj.description,
            'namespace': obj.namespace,
            'user_id': obj.user_id,
            'created_by': obj.created_by,
            'schedule_type': obj.schedule_type.value if hasattr(obj.schedule_type, 'value') else obj.schedule_type,
            'schedule_expression': obj.schedule_expression,
            'timezone': obj.timezone,
            'target_agent_name': obj.target_agent_name,
            'target_type': obj.target_type,
            'task_message': obj.task_message,
            'task_metadata': obj.task_metadata,
            'enabled': obj.enabled,
            'status': _derive_task_status(obj.enabled, obj.consecutive_failure_count),
            'max_retries': obj.max_retries,
            'retry_delay_seconds': obj.retry_delay_seconds,
            'timeout_seconds': obj.timeout_seconds,
            'source': obj.source,
            'consecutive_failure_count': obj.consecutive_failure_count,
            'run_count': obj.run_count,
            'notification_config': obj.notification_config,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
            'next_run_at': obj.next_run_at,
            'last_run_at': obj.last_run_at,
            'last_execution': last_execution,
            'last_completed_execution': last_completed_execution,
        }
        return cls(**data)


def _derive_task_status(enabled: bool, consecutive_failure_count: int) -> str:
    """Derive a display status from task fields.

    Returns:
        "error"  – if the task has consecutive failures
        "paused" – if the task is disabled
        "active" – otherwise
    """
    if consecutive_failure_count and consecutive_failure_count > 0:
        return "error"
    if not enabled:
        return "paused"
    return "active"


class ScheduledTaskListResponse(BaseModel):
    """Response model for paginated list of scheduled tasks."""
    tasks: List[ScheduledTaskResponse]
    total: int
    skip: int
    limit: int


class ArtifactInfo(BaseModel):
    """Artifact information."""
    name: str
    uri: str


class ExecutionResponse(BaseModel):
    """Response model for a task execution."""
    id: str
    scheduled_task_id: str

    status: str
    a2a_task_id: Optional[str]

    scheduled_for: int
    started_at: Optional[int]
    completed_at: Optional[int]
    duration_ms: Optional[int] = None

    result_summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int

    trigger_type: Optional[str] = "scheduled"
    triggered_by: Optional[str] = None

    artifacts: Optional[List[Union[str, Dict[str, Any], ArtifactInfo]]]
    notifications_sent: Optional[List[Dict[str, Any]]]

    task_snapshot: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Create ExecutionResponse from ORM model, calculating duration_ms."""
        data = {
            'id': obj.id,
            'scheduled_task_id': obj.scheduled_task_id,
            'status': obj.status,
            'a2a_task_id': obj.a2a_task_id,
            'scheduled_for': obj.scheduled_for,
            'started_at': obj.started_at,
            'completed_at': obj.completed_at,
            'result_summary': obj.result_summary,
            'error_message': obj.error_message,
            'retry_count': obj.retry_count,
            'trigger_type': getattr(obj, 'trigger_type', None) or "scheduled",
            'triggered_by': getattr(obj, 'triggered_by', None),
            'artifacts': obj.artifacts,
            'notifications_sent': obj.notifications_sent,
            'task_snapshot': getattr(obj, 'task_snapshot', None),
        }

        if obj.started_at and obj.completed_at:
            data['duration_ms'] = obj.completed_at - obj.started_at

        return cls(**data)


class ExecutionListResponse(BaseModel):
    """Response model for paginated list of executions."""
    executions: List[ExecutionResponse]
    total: int
    skip: int
    limit: int


class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status."""
    instance_id: str
    namespace: str
    active_tasks_count: int
    running_executions_count: int
    scheduler_running: bool
    pending_results_count: Optional[int] = None


class TaskActionResponse(BaseModel):
    """Response for task actions (enable/disable/delete)."""
    success: bool
    message: str
    task_id: str


class SchedulePreviewRequest(BaseModel):
    """Request for previewing next execution times."""
    schedule_type: str = Field(..., description="Schedule type: cron or interval")
    schedule_expression: str = Field(..., description="Schedule expression")
    timezone: str = Field(default="UTC", description="Timezone")
    count: int = Field(default=5, ge=1, le=20, description="Number of execution times to preview")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {v}")
        return v


class SchedulePreviewResponse(BaseModel):
    """Response with next execution times."""
    next_times: List[str]
    schedule_type: str
    schedule_expression: str
    timezone: str
