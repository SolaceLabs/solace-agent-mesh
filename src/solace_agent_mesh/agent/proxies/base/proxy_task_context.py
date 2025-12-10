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
