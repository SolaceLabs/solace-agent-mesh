"""
Feedback domain entity.
"""

from pydantic import BaseModel


class Feedback(BaseModel):
    """Feedback domain entity."""

    id: str
    session_id: str
    task_id: str
    user_id: str
    rating: str
    comment: str | None = None
    created_time: int

    class Config:
        from_attributes = True
