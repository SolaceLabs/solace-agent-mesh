"""
Manages context for tasks being processed by a gateway.
"""

import logging
import threading
from typing import Dict, Optional, Any

log = logging.getLogger(__name__)


class TaskContextManager:
    """
    Stores and retrieves arbitrary context associated with an A2A task_id.

    This context is typically provided by a specific gateway implementation
    (e.g., Slack channel/thread, HTTP session details) and is needed to
    route responses back correctly to the external system.

    The manager is thread-safe.
    """

    def __init__(self):
        """Initializes the TaskContextManager."""
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        log.debug("[TaskContextManager] Initialized.")

    def store_context(self, task_id: str, context_data: Dict[str, Any]) -> None:
        """
        Stores context data for a given task ID.

        Args:
            task_id: The unique identifier for the task.
            context_data: A dictionary containing the context to store.
        """
        with self._lock:
            self._contexts[task_id] = context_data
        log.debug("[TaskContextManager] Stored context for task_id: %s", task_id)

    def get_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the context data for a given task ID.

        Args:
            task_id: The unique identifier for the task.

        Returns:
            The context data dictionary if found, otherwise None.
        """
        with self._lock:
            context = self._contexts.get(task_id)
        log.debug(
            "[TaskContextManager] Retrieved context for task_id: %s (Found: %s)",
            task_id,
            context is not None,
        )
        return context

    def remove_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Removes and returns the context data for a given task ID."""
        with self._lock:
            context = self._contexts.pop(task_id, None)
        log.debug(
            "[TaskContextManager] Removed context for task_id: %s (Found: %s)",
            task_id,
            context is not None,
        )
        return context

    def clear_all_contexts_for_testing(self) -> None:
        """Removes all stored contexts. For testing purposes."""
        with self._lock:
            self._contexts.clear()
        log.debug("[TaskContextManager] All contexts cleared for testing.")
