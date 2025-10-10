"""
Manages Server-Sent Event (SSE) connections for streaming task updates.
"""

import asyncio
import threading
from typing import Dict, List, Any
import json
import datetime
import math

from solace_ai_connector.common.log import log

from .sse_event_buffer import SSEEventBuffer


class SSEManager:
    """
    Manages active SSE connections and distributes events based on task ID.
    Uses asyncio Queues for buffering events per connection.
    """

    def __init__(self, max_queue_size: int, event_buffer: SSEEventBuffer):
        self._connections: Dict[str, List[asyncio.Queue]] = {}
        self._event_buffer = event_buffer
        self._locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._locks_lock = threading.Lock()
        self.log_identifier = "[SSEManager]"
        self._max_queue_size = max_queue_size

    def _get_lock(self) -> asyncio.Lock:
        """Get or create a lock for the current event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            log.error(
                "%s _get_lock must be called from within an async context.",
                self.log_identifier,
            )
            raise RuntimeError(
                "SSEManager methods must be called from within an async context"
            )

        with self._locks_lock:
            if current_loop not in self._locks:
                self._locks[current_loop] = asyncio.Lock()
                log.debug(
                    "%s Created new lock for event loop %s",
                    self.log_identifier,
                    id(current_loop),
                )
            return self._locks[current_loop]

    def _sanitize_json(self, obj):
        if isinstance(obj, dict):
            return {k: self._sanitize_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_json(v) for v in obj]
        elif isinstance(obj, (float, int)):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, (str, bool, type(None))):
            return obj
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        else:
            return str(obj)

    async def create_sse_connection(self, task_id: str) -> asyncio.Queue:
        """
        Creates a new queue for an SSE connection subscribing to a task.

        Args:
            task_id: The ID of the task the connection is interested in.

        Returns:
            An asyncio.Queue that the SSE endpoint can consume from.
        """
        lock = self._get_lock()
        async with lock:
            if task_id not in self._connections:
                self._connections[task_id] = []

            connection_queue = asyncio.Queue(maxsize=self._max_queue_size)

            # Flush any pending events from the buffer to the new connection
            buffered_events = self._event_buffer.get_and_remove_buffer(task_id)
            if buffered_events:
                for event in buffered_events:
                    await connection_queue.put(event)

            self._connections[task_id].append(connection_queue)
            log.debug(
                "%s Created SSE connection queue for Task ID: %s. Total queues for task: %d",
                self.log_identifier,
                task_id,
                len(self._connections[task_id]),
            )
            return connection_queue

    async def remove_sse_connection(
        self, task_id: str, connection_queue: asyncio.Queue
    ):
        """
        Removes a specific SSE connection queue for a task.

        Args:
            task_id: The ID of the task.
            connection_queue: The specific queue instance to remove.
        """
        lock = self._get_lock()
        async with lock:
            if task_id in self._connections:
                try:
                    self._connections[task_id].remove(connection_queue)
                    log.debug(
                        "%s Removed SSE connection queue for Task ID: %s. Remaining queues: %d",
                        self.log_identifier,
                        task_id,
                        len(self._connections[task_id]),
                    )
                    if not self._connections[task_id]:
                        del self._connections[task_id]
                        log.debug(
                            "%s Removed Task ID entry: %s as no connections remain.",
                            self.log_identifier,
                            task_id,
                        )
                except ValueError:
                    log.debug(
                        "%s Attempted to remove an already removed queue for Task ID: %s.",
                        self.log_identifier,
                        task_id,
                    )
            else:
                log.warning(
                    "%s Attempted to remove queue for non-existent Task ID: %s.",
                    self.log_identifier,
                    task_id,
                )

    async def send_event(
        self, task_id: str, event_data: Dict[str, Any], event_type: str = "message"
    ):
        """
        Sends an event (as a dictionary) to all active SSE connections for a specific task.
        The event_data dictionary will be JSON serialized for the SSE 'data' field.

        Args:
            task_id: The ID of the task the event belongs to.
            event_data: The dictionary representing the A2A event (e.g., TaskStatusUpdateEvent).
            event_type: The type of the SSE event (default: "message").
        """
        lock = self._get_lock()
        async with lock:
            queues = self._connections.get(task_id)

            try:
                serialized_data = json.dumps(
                    self._sanitize_json(event_data), allow_nan=False
                )
            except Exception as json_err:
                log.error(
                    "%s Failed to JSON serialize event data for Task ID %s: %s",
                    self.log_identifier,
                    task_id,
                    json_err,
                )
                return

            sse_payload = {"event": event_type, "data": serialized_data}

            if not queues:
                log.debug(
                    "%s No active SSE connections for Task ID: %s. Buffering event.",
                    self.log_identifier,
                    task_id,
                )
                self._event_buffer.buffer_event(task_id, sse_payload)
                return

            log.debug(
                "%s Prepared SSE payload for Task ID %s: %s",
                self.log_identifier,
                task_id,
                sse_payload,
            )

            queues_to_remove = []
            for connection_queue in list(self._connections.get(task_id, [])):
                try:
                    await asyncio.wait_for(
                        connection_queue.put(sse_payload), timeout=0.1
                    )
                    log.debug(
                        "%s Queued event for Task ID: %s to one connection.",
                        self.log_identifier,
                        task_id,
                    )
                except asyncio.QueueFull:
                    log.warning(
                        "%s SSE connection queue full for Task ID: %s. Event dropped for one connection.",
                        self.log_identifier,
                        task_id,
                    )
                    queues_to_remove.append(connection_queue)
                except asyncio.TimeoutError:
                    log.warning(
                        "%s Timeout putting event onto SSE queue for Task ID: %s. Event dropped for one connection.",
                        self.log_identifier,
                        task_id,
                    )
                    queues_to_remove.append(connection_queue)
                except Exception as e:
                    log.error(
                        "%s Error putting event onto queue for Task ID %s: %s",
                        self.log_identifier,
                        task_id,
                        e,
                    )
                    queues_to_remove.append(connection_queue)

            if queues_to_remove and task_id in self._connections:
                current_queues = self._connections[task_id]
                for q in queues_to_remove:
                    try:
                        current_queues.remove(q)
                        log.warning(
                            "%s Removed potentially broken/full SSE queue for Task ID: %s",
                            self.log_identifier,
                            task_id,
                        )
                    except ValueError:
                        pass

                if not current_queues:
                    del self._connections[task_id]
                    log.debug(
                        "%s Removed Task ID entry: %s after cleaning queues.",
                        self.log_identifier,
                        task_id,
                    )

    async def close_connection(self, task_id: str, connection_queue: asyncio.Queue):
        """
        Signals a specific SSE connection queue to close by putting None.
        Also removes the queue from the manager.
        """
        log.debug(
            "%s Closing specific SSE connection queue for Task ID: %s",
            self.log_identifier,
            task_id,
        )
        try:
            await asyncio.wait_for(connection_queue.put(None), timeout=0.1)
        except asyncio.QueueFull:
            log.warning(
                "%s Could not put None (close signal) on full queue for Task ID: %s. Connection might not close cleanly.",
                self.log_identifier,
                task_id,
            )
        except asyncio.TimeoutError:
            log.warning(
                "%s Timeout putting None (close signal) on queue for Task ID: %s.",
                self.log_identifier,
                task_id,
            )
        except Exception as e:
            log.error(
                "%s Error putting None (close signal) on queue for Task ID %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
        finally:
            await self.remove_sse_connection(task_id, connection_queue)

    async def close_all_for_task(self, task_id: str):
        """
        Closes all SSE connections associated with a specific task.
        If a connection existed, it also cleans up the event buffer.
        If no connection ever existed, the buffer is left for a late-connecting client.
        """
        lock = self._get_lock()
        async with lock:
            if task_id in self._connections:
                # This is the "normal" case: a client is or was connected.
                # It's safe to clean up everything.
                queues_to_close = self._connections.pop(task_id)
                log.debug(
                    "%s Closing %d SSE connections for Task ID: %s and cleaning up buffer.",
                    self.log_identifier,
                    len(queues_to_close),
                    task_id,
                )
                for q in queues_to_close:
                    try:
                        await asyncio.wait_for(q.put(None), timeout=0.1)
                    except asyncio.QueueFull:
                        log.warning(
                            "%s Could not put None (close signal) on full queue during close_all for Task ID: %s.",
                            self.log_identifier,
                            task_id,
                        )
                    except asyncio.TimeoutError:
                        log.warning(
                            "%s Timeout putting None (close signal) on queue during close_all for Task ID: %s.",
                            self.log_identifier,
                            task_id,
                        )
                    except Exception as e:
                        log.error(
                            "%s Error putting None (close signal) on queue during close_all for Task ID %s: %s",
                            self.log_identifier,
                            task_id,
                            e,
                        )

                # Since a connection existed, the buffer is no longer needed.
                self._event_buffer.remove_buffer(task_id)
                log.debug(
                    "%s Removed Task ID entry: %s and signaled queues to close.",
                    self.log_identifier,
                    task_id,
                )
            else:
                # This is the "race condition" case: no client has connected yet.
                # We MUST leave the buffer intact for the late-connecting client.
                log.debug(
                    "%s No active connections found for Task ID: %s. Leaving event buffer intact.",
                    self.log_identifier,
                    task_id,
                )

    def cleanup_old_locks(self):
        """Remove locks for closed event loops to prevent memory leaks."""
        with self._locks_lock:
            closed_loops = [loop for loop in self._locks if loop.is_closed()]
            for loop in closed_loops:
                del self._locks[loop]
                log.debug(
                    "%s Cleaned up lock for closed event loop %s",
                    self.log_identifier,
                    id(loop),
                )

    async def close_all(self):
        """Closes all active SSE connections managed by this instance."""
        self.cleanup_old_locks()
        lock = self._get_lock()
        async with lock:
            log.debug("%s Closing all active SSE connections...", self.log_identifier)
            all_task_ids = list(self._connections.keys())
            closed_count = 0
            for task_id in all_task_ids:
                if task_id in self._connections:
                    queues = self._connections.pop(task_id)
                    closed_count += len(queues)
                    for q in queues:
                        try:
                            await asyncio.wait_for(q.put(None), timeout=0.1)
                        except Exception:
                            pass
            log.debug(
                "%s Closed %d connections for tasks: %s",
                self.log_identifier,
                closed_count,
                all_task_ids,
            )
            self._connections.clear()
