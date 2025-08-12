"""
Task-related request DTOs.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import UploadFile

from ....shared.types import TaskId, UserId, SessionId, AgentId


class SendTaskRequest(BaseModel):
    """Request DTO for sending a non-streaming task."""
    agent_name: str = Field(..., description="The name of the target A2A agent")
    message: str = Field(..., description="The user's message or prompt")
    user_id: UserId
    client_id: Optional[str] = None
    session_id: Optional[SessionId] = None
    
    class Config:
        # UploadFile cannot be included in Pydantic models directly
        # Files will be handled separately in the controller
        arbitrary_types_allowed = True


class SubscribeTaskRequest(BaseModel):
    """Request DTO for sending a streaming task."""
    agent_name: str = Field(..., description="The name of the target A2A agent")
    message: str = Field(..., description="The user's message or prompt")
    user_id: UserId
    session_id: Optional[SessionId] = None
    client_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class CancelTaskRequest(BaseModel):
    """Request DTO for cancelling a task."""
    task_id: TaskId = Field(..., description="The ID of the task to cancel")
    client_id: Optional[str] = None
    user_id: UserId


class GetTaskStatusRequest(BaseModel):
    """Request DTO for getting task status."""
    task_id: TaskId
    user_id: UserId


class TaskFilesInfo(BaseModel):
    """Information about uploaded files for a task."""
    filename: str
    content_type: str
    size: int
    
    
class ProcessedTaskRequest(BaseModel):
    """Internal DTO for processed task request with file information."""
    agent_name: str
    message: str
    user_id: UserId
    session_id: Optional[SessionId] = None
    client_id: Optional[str] = None
    files: List[TaskFilesInfo] = []
    metadata: Optional[Dict[str, Any]] = None