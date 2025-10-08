"""
Task Event domain entity.
"""
from typing import Any

from pydantic import BaseModel


class TaskEvent(BaseModel):
    """TaskEvent domain entity."""

    id: str
    task_id: str
    user_id: str | None = None
    created_time: int
    topic: str
    direction: str
    payload: dict[str, Any]

    class Config:
        from_attributes = True
