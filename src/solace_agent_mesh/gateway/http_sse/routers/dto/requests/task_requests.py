"""
Task-related request DTOs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SaveTaskRequest(BaseModel):
    """Request DTO for saving a task."""
    
    task_id: str = Field(..., alias="taskId", min_length=1)
    user_message: Optional[str] = Field(None, alias="userMessage")
    message_bubbles: List[Dict[str, Any]] = Field(..., alias="messageBubbles")
    task_metadata: Optional[Dict[str, Any]] = Field(None, alias="taskMetadata")
    
    model_config = {"populate_by_name": True}
    
    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """Validate that task_id is non-empty."""
        if not v or not v.strip():
            raise ValueError("task_id cannot be empty")
        return v.strip()
    
    @field_validator("message_bubbles")
    @classmethod
    def validate_message_bubbles(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate that message_bubbles is non-empty and has required fields."""
        if not v or len(v) == 0:
            raise ValueError("message_bubbles cannot be empty")
        
        for i, bubble in enumerate(v):
            if not isinstance(bubble, dict):
                raise ValueError(f"message_bubbles[{i}] must be a dictionary")
            if "id" not in bubble:
                raise ValueError(f"message_bubbles[{i}] must have an 'id' field")
            if "type" not in bubble:
                raise ValueError(f"message_bubbles[{i}] must have a 'type' field")
        
        return v
