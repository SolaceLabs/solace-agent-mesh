"""
Task-related response DTOs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .base_responses import BaseTimestampResponse


class TaskResponse(BaseTimestampResponse):
    """Response DTO for a single task."""
    
    task_id: str = Field(..., alias="taskId")
    session_id: str = Field(..., alias="sessionId")
    user_message: Optional[str] = Field(None, alias="userMessage")
    message_bubbles: List[Dict[str, Any]] = Field(..., alias="messageBubbles")
    task_metadata: Optional[Dict[str, Any]] = Field(None, alias="taskMetadata")
    created_time: int = Field(..., alias="createdTime")
    updated_time: Optional[int] = Field(None, alias="updatedTime")
    
    model_config = {"populate_by_name": True}


class TaskListResponse(BaseModel):
    """Response DTO for a list of tasks."""
    
    tasks: List[TaskResponse]
    
    model_config = {"populate_by_name": True}
