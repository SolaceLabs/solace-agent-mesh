"""
Encapsulates the runtime state for a single, in-flight proxied agent task.
"""

from typing import Any, Dict
from dataclasses import dataclass


@dataclass
class ProxyTaskContext:
    """
    A class to hold all runtime state and control mechanisms for a single proxied agent task.
    This object is created when a task is initiated and destroyed when it completes.
    """

    task_id: str  # SAM's task ID (used for upstream communication)
    a2a_context: Dict[str, Any]
    downstream_task_id: str | None = None  # Downstream agent's task ID (used for cancellation)
    original_request: Any = None  # Original A2A request (for task pause/resume in OAuth2 flows)
    streaming_buffer: str = ""  # Buffer for accumulating streaming text responses

    def append_to_streaming_buffer(self, text: str) -> None:
        """
        Appends text to the streaming buffer.
        Note: No lock needed - each ProxyTaskContext is accessed only by its own async task handler.
        """
        self.streaming_buffer += text

    def get_streaming_buffer_content(self) -> str:
        """Returns the current buffer content without clearing it."""
        return self.streaming_buffer

    def flush_streaming_buffer(self) -> str:
        """Returns the buffer content and clears it."""
        content = self.streaming_buffer
        self.streaming_buffer = ""
        return content
