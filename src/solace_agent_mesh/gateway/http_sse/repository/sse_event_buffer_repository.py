"""
Repository for SSE Event Buffer operations.

This repository handles persistence of SSE events for background tasks
that need to be replayed when the user returns to the session.
"""

import logging
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .models.sse_event_buffer_model import SSEEventBufferModel
from .models.task_model import TaskModel
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)

# Maximum retry attempts for sequence number race condition
MAX_SEQUENCE_RETRIES = 3


class SSEEventBufferRepository:
    """Repository for SSE event buffer database operations."""

    def __init__(self):
        self.log_identifier = "[SSEEventBufferRepository]"

    def buffer_event(
        self,
        db: DBSession,
        task_id: str,
        session_id: str,
        user_id: str,
        event_type: str,
        event_data: dict,
        created_time: int | None = None,
    ) -> SSEEventBufferModel:
        """
        Buffer an SSE event for later replay.
        
        Uses retry logic to handle rare race conditions where concurrent writes
        could result in duplicate sequence numbers. The unique constraint on
        (task_id, event_sequence) ensures data integrity.
        
        Note: In practice, this race condition is extremely unlikely because:
        1. Events for each task flow through a single-threaded message processor
        2. Each task has its own event stream arriving sequentially
        
        The retry logic is a defensive measure for edge cases like hybrid mode
        RAM buffer flush coinciding with a new event, or multi-worker deployments.
        
        Args:
            db: Database session
            task_id: The task ID this event belongs to
            session_id: The session ID
            user_id: The user ID
            event_type: The SSE event type (e.g., 'message')
            event_data: The event data payload
            created_time: Optional timestamp for when the event was originally created
                         (used by hybrid mode when flushing RAM buffer)
            
        Returns:
            The created SSEEventBufferModel instance
            
        Raises:
            IntegrityError: If all retry attempts fail (should be extremely rare)
        """
        last_error = None
        
        for attempt in range(MAX_SEQUENCE_RETRIES):
            try:
                # Get next sequence number for this task
                max_seq = db.query(func.max(SSEEventBufferModel.event_sequence))\
                    .filter(SSEEventBufferModel.task_id == task_id)\
                    .scalar() or 0
                
                # Create buffer entry
                buffer_entry = SSEEventBufferModel(
                    task_id=task_id,
                    session_id=session_id,
                    user_id=user_id,
                    event_sequence=max_seq + 1,
                    event_type=event_type,
                    event_data=event_data,
                    created_at=created_time if created_time is not None else now_epoch_ms(),
                    consumed=False,
                )
                db.add(buffer_entry)
                
                # Mark task as having buffered events
                task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
                if task and not task.events_buffered:
                    task.events_buffered = True
                
                db.flush()  # Flush to get the ID and trigger constraint check
                
                log.debug(
                    "%s Buffered event for task %s: sequence=%d, type=%s",
                    self.log_identifier,
                    task_id,
                    buffer_entry.event_sequence,
                    event_type,
                )
                
                return buffer_entry
                
            except IntegrityError as e:
                # Rollback the failed transaction
                db.rollback()
                last_error = e
                
                # Check if this is a sequence number collision
                if "sse_event_buffer_task_seq_unique" in str(e) or "UNIQUE constraint" in str(e):
                    log.warning(
                        "%s Sequence number race condition detected for task %s (attempt %d/%d), retrying...",
                        self.log_identifier,
                        task_id,
                        attempt + 1,
                        MAX_SEQUENCE_RETRIES,
                    )
                    continue
                else:
                    # Some other integrity error, re-raise
                    raise
        
        # All retries failed - this should be extremely rare
        log.error(
            "%s Failed to buffer event after %d attempts for task %s: %s",
            self.log_identifier,
            MAX_SEQUENCE_RETRIES,
            task_id,
            last_error,
        )
        raise last_error

    def buffer_events_batch(
        self,
        db: DBSession,
        task_id: str,
        events: List[tuple],
    ) -> int:
        """
        Buffer multiple SSE events in a single batch insert.

        For PostgreSQL: Uses SELECT FOR UPDATE to prevent race conditions.
        For SQLite: Relies on database-level locking (SQLite serializes writes).
        
        Args:
            db: Database session
            task_id: The task ID these events belong to
            events: List of tuples (event_type, event_data, timestamp, session_id, user_id)
            
        Returns:
            Number of events inserted
        """
        if not events:
            return 0
        
        # Check if database supports row-level locking (PostgreSQL does, SQLite doesn't)
        dialect_name = db.bind.dialect.name if db.bind else "unknown"
        supports_row_locking = dialect_name in ("postgresql", "mysql", "oracle")
        
        # Get task with optional row lock for databases that support it
        task_query = db.query(TaskModel).filter(TaskModel.id == task_id)
        if supports_row_locking:
            task_query = task_query.with_for_update()
        task = task_query.first()
        
        # Get max sequence (safe due to row lock on PostgreSQL, or DB-level lock on SQLite)
        max_seq = db.query(func.max(SSEEventBufferModel.event_sequence))\
            .filter(SSEEventBufferModel.task_id == task_id)\
            .scalar() or 0
        
        # Build list of model instances with sequential sequence numbers
        buffer_entries = []
        for i, (event_type, event_data, timestamp, session_id, user_id) in enumerate(events):
            buffer_entries.append(SSEEventBufferModel(
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                event_sequence=max_seq + i + 1,
                event_type=event_type,
                event_data=event_data,
                created_at=timestamp,
                consumed=False,
            ))
        
        # Bulk insert all events
        db.bulk_save_objects(buffer_entries)
        
        # Mark task as having buffered events (task already fetched above)
        if task and not task.events_buffered:
            task.events_buffered = True
        
        db.flush()
        
        log.debug(
            "%s Batch buffered %d events for task %s (sequences %d-%d)",
            self.log_identifier,
            len(events),
            task_id,
            max_seq + 1,
            max_seq + len(events),
        )
        
        return len(events)

    def get_buffered_events(
        self,
        db: DBSession,
        task_id: str,
        mark_consumed: bool = True,
    ) -> List[dict]:
        """
        Get all buffered events for a task in sequence order.
        
        Args:
            db: Database session
            task_id: The task ID to get events for
            mark_consumed: Whether to mark events as consumed 
            
        Returns:
            List of event dictionaries with type, data, and sequence
        """
        query = db.query(SSEEventBufferModel)\
            .filter(SSEEventBufferModel.task_id == task_id)
        
        if mark_consumed:
            query = query.filter(SSEEventBufferModel.consumed.is_(False))
            query = query.with_for_update()
        
        events = query.order_by(SSEEventBufferModel.event_sequence).all()
        
        event_data = [
            {
                "type": event.event_type,
                "data": event.event_data,
                "sequence": event.event_sequence,
            }
            for event in events
        ]
        
        if mark_consumed and events:
            # Mark events as consumed
            consumed_at = now_epoch_ms()
            db.query(SSEEventBufferModel)\
                .filter(SSEEventBufferModel.task_id == task_id)\
                .update({
                    "consumed": True,
                    "consumed_at": consumed_at,
                })
            
            # Mark task as consumed
            task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
            if task:
                task.events_consumed = True
            
            log.info(
                "%s Marked %d events as consumed for task %s",
                self.log_identifier,
                len(events),
                task_id,
            )
        
        return event_data

    def get_unconsumed_events_for_session(
        self,
        db: DBSession,
        session_id: str,
        task_id: Optional[str] = None,
        mark_consumed: bool = False,
    ) -> List[SSEEventBufferModel]:
        """
        Get unconsumed events for a session, optionally filtered by task.
        
        Args:
            db: Database session
            session_id: The session ID
            task_id: Optional task ID to filter by
            mark_consumed: Whether to mark events as consumed
            
        Returns:
            List of SSEEventBufferModel instances
        """
        query = db.query(SSEEventBufferModel)\
            .filter(SSEEventBufferModel.session_id == session_id)\
            .filter(SSEEventBufferModel.consumed.is_(False))
        
        if task_id:
            query = query.filter(SSEEventBufferModel.task_id == task_id)
        
        events = query.order_by(SSEEventBufferModel.event_sequence).all()
        
        if mark_consumed and events:
            # Mark events as consumed
            consumed_at = now_epoch_ms()
            for event in events:
                event.consumed = True
                event.consumed_at = consumed_at
            
            log.info(
                "%s Marked %d events as consumed for session %s (task=%s)",
                self.log_identifier,
                len(events),
                session_id,
                task_id,
            )
        
        return events

    def has_unconsumed_events(
        self,
        db: DBSession,
        task_id: str,
    ) -> bool:
        """
        Check if a task has unconsumed buffered events.
        
        Args:
            db: Database session
            task_id: The task ID to check
            
        Returns:
            True if there are unconsumed events, False otherwise
        """
        count = db.query(func.count(SSEEventBufferModel.id))\
            .filter(SSEEventBufferModel.task_id == task_id)\
            .filter(SSEEventBufferModel.consumed.is_(False))\
            .scalar()
        
        return count > 0

    def get_event_count(
        self,
        db: DBSession,
        task_id: str,
    ) -> int:
        """
        Get the total number of buffered events for a task.
        
        Args:
            db: Database session
            task_id: The task ID
            
        Returns:
            Number of buffered events
        """
        return db.query(func.count(SSEEventBufferModel.id))\
            .filter(SSEEventBufferModel.task_id == task_id)\
            .scalar() or 0

    def cleanup_consumed_events(
        self,
        db: DBSession,
        older_than_ms: int,
    ) -> int:
        """
        Clean up consumed events older than the specified time.
        
        Args:
            db: Database session
            older_than_ms: Delete events consumed before this epoch time (ms)
            
        Returns:
            Number of events deleted
        """
        deleted = db.query(SSEEventBufferModel)\
            .filter(SSEEventBufferModel.consumed.is_(True))\
            .filter(SSEEventBufferModel.consumed_at < older_than_ms)\
            .delete()
        
        if deleted > 0:
            log.info(
                "%s Cleaned up %d consumed events older than %d",
                self.log_identifier,
                deleted,
                older_than_ms,
            )
        
        return deleted

    def delete_events_for_task(
        self,
        db: DBSession,
        task_id: str,
    ) -> int:
        """
        Delete all buffered events for a task.
        
        Args:
            db: Database session
            task_id: The task ID
            
        Returns:
            Number of events deleted
        """
        deleted = db.query(SSEEventBufferModel)\
            .filter(SSEEventBufferModel.task_id == task_id)\
            .delete()
        
        if deleted > 0:
            log.debug(
                "%s Deleted %d events for task %s",
                self.log_identifier,
                deleted,
                task_id,
            )
        
        return deleted

    def cleanup_old_events(
        self,
        db: DBSession,
        older_than_ms: int,
        batch_size: int = 1000,
    ) -> int:
        """
        Clean up ALL events (both consumed and unconsumed) older than the specified time.
        
        This is necessary because unconsumed events can accumulate indefinitely if users
        don't return to their sessions to replay them. The chat_tasks table serves as a
        fallback for displaying old chat history.
        
        Args:
            db: Database session
            older_than_ms: Delete events created before this epoch time (ms)
            batch_size: Number of events to delete per batch
            
        Returns:
            Total number of events deleted
        """
        total_deleted = 0
        
        while True:
            # Delete in batches to avoid long-running transactions
            # Get IDs of events to delete
            events_to_delete = db.query(SSEEventBufferModel.id)\
                .filter(SSEEventBufferModel.created_at < older_than_ms)\
                .limit(batch_size)\
                .all()
            
            if not events_to_delete:
                break
            
            event_ids = [e.id for e in events_to_delete]
            deleted = db.query(SSEEventBufferModel)\
                .filter(SSEEventBufferModel.id.in_(event_ids))\
                .delete(synchronize_session=False)
            
            db.commit()
            total_deleted += deleted
            
            log.debug(
                "%s Deleted batch of %d old SSE events (total so far: %d)",
                self.log_identifier,
                deleted,
                total_deleted,
            )
        
        if total_deleted > 0:
            log.info(
                "%s Cleaned up %d SSE events older than %d ms",
                self.log_identifier,
                total_deleted,
                older_than_ms,
            )
        
        return total_deleted
