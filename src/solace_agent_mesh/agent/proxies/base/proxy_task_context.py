"""
Encapsulates the runtime state for a single, in-flight proxied agent task.
"""

import asyncio
from typing import Any, Dict
from dataclasses import dataclass, field


@dataclass
class ProxyTaskContext:
    """
    A class to hold all runtime state and control mechanisms for a single proxied agent task.
    This object is created when a task is initiated and destroyed when it completes.
    """

    task_id: str
    a2a_context: Dict[str, Any]
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)
