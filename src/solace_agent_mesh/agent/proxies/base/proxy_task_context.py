"""
Encapsulates the runtime state for a single, in-flight proxied agent task.
"""

from typing import Any, Dict
from dataclasses import dataclass, field


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

    # Text batching state
    _streaming_text_buffer: str = field(default="", init=False)
    _batching_threshold_bytes: int = field(default=100, init=True)
    _has_published_batched_text: bool = field(default=False, init=False)
    _has_published_converted_artifact: bool = field(default=False, init=False)

    def append_to_streaming_buffer(self, text: str) -> None:
        """Appends text to the streaming buffer for batching."""
        self._streaming_text_buffer += text

    def get_streaming_buffer_content(self) -> str:
        """Returns the current content of the streaming buffer."""
        return self._streaming_text_buffer

    def clear_streaming_buffer(self) -> None:
        """Clears the streaming buffer."""
        self._streaming_text_buffer = ""

    def get_batching_threshold(self) -> int:
        """Returns the batching threshold in bytes for this task."""
        return self._batching_threshold_bytes

    def mark_batched_text_published(self) -> None:
        """Marks that batched text has been published for this task."""
        self._has_published_batched_text = True

    def has_published_batched_text(self) -> bool:
        """Returns whether batched text has been published for this task."""
        return self._has_published_batched_text

    def mark_converted_artifact_published(self) -> None:
        """Marks that a converted artifact has been published for this task."""
        self._has_published_converted_artifact = True

    def has_published_converted_artifact(self) -> bool:
        """Returns whether a converted artifact has been published for this task."""
        return self._has_published_converted_artifact

    def has_published_streaming_text(self) -> bool:
        """Returns whether any streaming text (batched or artifact) has been published."""
        return self._has_published_batched_text or self._has_published_converted_artifact
