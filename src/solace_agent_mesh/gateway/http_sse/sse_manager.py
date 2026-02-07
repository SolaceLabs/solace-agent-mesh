"""
Manages Server-Sent Event (SSE) connections for streaming task updates.
"""

import logging
import asyncio
import threading
from typing import Dict, List, Any, Callable, Optional
import json
import datetime
import math

from .sse_event_buffer import SSEEventBuffer
from .persistent_sse_event_buffer import PersistentSSEEventBuffer

log = logging.getLogger(__name__)
trace_logger = logging.getLogger("sam_trace")


class SSEManager:
    """
    Manages active SSE connections and distributes events based on task ID.
    Uses asyncio Queues for buffering events per connection.

    Note: This manager uses a threading.Lock to ensure thread-safety across
    different event loops (e.g., FastAPI event loop and SAC component event loop).
    """

    def __init__(
        self,
        max_queue_size: int,
        event_buffer: SSEEventBuffer,
        session_factory: Optional[Callable] = None,
        persistent_buffer_enabled: bool = True,
    ):
        self._connections: Dict[str, List[asyncio.Queue]] = {}
        self._event_buffer = event_buffer
        # Use a single threading lock for cross-event-loop synchronization
        self._lock = threading.Lock()
        self.log_identifier = "[SSEManager]"
        self._max_queue_size = max_queue_size
        self._session_factory = session_factory
        self._background_task_cache: Dict[str, bool] = {}  # Cache to avoid repeated DB queries
        self._tasks_with_prior_connection: set = set()  # Track tasks that have had at least one SSE connection
        
        # Initialize persistent buffer for background tasks
        self._persistent_buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=persistent_buffer_enabled,
        )

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
        connection_queue = asyncio.Queue(maxsize=self._max_queue_size)
        buffered_events = None

        # Use threading lock for cross-event-loop synchronization
        with self._lock:
            if task_id not in self._connections:
                self._connections[task_id] = []

            # Get buffered events atomically with adding the queue to connections
            buffered_events = self._event_buffer.get_and_remove_buffer(task_id)

            # Add queue to connections BEFORE releasing lock to ensure
            # no events are buffered after we've retrieved the buffer
            self._connections[task_id].append(connection_queue)

            # Mark this task as having had at least one connection
            # This is used to distinguish "no connection yet" from "had connection but disconnected"
            self._tasks_with_prior_connection.add(task_id)

            log.debug(
                "%s Created SSE connection queue for Task ID: %s. Total queues for task: %d",
                self.log_identifier,
                task_id,
                len(self._connections[task_id]),
            )

        # Put buffered events into queue AFTER releasing the lock
        # This is safe because the queue is already registered in _connections,
        # so any new events will go directly to the queue via send_event
        if buffered_events:
            for event in buffered_events:
                await connection_queue.put(event)

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
        with self._lock:
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

    def _is_background_task(self, task_id: str) -> bool:
        """
        Check if a task is a background task.
        Uses caching and checks registered metadata first, then database.
        
        The order of checks is:
        1. Cache (fastest)
        2. Persistent buffer metadata (registered when task is submitted - before DB record exists)
        3. Database query (fallback) - also reconstructs metadata if found
        
        Args:
            task_id: The ID of the task to check
            
        Returns:
            True if the task is a background task, False otherwise
        """
        # Check cache first
        if task_id in self._background_task_cache:
            return self._background_task_cache[task_id]
        
        # Check if task has metadata registered for persistent buffering
        # This is set when the task is submitted (before the task record is created in DB)
        metadata = self._persistent_buffer.get_task_metadata(task_id)
        if metadata is not None:
            # If metadata exists, this is a background task
            self._background_task_cache[task_id] = True
            log.debug(
                "%s Task %s identified as background task from registered metadata",
                self.log_identifier,
                task_id,
            )
            return True
        
        # Fallback to database query
        # (for tasks that were submitted before we had the persistent buffer metadata)
        if not self._session_factory:
            return False
        
        try:
            from .repository.task_repository import TaskRepository
            
            db = self._session_factory()
            try:
                repo = TaskRepository()
                task = repo.find_by_id(db, task_id)
                is_background = task and task.background_execution_enabled
                
                # Cache the result
                self._background_task_cache[task_id] = is_background
                
                # If this is a background task found via DB, reconstruct metadata
                # This handles the case where metadata was lost (e.g., due to worker restart)
                # and allows events to be properly buffered
                if is_background and task:
                    # Try to get session_id and user_id from the task
                    session_id = getattr(task, 'session_id', None)
                    user_id = getattr(task, 'user_id', None)
                    
                    if session_id and user_id:
                        self._persistent_buffer.set_task_metadata(task_id, session_id, user_id)
                        log.info(
                            "%s Reconstructed metadata for background task %s from database: session=%s, user=%s",
                            self.log_identifier,
                            task_id,
                            session_id,
                            user_id,
                        )
                
                return is_background
            finally:
                db.close()
        except Exception as e:
            log.warning(
                "%s Failed to check if task %s is a background task: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return False

    def register_task_for_persistent_buffer(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Register task metadata for persistent buffering.
        
        This should be called when a background task is created so we have
        the session_id and user_id available when buffering events.
        
        Args:
            task_id: The task ID
            session_id: The session ID
            user_id: The user ID
        """
        self._persistent_buffer.set_task_metadata(task_id, session_id, user_id)
        log.debug(
            "%s Registered task %s for persistent buffering (session=%s)",
            self.log_identifier,
            task_id,
            session_id,
        )

    def get_persistent_buffer(self) -> PersistentSSEEventBuffer:
        """Get the persistent buffer instance."""
        return self._persistent_buffer

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
        # Serialize data outside the lock
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

        # Check if this is a background task (for compatibility during migration)
        is_background_task = self._is_background_task(task_id)
        
        # UNIFIED ARCHITECTURE: Always buffer to persistent storage for replay
        # This enables session switching, browser refresh recovery, and reconnection for ALL tasks
        # The FE will clear the buffer after successfully saving the chat_task
        # Note: We check is_enabled() which is tied to the background_tasks feature flag
        if self._persistent_buffer.is_enabled():
            # Check if this task has metadata registered (ensures we have session_id/user_id)
            # All tasks with registered metadata get buffered
            task_metadata = self._persistent_buffer.get_task_metadata(task_id)
            if task_metadata is not None:
                buffered = self._persistent_buffer.buffer_event(
                    task_id=task_id,
                    event_type=event_type,
                    event_data=sse_payload,  # Store the full SSE payload
                )
                log.debug(
                    "%s Buffered event for task %s: type=%s, is_background=%s, result=%s",
                    self.log_identifier,
                    task_id,
                    event_type,
                    is_background_task,
                    buffered,
                )
            elif is_background_task:
                # Fallback for background tasks without registered metadata
                # This shouldn't happen in normal flow but provides safety
                log.warning(
                    "%s Background task %s has no registered metadata, attempting to buffer anyway",
                    self.log_identifier,
                    task_id,
                )
                self._persistent_buffer.buffer_event(
                    task_id=task_id,
                    event_type=event_type,
                    event_data=sse_payload,
                )

        # Get queues and decide action under the lock
        queues_copy = None

        with self._lock:
            queues = self._connections.get(task_id)

            if not queues:
                # Check if this task has ever had a connection
                has_had_connection = task_id in self._tasks_with_prior_connection

                # Only drop events for background tasks that have HAD a connection before
                # If no connection has ever been made, we must buffer so the first client gets the events
                if is_background_task and has_had_connection:
                    # For background tasks where client disconnected, drop events to prevent buffer overflow
                    # Events are already persisted to database, so we don't need in-memory buffer
                    log.debug(
                        "%s No active SSE connections for background task %s (had prior connection). "
                        "Events persisted to database for replay.",
                        self.log_identifier,
                        task_id,
                    )
                else:
                    log.debug(
                        "%s No active SSE connections for Task ID: %s. Buffering event.",
                        self.log_identifier,
                        task_id,
                    )
                    self._event_buffer.buffer_event(task_id, sse_payload)
                return
            else:
                # Make a copy of queues to iterate outside the lock
                queues_copy = list(queues)

        # Log the payload outside the lock
        if trace_logger.isEnabledFor(logging.DEBUG):
            trace_logger.debug(
                "%s Prepared SSE payload for Task ID %s: %s",
                self.log_identifier,
                task_id,
                sse_payload,
            )
        else:
            log.debug(
                "%s Prepared SSE payload for Task ID %s",
                self.log_identifier,
                task_id,
            )

        # Send to queues outside the lock (async operations)
        queues_to_remove = []
        for connection_queue in queues_copy:
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

        # Remove broken queues under the lock
        if queues_to_remove:
            with self._lock:
                if task_id in self._connections:
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

    async def drain_buffer_for_background_task(self, task_id: str):
        """
        Drains the event buffer for a background task when a client disconnects.
        This prevents buffer overflow warnings when background tasks continue
        generating events with no active consumers.
        
        Args:
            task_id: The ID of the background task
        """
        log.info(
            "%s Draining event buffer for background task: %s",
            self.log_identifier,
            task_id,
        )
        
        # Remove any buffered events to prevent overflow
        buffered_events = self._event_buffer.get_and_remove_buffer(task_id)
        if buffered_events:
            log.info(
                "%s Drained %d buffered events for background task: %s",
                self.log_identifier,
                len(buffered_events),
                task_id,
            )
        else:
            log.debug(
                "%s No buffered events to drain for background task: %s",
                self.log_identifier,
                task_id,
            )

    async def close_all_for_task(self, task_id: str):
        """
        Closes all SSE connections associated with a specific task.
        If a connection existed, it also cleans up the event buffer.
        If no connection ever existed, the buffer is left for a late-connecting client.
        """
        queues_to_close = None
        should_remove_buffer = False

        with self._lock:
            if task_id in self._connections:
                # This is the "normal" case: a client is or was connected.
                # It's safe to clean up everything.
                queues_to_close = self._connections.pop(task_id)
                should_remove_buffer = True
                log.debug(
                    "%s Closing %d SSE connections for Task ID: %s and cleaning up buffer.",
                    self.log_identifier,
                    len(queues_to_close),
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

        # Close queues outside the lock (async operations)
        if queues_to_close:
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
            # This is safe to do without lock since we already removed the task from _connections
            if should_remove_buffer:
                self._event_buffer.remove_buffer(task_id)

                # Clean up the connection tracking
                with self._lock:
                    self._tasks_with_prior_connection.discard(task_id)

                log.debug(
                    "%s Removed Task ID entry: %s and signaled queues to close.",
                    self.log_identifier,
                    task_id,
                )

    def cleanup_old_locks(self):
        """Legacy method - no longer needed with single threading lock.
        Kept for API compatibility but does nothing."""
        pass

    async def close_all(self):
        """Closes all active SSE connections managed by this instance."""
        self.cleanup_old_locks()

        # Collect all queues to close under the lock
        all_queues_to_close = []
        all_task_ids = []

        with self._lock:
            log.debug("%s Closing all active SSE connections...", self.log_identifier)
            all_task_ids = list(self._connections.keys())
            for task_id in all_task_ids:
                if task_id in self._connections:
                    queues = self._connections.pop(task_id)
                    all_queues_to_close.extend(queues)
            self._connections.clear()
            self._tasks_with_prior_connection.clear()

        # Close queues outside the lock (async operations)
        closed_count = len(all_queues_to_close)
        for q in all_queues_to_close:
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
