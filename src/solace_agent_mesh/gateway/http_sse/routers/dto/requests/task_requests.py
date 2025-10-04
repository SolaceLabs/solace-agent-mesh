"""
Task-related request DTOs.
"""

import json
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SaveTaskRequest(BaseModel):
    """Request DTO for saving a task."""
    
    task_id: str = Field(..., alias="taskId", min_length=1)
    user_message: Optional[str] = Field(None, alias="userMessage")
    message_bubbles: str = Field(..., alias="messageBubbles")  # JSON string (opaque)
    task_metadata: Optional[str] = Field(None, alias="taskMetadata")  # JSON string (opaque)
    
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
    def validate_message_bubbles(cls, v: str) -> str:
        """Validate that message_bubbles is a non-empty JSON string."""
        if not v or not v.strip():
            raise ValueError("message_bubbles cannot be empty")
        
        # Validate it's valid JSON (but don't validate structure)
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list) or len(parsed) == 0:
                raise ValueError("message_bubbles must be a non-empty JSON array")
        except json.JSONDecodeError as e:
            raise ValueError(f"message_bubbles must be valid JSON: {e}")
        
        return v
    
    @field_validator("task_metadata")
    @classmethod
    def validate_task_metadata(cls, v: Optional[str]) -> Optional[str]:
        """Validate that task_metadata is valid JSON if provided."""
        if v is None or not v.strip():
            return None
        
        # Validate it's valid JSON (but don't validate structure)
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"task_metadata must be valid JSON: {e}")
        
        return v
