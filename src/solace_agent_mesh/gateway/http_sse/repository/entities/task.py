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

    class Config:
        from_attributes = True
