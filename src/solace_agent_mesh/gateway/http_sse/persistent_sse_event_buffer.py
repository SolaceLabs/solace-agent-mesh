"""
A database-backed buffer for holding SSE events for background tasks.

This buffer persists events to the database so they survive server restarts
and can be replayed when the user returns to the session. It works alongside
the in-memory SSEEventBuffer - the in-memory buffer handles short-term buffering
for race conditions, while this persistent buffer handles long-term storage
for background tasks.

HYBRID MODE:
When hybrid_mode_enabled=True, events are first buffered in RAM and only
flushed to the database when:
1. The RAM buffer reaches the flush threshold (default: 10 events)
2. The SSE connection is closed (client disconnects)
3. The task completes
4. Explicit flush is requested

This reduces database write pressure for short-lived tasks while maintaining
durability for longer-running background tasks.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class PersistentSSEEventBuffer:
    """
    Database-backed buffer for SSE events.
    
    This buffer stores events in the database for background tasks that need
    to be replayed when the user returns. It's designed to work with the
    SSEManager to provide persistent event storage.
    
    HYBRID MODE :
    When enabled, events are buffered in RAM first and batched to DB to reduce
    database write pressure. This is off by default for safety but can be
    enabled via config for performance optimization.
    """

    def __init__(
        self,
        session_factory: Optional[Callable] = None,
        enabled: bool = True,
        hybrid_mode_enabled: bool = False,
        hybrid_flush_threshold: int = 10,
    ):
        """
        Initialize the persistent event buffer.
        
        Args:
            session_factory: Factory function to create database sessions
            enabled: Whether persistent buffering is enabled
            hybrid_mode_enabled: Whether to use RAM-first buffering (default: False)
            hybrid_flush_threshold: Number of events before flushing RAM to DB (default: 10)
        """
        self._session_factory = session_factory
        self._enabled = enabled
        self._lock = threading.Lock()
        self.log_identifier = "[PersistentSSEEventBuffer]"
        
        # Hybrid mode configuration
        self._hybrid_mode_enabled = hybrid_mode_enabled
        self._hybrid_flush_threshold = hybrid_flush_threshold
        
        # Cache for task metadata to avoid repeated DB queries
        self._task_metadata_cache: Dict[str, Dict[str, str]] = {}
        
        # RAM buffer for hybrid mode: task_id -> list of (event_type, event_data, timestamp)
        self._ram_buffer: Dict[str, List[Tuple[str, Dict[str, Any], int]]] = {}
        
        log.info(
            "%s Initialized (enabled=%s, has_session_factory=%s, hybrid_mode=%s, flush_threshold=%d)",
            self.log_identifier,
            self._enabled,
            self._session_factory is not None,
            self._hybrid_mode_enabled,
            self._hybrid_flush_threshold,
        )

    def is_enabled(self) -> bool:
        """Check if persistent buffering is enabled and configured."""
        return self._enabled and self._session_factory is not None

    def is_hybrid_mode_enabled(self) -> bool:
        """Check if hybrid RAM+DB buffering mode is enabled."""
        return self._hybrid_mode_enabled and self.is_enabled()

    def set_task_metadata(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Store task metadata for later use when buffering events.
        
        This stores metadata in memory (for fast access). Cross-process access
        is handled via get_task_metadata which falls back to database lookup.
        
        Args:
            task_id: The task ID
            session_id: The session ID
            user_id: The user ID
        """
        # Store in memory cache only - don't write to DB to avoid conflicts
        with self._lock:
            self._task_metadata_cache[task_id] = {
                "session_id": session_id,
                "user_id": user_id,
            }
        
        log.debug(
            "%s Cached metadata for task %s: session=%s, user=%s",
            self.log_identifier,
            task_id,
            session_id,
            user_id,
        )

    def get_task_metadata(self, task_id: str) -> Optional[Dict[str, str]]:
        """
        Get task metadata from cache or database.
        
        First checks the in-memory cache, then falls back to database lookup.
        This ensures metadata is available even across process boundaries.
        
        Args:
            task_id: The task ID
            
        Returns:
            Dictionary with session_id and user_id, or None if not found
        """
        # Check in-memory cache first
        with self._lock:
            cached = self._task_metadata_cache.get(task_id)
            if cached:
                return cached
        
        # Fall back to database lookup
        if self._session_factory:
            try:
                from .repository.task_repository import TaskRepository
                
                db = self._session_factory()
                try:
                    repo = TaskRepository()
                    task = repo.find_by_id(db, task_id)
                    if task and task.session_id and task.user_id:
                        metadata = {
                            "session_id": task.session_id,
                            "user_id": task.user_id,
                        }
                        # Cache it for future lookups
                        with self._lock:
                            self._task_metadata_cache[task_id] = metadata
                        log.debug(
                            "%s Retrieved task metadata from database for %s: session=%s, user=%s",
                            self.log_identifier,
                            task_id,
                            task.session_id,
                            task.user_id,
                        )
                        return metadata
                finally:
                    db.close()
            except Exception as e:
                log.debug(
                    "%s Failed to get task metadata from database: %s",
                    self.log_identifier,
                    e,
                )
        
        return None

    def clear_task_metadata(self, task_id: str) -> None:
        """
        Clear cached task metadata.
        
        Args:
            task_id: The task ID
        """
        with self._lock:
            self._task_metadata_cache.pop(task_id, None)

    def buffer_event(
        self,
        task_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Buffer an SSE event.
        
        In normal mode: writes directly to database.
        In hybrid mode: buffers to RAM first, flushes to DB when threshold reached.
        
        Args:
            task_id: The task ID this event belongs to
            event_type: The SSE event type (e.g., 'message')
            event_data: The event data payload (already serialized)
            session_id: The session ID (optional, will use cached if not provided)
            user_id: The user ID (optional, will use cached if not provided)
            
        Returns:
            True if the event was buffered, False otherwise
        """
        if not self.is_enabled():
            return False
        
        # Get metadata from cache if not provided
        if not session_id or not user_id:
            metadata = self.get_task_metadata(task_id)
            if metadata:
                session_id = session_id or metadata.get("session_id")
                user_id = user_id or metadata.get("user_id")
        
        if not session_id or not user_id:
            log.warning(
                "%s Cannot buffer event for task %s: missing session_id or user_id",
                self.log_identifier,
                task_id,
            )
            return False
        
        # HYBRID MODE: Buffer to RAM first, flush to DB on threshold
        if self.is_hybrid_mode_enabled():
            return self._buffer_event_hybrid(task_id, event_type, event_data, session_id, user_id)
        
        # NORMAL MODE: Write directly to database
        return self._buffer_event_to_db(task_id, event_type, event_data, session_id, user_id)
    
    def _buffer_event_hybrid(
        self,
        task_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
    ) -> bool:
        """
        Buffer event to RAM, flush to DB when threshold reached.
        
        Args:
            task_id: The task ID
            event_type: The SSE event type
            event_data: The event payload
            session_id: The session ID
            user_id: The user ID
            
        Returns:
            True if buffered successfully
        """
        timestamp = int(time.time() * 1000)  # milliseconds
        should_flush = False
        
        with self._lock:
            # Add to RAM buffer
            if task_id not in self._ram_buffer:
                self._ram_buffer[task_id] = []
            
            self._ram_buffer[task_id].append((event_type, event_data, timestamp, session_id, user_id))
            
            buffer_size = len(self._ram_buffer[task_id])
            
            # Check if we should flush
            if buffer_size >= self._hybrid_flush_threshold:
                should_flush = True
                log.info(
                    "%s [Hybrid] RAM buffer for task %s reached threshold (%d >= %d), will flush to DB",
                    self.log_identifier,
                    task_id,
                    buffer_size,
                    self._hybrid_flush_threshold,
                )
        
        # Flush outside the lock to avoid holding it during DB operations
        if should_flush:
            self.flush_task_buffer(task_id)
        
        log.info(
            "%s [Hybrid] Buffered event to RAM for task %s (type=%s, ram_buffer_size=%d)",
            self.log_identifier,
            task_id,
            event_type,
            buffer_size if not should_flush else 0,  # After flush, buffer is empty
        )
        
        return True
    
    def _buffer_event_to_db(
        self,
        task_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
    ) -> bool:
        """
        Buffer event directly to database (normal mode).
        
        Args:
            task_id: The task ID
            event_type: The SSE event type
            event_data: The event payload
            session_id: The session ID
            user_id: The user ID
            
        Returns:
            True if buffered successfully
        """
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                repo.buffer_event(
                    db=db,
                    task_id=task_id,
                    session_id=session_id,
                    user_id=user_id,
                    event_type=event_type,
                    event_data=event_data,
                )
                
                # Note: We don't update the tasks table here because:
                # 1. The task record may not exist yet (it's created by task_logger_service)
                # 2. We can determine if events exist by querying sse_event_buffer directly
                
                db.commit()
                
                log.debug(
                    "%s Buffered event for task %s (type=%s)",
                    self.log_identifier,
                    task_id,
                    event_type,
                )
                return True
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to buffer event for task %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return False
    
    def flush_task_buffer(self, task_id: str) -> int:
        """
        Flush RAM buffer for a specific task to database.
        
        This is called:
        1. When RAM buffer reaches threshold
        2. When SSE connection is closed
        3. When task completes
        
        Args:
            task_id: The task ID to flush
            
        Returns:
            Number of events flushed
        """
        if not self.is_hybrid_mode_enabled():
            return 0
        
        # Extract events from RAM buffer under lock
        events_to_flush = []
        with self._lock:
            events_to_flush = self._ram_buffer.pop(task_id, [])
        
        if not events_to_flush:
            return 0
        
        # Flush to database outside the lock
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                
                for event_type, event_data, timestamp, session_id, user_id in events_to_flush:
                    repo.buffer_event(
                        db=db,
                        task_id=task_id,
                        session_id=session_id,
                        user_id=user_id,
                        event_type=event_type,
                        event_data=event_data,
                        created_time=timestamp,
                    )
                
                db.commit()
                
                log.info(
                    "%s [Hybrid] Flushed %d events for task %s from RAM to DB",
                    self.log_identifier,
                    len(events_to_flush),
                    task_id,
                )
                
                return len(events_to_flush)
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s [Hybrid] Failed to flush events for task %s: %s. Events lost: %d",
                self.log_identifier,
                task_id,
                e,
                len(events_to_flush),
            )
            # Re-add events to buffer on failure for retry
            with self._lock:
                if task_id not in self._ram_buffer:
                    self._ram_buffer[task_id] = []
                # Prepend the failed events (they came first)
                self._ram_buffer[task_id] = events_to_flush + self._ram_buffer[task_id]
            return 0
    
    def flush_all_buffers(self) -> int:
        """
        Flush all RAM buffers to database.
        
        This is called during shutdown to ensure no events are lost.
        
        Returns:
            Total number of events flushed
        """
        if not self.is_hybrid_mode_enabled():
            return 0
        
        # Get all task IDs with buffered events
        with self._lock:
            task_ids = list(self._ram_buffer.keys())
        
        total_flushed = 0
        for task_id in task_ids:
            total_flushed += self.flush_task_buffer(task_id)
        
        if total_flushed > 0:
            log.info(
                "%s [Hybrid] Flushed all buffers: %d total events",
                self.log_identifier,
                total_flushed,
            )
        
        return total_flushed
    
    def get_ram_buffer_size(self, task_id: str) -> int:
        """
        Get the number of events in RAM buffer for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            Number of events in RAM buffer
        """
        with self._lock:
            return len(self._ram_buffer.get(task_id, []))

    def get_buffered_events(
        self,
        task_id: str,
        mark_consumed: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all buffered events for a task.
        
        In hybrid mode: first flushes RAM buffer to DB, then retrieves from DB.
        This ensures all events are returned in correct order.
        
        Args:
            task_id: The task ID
            mark_consumed: Whether to mark events as consumed
            
        Returns:
            List of event dictionaries
        """
        if not self.is_enabled():
            return []
        
        # In hybrid mode, flush RAM buffer first to ensure all events are in DB
        if self.is_hybrid_mode_enabled():
            self.flush_task_buffer(task_id)
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                events = repo.get_buffered_events(
                    db=db,
                    task_id=task_id,
                    mark_consumed=mark_consumed,
                )
                if mark_consumed:
                    db.commit()
                
                log.info(
                    "%s Retrieved %d buffered events for task %s (mark_consumed=%s)",
                    self.log_identifier,
                    len(events),
                    task_id,
                    mark_consumed,
                )
                return events
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to get buffered events for task %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return []

    def has_unconsumed_events(self, task_id: str) -> bool:
        """
        Check if a task has unconsumed buffered events.
        
        In hybrid mode, also checks RAM buffer.
        
        Args:
            task_id: The task ID
            
        Returns:
            True if there are unconsumed events
        """
        if not self.is_enabled():
            return False
        
        # In hybrid mode, check RAM buffer first
        if self.is_hybrid_mode_enabled():
            with self._lock:
                if self._ram_buffer.get(task_id):
                    return True
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                return repo.has_unconsumed_events(db, task_id)
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to check unconsumed events for task %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return False

    def get_unconsumed_events_for_session(
        self,
        session_id: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all unconsumed events for a session, grouped by task.
        
        Args:
            session_id: The session ID
            
        Returns:
            Dictionary mapping task_id to list of events
        """
        if not self.is_enabled():
            return {}
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                return repo.get_unconsumed_events_for_session(db, session_id)
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to get unconsumed events for session %s: %s",
                self.log_identifier,
                session_id,
                e,
            )
            return {}

    def delete_events_for_task(self, task_id: str) -> int:
        """
        Delete all buffered events for a task.
        
        In hybrid mode, also clears RAM buffer.
        
        Args:
            task_id: The task ID
            
        Returns:
            Number of events deleted
        """
        log.info(
            "%s [BufferCleanup] delete_events_for_task called for task_id=%s, is_enabled=%s, hybrid_mode=%s",
            self.log_identifier,
            task_id,
            self.is_enabled(),
            self.is_hybrid_mode_enabled(),
        )
        if not self.is_enabled():
            log.info("%s [BufferCleanup] Buffer not enabled, returning 0", self.log_identifier)
            return 0
        
        # In hybrid mode, clear RAM buffer first (discard without flushing to DB)
        ram_cleared = 0
        if self.is_hybrid_mode_enabled():
            with self._lock:
                events = self._ram_buffer.pop(task_id, [])
                ram_cleared = len(events)
                if ram_cleared > 0:
                    log.info(
                        "%s [BufferCleanup] Cleared %d events from RAM buffer for task %s (discarded, not flushed)",
                        self.log_identifier,
                        ram_cleared,
                        task_id,
                    )
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                deleted = repo.delete_events_for_task(db, task_id)
                db.commit()
                
                log.debug(
                    "%s [BufferCleanup] Deleted %d events for task %s from database (+ %d from RAM)",
                    self.log_identifier,
                    deleted,
                    task_id,
                    ram_cleared,
                )
                
                # Clear cached metadata
                self.clear_task_metadata(task_id)
                
                return deleted + ram_cleared
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to delete events for task %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return ram_cleared  # Still return RAM cleared count

    def cleanup_old_events(self, days: int = 7) -> int:
        """
        Clean up consumed events older than the specified number of days.
        
        Args:
            days: Number of days to keep consumed events
            
        Returns:
            Number of events deleted
        """
        if not self.is_enabled():
            return 0
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
            
            # Calculate cutoff time
            cutoff_ms = now_epoch_ms() - (days * 24 * 60 * 60 * 1000)
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                deleted = repo.cleanup_consumed_events(db, cutoff_ms)
                db.commit()
                
                if deleted > 0:
                    log.info(
                        "%s Cleaned up %d consumed events older than %d days",
                        self.log_identifier,
                        deleted,
                        days,
                    )
                
                return deleted
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to cleanup old events: %s",
                self.log_identifier,
                e,
            )
            return 0
