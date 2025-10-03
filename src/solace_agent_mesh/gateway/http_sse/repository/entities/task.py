"""
Task domain entity.
"""

from pydantic import BaseModel


class Task(BaseModel):
    """Task domain entity."""

    id: str
    user_id: str
    start_time: int
    end_time: int | None = None
    status: str | None = None
    initial_request_text: str | None = None
    
    # Token usage fields
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_cached_input_tokens: int | None = None
    token_usage_details: dict | None = None

    class Config:
        from_attributes = True
