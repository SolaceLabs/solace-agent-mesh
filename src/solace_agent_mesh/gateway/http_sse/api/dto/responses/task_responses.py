"""
Task-related response DTOs.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from ....shared.types import TaskId, UserId, SessionId, AgentId
from ....shared.enums import TaskStatus


class TaskResponse(BaseModel):
    """Response DTO for task information."""
    task_id: TaskId
    agent_name: str
    status: TaskStatus
    user_id: UserId
    session_id: Optional[SessionId] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SendTaskResponse(BaseModel):
    """Response DTO for send task endpoint."""
    task_id: TaskId
    message: str = "Task submitted successfully"
    status: TaskStatus = TaskStatus.PENDING


class SubscribeTaskResponse(BaseModel):
    """Response DTO for subscribe task endpoint."""
    task_id: TaskId
    session_id: SessionId
    message: str = "Streaming task submitted successfully"
    status: TaskStatus = TaskStatus.PENDING


class CancelTaskResponse(BaseModel):
    """Response DTO for cancel task endpoint."""
    task_id: TaskId
    message: str = "Cancellation request sent successfully"
    cancelled_at: datetime


class TaskStatusResponse(BaseModel):
    """Response DTO for task status."""
    task: TaskResponse


class TaskListResponse(BaseModel):
    """Response DTO for listing tasks."""
    tasks: List[TaskResponse]
    total_count: int


class TaskErrorResponse(BaseModel):
    """Response DTO for task errors."""
    task_id: TaskId
    error_type: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    occurred_at: datetime


class JSONRPCTaskResponse(BaseModel):
    """Response DTO matching the existing JSONRPC format."""
    result: Dict[str, Any]
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    jsonrpc: str = "2.0"