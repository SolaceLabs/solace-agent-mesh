"""
ChatTask domain entity.
"""

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChatTask(BaseModel):
    """ChatTask domain entity with business logic."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    user_message: Optional[str] = None
    message_bubbles: str  # JSON string (opaque to backend)
    task_metadata: Optional[str] = None  # JSON string (opaque to backend)
    created_time: int
    updated_time: Optional[int] = None

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

    def add_feedback(self, feedback_type: str, feedback_text: Optional[str] = None) -> None:
        """Add or update feedback for this task."""
        # Parse metadata, update, re-serialize
        metadata = json.loads(self.task_metadata) if self.task_metadata else {}
        
        metadata["feedback"] = {
            "type": feedback_type,
            "text": feedback_text,
            "submitted": True
        }
        
        self.task_metadata = json.dumps(metadata)

    def get_feedback(self) -> Optional[Dict[str, Any]]:
        """Get feedback for this task."""
        if self.task_metadata:
            metadata = json.loads(self.task_metadata)
            return metadata.get("feedback")
        return None
