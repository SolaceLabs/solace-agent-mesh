"""
A thread-safe buffer for holding early SSE events before a client connects.
"""

import logging
import datetime
import threading
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class SSEEventBuffer:
    """Manages buffering and cleanup of SSE events for tasks without active listeners."""

    def __init__(self, max_queue_size: int, max_age_seconds: int):
        self._pending_events: Dict[
            str, Tuple[datetime.datetime, List[Dict[str, Any]]]
        ] = {}
        self._lock = threading.Lock()
        self._max_queue_size = max_queue_size
        self._max_age_seconds = max_age_seconds
        self.log_identifier = "[SSEEventBuffer]"
        log.debug(
            "%s Initialized with max_age:%ds, max_size:%d",
            self.log_identifier,
            self._max_age_seconds,
            self._max_queue_size,
        )

    def buffer_event(self, task_id: str, event: Dict[str, Any]):
        """Buffers an event for a given task ID."""
        with self._lock:
            if task_id not in self._pending_events:
                self._pending_events[task_id] = (
                    datetime.datetime.now(datetime.timezone.utc),
                    [],
                )

            if len(self._pending_events[task_id][1]) < self._max_queue_size:
                self._pending_events[task_id][1].append(event)
            else:
                log.warning(
                    "%s Buffer full for Task ID: %s. Event dropped.",
                    self.log_identifier,
                    task_id,
                )

    def get_and_remove_buffer(self, task_id: str) -> Optional[List[Dict[str, Any]]]:
        """Atomically retrieves and removes the event buffer for a task."""
        with self._lock:
            buffer_tuple = self._pending_events.pop(task_id, None)
            if buffer_tuple:
                log.debug(
                    "%s Flushing %d events for Task ID: %s",
                    self.log_identifier,
                    len(buffer_tuple[1]),
                    task_id,
                )
                return buffer_tuple[1]
            return None

    def remove_buffer(self, task_id: str):
        """Explicitly removes a buffer for a task, e.g., on finalization."""
        with self._lock:
            if self._pending_events.pop(task_id, None):
                log.debug(
                    "%s Removed buffer for task %s.", self.log_identifier, task_id
                )

    def cleanup_stale_buffers(self):
        """Removes all pending event buffers older than the max age."""
        with self._lock:
            now = datetime.datetime.now(datetime.timezone.utc)
            stale_tasks = [
                task_id
                for task_id, (timestamp, _) in self._pending_events.items()
                if (now - timestamp).total_seconds() > self._max_age_seconds
            ]

            if stale_tasks:
                log.debug(
                    "%s Cleaning up %d stale event buffers.",
                    self.log_identifier,
                    len(stale_tasks),
                )
                for task_id in stale_tasks:
                    del self._pending_events[task_id]
