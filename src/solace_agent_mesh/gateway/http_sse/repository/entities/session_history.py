"""
Session history composite entity.
"""

from pydantic import BaseModel

from .message import Message
from .session import Session


class SessionHistory(BaseModel):
    """Composite entity representing a session with its messages."""
    
    session: Session
    messages: list[Message] = []
    total_message_count: int = 0