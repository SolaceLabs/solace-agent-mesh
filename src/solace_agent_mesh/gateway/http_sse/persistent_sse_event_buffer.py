"""
A database-backed buffer for holding SSE events for background tasks.

This buffer persists events to the database so they survive server restarts
and can be replayed when the user returns to the session. It works alongside
the in-memory SSEEventBuffer - the in-memory buffer handles short-term buffering
for race conditions, while this persistent buffer handles long-term storage
for background tasks.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class PersistentSSEEventBuffer:
    """
    Database-backed buffer for SSE events.
    
    This buffer stores events in the database for background tasks that need
    to be replayed when the user returns. It's designed to work with the
    SSEManager to provide persistent event storage.
    """

    def __init__(
        self,
        session_factory: Optional[Callable] = None,
        enabled: bool = True,
    ):
        """
        Initialize the persistent event buffer.
        
        Args:
            session_factory: Factory function to create database sessions
            enabled: Whether persistent buffering is enabled
        """
        self._session_factory = session_factory
        self._enabled = enabled
        self._lock = threading.Lock()
        self.log_identifier = "[PersistentSSEEventBuffer]"
        
        # Cache for task metadata to avoid repeated DB queries
        self._task_metadata_cache: Dict[str, Dict[str, str]] = {}
        
        log.info(
            "%s Initialized (enabled=%s, has_session_factory=%s)",
            self.log_identifier,
            self._enabled,
            self._session_factory is not None,
        )

    def is_enabled(self) -> bool:
        """Check if persistent buffering is enabled and configured."""
        return self._enabled and self._session_factory is not None

    def set_task_metadata(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Cache task metadata for later use when buffering events.
        
        This should be called when a task is created so we have the
        session_id and user_id available when buffering events.
        
        Args:
            task_id: The task ID
            session_id: The session ID
            user_id: The user ID
        """
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
        Get cached task metadata.
        
        Args:
            task_id: The task ID
            
        Returns:
            Dictionary with session_id and user_id, or None if not cached
        """
        with self._lock:
            return self._task_metadata_cache.get(task_id)

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
        Buffer an SSE event to the database.
        
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

    def get_buffered_events(
        self,
        task_id: str,
        mark_consumed: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all buffered events for a task.
        
        Args:
            task_id: The task ID
            mark_consumed: Whether to mark events as consumed
            
        Returns:
            List of event dictionaries
        """
        if not self.is_enabled():
            return []
        
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
        
        Args:
            task_id: The task ID
            
        Returns:
            True if there are unconsumed events
        """
        if not self.is_enabled():
            return False
        
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
        
        Args:
            task_id: The task ID
            
        Returns:
            Number of events deleted
        """
        if not self.is_enabled():
            return 0
        
        try:
            from .repository.sse_event_buffer_repository import SSEEventBufferRepository
            
            db = self._session_factory()
            try:
                repo = SSEEventBufferRepository()
                deleted = repo.delete_events_for_task(db, task_id)
                db.commit()
                
                # Clear cached metadata
                self.clear_task_metadata(task_id)
                
                return deleted
            finally:
                db.close()
        except Exception as e:
            log.error(
                "%s Failed to delete events for task %s: %s",
                self.log_identifier,
                task_id,
                e,
            )
            return 0

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
