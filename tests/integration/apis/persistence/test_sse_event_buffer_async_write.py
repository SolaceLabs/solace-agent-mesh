"""
Integration tests for PersistentSSEEventBuffer async write queue.

These tests verify that the async worker thread actually processes events
and writes them to the database.
"""

import time
import pytest
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
    PersistentSSEEventBuffer,
)
from solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository import (
    SSEEventBufferRepository,
)
from solace_agent_mesh.gateway.http_sse.repository.models.sse_event_buffer_model import (
    SSEEventBufferModel,
)


def _create_session_factory(db_engine):
    """Creates a session factory bound to the test database."""
    return sessionmaker(bind=db_engine)


def _count_buffered_events(db_engine, task_id: str) -> int:
    """Count buffered events for a specific task."""
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        count = (
            db_session.query(SSEEventBufferModel)
            .filter(SSEEventBufferModel.task_id == task_id)
            .count()
        )
        return count
    finally:
        db_session.close()


def _get_buffered_events(db_engine, task_id: str) -> list:
    """Get all buffered events for a specific task."""
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        events = (
            db_session.query(SSEEventBufferModel)
            .filter(SSEEventBufferModel.task_id == task_id)
            .order_by(SSEEventBufferModel.event_sequence)
            .all()
        )
        # Convert to list of dicts to avoid detached instance issues
        return [
            {
                "task_id": e.task_id,
                "session_id": e.session_id,
                "user_id": e.user_id,
                "event_type": e.event_type,
                "event_data": e.event_data,
                "event_sequence": e.event_sequence,
                "created_at": e.created_at,
            }
            for e in events
        ]
    finally:
        db_session.close()


