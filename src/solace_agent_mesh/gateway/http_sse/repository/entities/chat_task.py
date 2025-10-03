"""
ChatTask domain entity.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChatTask(BaseModel):
    """ChatTask domain entity with business logic."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    user_message: Optional[str] = None
    message_bubbles: List[Dict[str, Any]]
    task_metadata: Optional[Dict[str, Any]] = None
    created_time: int
    updated_time: Optional[int] = None

    @field_validator("message_bubbles")
    @classmethod
    def validate_message_bubbles(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate that message_bubbles is a non-empty list with required fields."""
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

    def add_feedback(self, feedback_type: str, feedback_text: Optional[str] = None) -> None:
        """Add or update feedback for this task."""
        if self.task_metadata is None:
            self.task_metadata = {}
        
        self.task_metadata["feedback"] = {
            "type": feedback_type,
            "text": feedback_text,
            "submitted": True
        }

    def get_feedback(self) -> Optional[Dict[str, Any]]:
        """Get feedback for this task."""
        if self.task_metadata:
            return self.task_metadata.get("feedback")
        return None
