"""
Pydantic models for scheduled tasks API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from croniter import croniter


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
    task_message: List[MessagePart] = Field(..., min_length=1, description="Task message parts")
    task_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional A2A metadata")
    
    enabled: bool = Field(default=True, description="Enable task immediately")
    max_retries: int = Field(default=0, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=0, description="Delay between retries")
    timeout_seconds: int = Field(default=3600, ge=60, description="Execution timeout")
    
    notification_config: Optional[NotificationConfig] = Field(None, description="Notification settings")
    user_level: bool = Field(default=True, description="True for user-specific, False for namespace-level")

    @field_validator("schedule_expression")
    @classmethod
    def validate_schedule_expression(cls, v: str, info) -> str:
        """Validate schedule expression based on schedule_type."""
        schedule_type = info.data.get("schedule_type")
        
        if schedule_type == "cron":
            if not croniter.is_valid(v):
                raise ValueError(f"Invalid cron expression: {v}")
        elif schedule_type == "interval":
            # Validate interval format (e.g., "30s", "5m", "1h", "1d")
            if not v or not v[-1] in "smhd":
                raise ValueError(f"Invalid interval format: {v}. Use format like '30s', '5m', '1h', '1d'")
            try:
                int(v[:-1])
            except ValueError:
                raise ValueError(f"Invalid interval value: {v}")
        elif schedule_type == "one_time":
            # Validate ISO 8601 datetime
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
    task_message: Optional[List[MessagePart]] = None
    task_metadata: Optional[Dict[str, Any]] = None
    
    enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=0)
    timeout_seconds: Optional[int] = Field(None, ge=60)
    
    notification_config: Optional[NotificationConfig] = None


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
    task_message: List[Dict[str, Any]]
    task_metadata: Optional[Dict[str, Any]]
    
    enabled: bool
    max_retries: int
    retry_delay_seconds: int
    timeout_seconds: int
    
    notification_config: Optional[Dict[str, Any]]
    
    created_at: int
    updated_at: int
    next_run_at: Optional[int]
    last_run_at: Optional[int]
    
    class Config:
        from_attributes = True


class ScheduledTaskListResponse(BaseModel):
    """Response model for paginated list of scheduled tasks."""
    tasks: List[ScheduledTaskResponse]
    total: int
    skip: int
    limit: int


class ExecutionResponse(BaseModel):
    """Response model for a task execution."""
    id: str
    scheduled_task_id: str
    
    status: str
    a2a_task_id: Optional[str]
    
    scheduled_for: int
    started_at: Optional[int]
    completed_at: Optional[int]
    
    result_summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    
    artifacts: Optional[List[str]]
    notifications_sent: Optional[List[Dict[str, Any]]]
    
    class Config:
        from_attributes = True


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
    is_leader: bool
    active_tasks_count: int
    running_executions_count: int
    scheduler_running: bool
    leader_info: Optional[Dict[str, Any]] = None
    pending_results_count: Optional[int] = None


class TaskActionResponse(BaseModel):
    """Response for task actions (enable/disable/delete)."""
    success: bool
    message: str
    task_id: str