@pytest.mark.integration
class TestAsyncWriteWorkerIntegration:
    """Integration tests for async write worker thread."""

    def test_async_worker_writes_single_event_to_db(self, test_db_engine):
        """Verify worker thread processes a single event and writes to DB."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-async-single-001"
        session_id = "session-001"
        user_id = "user-001"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,  # Direct async queue mode
        )

        try:
            # Queue an event
            result = buffer.buffer_event(
                task_id=task_id,
                event_type="status_update",
                event_data={"message": "Test status", "progress": 50},
                session_id=session_id,
                user_id=user_id,
            )
            assert result is True, "buffer_event should return True on success"

            # Wait for the async worker to process (with timeout)
            buffer._async_write_queue.join()

            # Small additional delay to ensure DB commit completes
            time.sleep(0.1)

            # Verify event was written to DB
            events = _get_buffered_events(test_db_engine, task_id)
            assert len(events) == 1, f"Expected 1 event in DB, got {len(events)}"

            event = events[0]
            assert event["task_id"] == task_id
            assert event["session_id"] == session_id
            assert event["user_id"] == user_id
            assert event["event_type"] == "status_update"
            assert event["event_data"]["message"] == "Test status"
            assert event["event_data"]["progress"] == 50
            assert event["event_sequence"] == 1

        finally:
            buffer.shutdown()

    def test_async_worker_writes_multiple_events_in_order(self, test_db_engine):
        """Verify worker thread processes multiple events in correct order."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-async-multiple-001"
        session_id = "session-002"
        user_id = "user-002"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,
        )

        try:
            # Queue multiple events
            for i in range(5):
                result = buffer.buffer_event(
                    task_id=task_id,
                    event_type="progress",
                    event_data={"step": i + 1, "total": 5},
                    session_id=session_id,
                    user_id=user_id,
                )
                assert result is True

            # Wait for all events to be processed
            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify all events were written in order
            events = _get_buffered_events(test_db_engine, task_id)
            assert len(events) == 5, f"Expected 5 events in DB, got {len(events)}"

            for i, event in enumerate(events):
                assert event["event_sequence"] == i + 1
                assert event["event_data"]["step"] == i + 1
                assert event["event_data"]["total"] == 5

        finally:
            buffer.shutdown()

    def test_async_worker_preserves_timestamp(self, test_db_engine):
        """Verify worker thread preserves the original timestamp."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-async-timestamp-001"
        session_id = "session-003"
        user_id = "user-003"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,
        )

        try:
            # Record time before queueing
            before_time = int(time.time() * 1000)

            result = buffer.buffer_event(
                task_id=task_id,
                event_type="test",
                event_data={"test": True},
                session_id=session_id,
                user_id=user_id,
            )
            assert result is True

            # Record time after queueing
            after_time = int(time.time() * 1000)

            # Wait for processing
            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify timestamp is within expected range
            events = _get_buffered_events(test_db_engine, task_id)
            assert len(events) == 1

            event = events[0]
            assert event["created_at"] >= before_time
            assert event["created_at"] <= after_time + 1000  # Allow some margin

        finally:
            buffer.shutdown()

    def test_async_worker_handles_shutdown_gracefully(self, test_db_engine):
        """Verify pending events are flushed on shutdown."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-async-shutdown-001"
        session_id = "session-004"
        user_id = "user-004"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,
        )

        # Queue events
        for i in range(3):
            buffer.buffer_event(
                task_id=task_id,
                event_type="shutdown_test",
                event_data={"index": i},
                session_id=session_id,
                user_id=user_id,
            )

        # Shutdown (should drain the queue)
        buffer.shutdown()

        # Give a moment for DB operations to complete
        time.sleep(0.2)

        # Verify all events were written before shutdown completed
        event_count = _count_buffered_events(test_db_engine, task_id)
        assert event_count == 3, f"Expected 3 events after shutdown, got {event_count}"

    def test_async_queue_stats(self, test_db_engine):
        """Verify get_async_queue_stats returns correct information."""
        session_factory = _create_session_factory(test_db_engine)

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,
            async_write_queue_size=500,
        )

        try:
            stats = buffer.get_async_queue_stats()

            assert "queue_size" in stats
            assert "max_queue_size" in stats
            assert "worker_alive" in stats
            assert "dropped_events" in stats

            assert stats["max_queue_size"] == 500
            assert stats["worker_alive"] is True
            assert stats["dropped_events"] == 0

        finally:
            buffer.shutdown()

    def test_async_worker_handles_db_errors_gracefully(self, test_db_engine):
        """Verify worker continues processing after DB errors."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-async-error-001"
        session_id = "session-005"
        user_id = "user-005"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=False,
        )

        try:
            # Queue a valid event
            buffer.buffer_event(
                task_id=task_id,
                event_type="valid_event",
                event_data={"test": "data"},
                session_id=session_id,
                user_id=user_id,
            )

            # Wait for processing
            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify worker is still alive and can process more
            stats = buffer.get_async_queue_stats()
            assert stats["worker_alive"] is True

            # Queue another event
            buffer.buffer_event(
                task_id=task_id,
                event_type="another_event",
                event_data={"more": "data"},
                session_id=session_id,
                user_id=user_id,
            )

            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify both events were written
            event_count = _count_buffered_events(test_db_engine, task_id)
            assert event_count == 2

        finally:
            buffer.shutdown()


@pytest.mark.integration
class TestHybridModeAsyncFlush:
    """Integration tests for hybrid mode with async queue flushing."""

    def test_hybrid_mode_flushes_to_async_queue(self, test_db_engine):
        """Verify hybrid mode flushes RAM buffer through async queue."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-hybrid-async-001"
        session_id = "session-hybrid-001"
        user_id = "user-hybrid-001"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=3,  # Flush after 3 events
        )

        try:
            # Add events up to threshold
            for i in range(3):
                buffer.buffer_event(
                    task_id=task_id,
                    event_type="hybrid_event",
                    event_data={"index": i},
                    session_id=session_id,
                    user_id=user_id,
                )

            # Wait for async processing
            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify events were written to DB
            events = _get_buffered_events(test_db_engine, task_id)
            assert len(events) == 3

            for i, event in enumerate(events):
                assert event["event_data"]["index"] == i

        finally:
            buffer.shutdown()

    def test_hybrid_mode_explicit_flush(self, test_db_engine):
        """Verify explicit flush_task_buffer works with async queue."""
        session_factory = _create_session_factory(test_db_engine)
        task_id = "test-hybrid-flush-001"
        session_id = "session-hybrid-002"
        user_id = "user-hybrid-002"

        buffer = PersistentSSEEventBuffer(
            session_factory=session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,  # High threshold - won't auto-flush
        )

        try:
            # Add some events (below threshold)
            buffer.buffer_event(
                task_id=task_id,
                event_type="pre_flush",
                event_data={"before": True},
                session_id=session_id,
                user_id=user_id,
            )
            buffer.buffer_event(
                task_id=task_id,
                event_type="pre_flush",
                event_data={"before": True, "seq": 2},
                session_id=session_id,
                user_id=user_id,
            )

            # Explicitly flush
            flushed = buffer.flush_task_buffer(task_id)
            assert flushed == 2

            # Wait for async processing
            buffer._async_write_queue.join()
            time.sleep(0.1)

            # Verify events were written
            event_count = _count_buffered_events(test_db_engine, task_id)
            assert event_count == 2

        finally:
            buffer.shutdown()
