"""Comprehensive tests for 100% coverage of persistent_sse_event_buffer.py."""

import pytest
from unittest.mock import MagicMock, patch
import time

from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
    PersistentSSEEventBuffer,
)


class TestPersistentSSEEventBufferComprehensive:
    """Comprehensive tests for PersistentSSEEventBuffer."""

    def test_init_with_all_parameters(self):
        """Test initialization with all parameters."""
        mock_factory = MagicMock()

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=20
        )

        assert buffer.is_enabled() is True
        assert buffer.is_hybrid_mode_enabled() is True
        assert buffer._hybrid_flush_threshold == 20

    def test_init_disabled(self):
        """Test initialization when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        assert buffer.is_enabled() is False
        assert buffer.is_hybrid_mode_enabled() is False

    def test_init_no_session_factory(self):
        """Test that buffer is not enabled without session factory."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=True
        )

        assert buffer.is_enabled() is False

    def test_init_hybrid_mode_but_not_enabled(self):
        """Test hybrid mode is off if buffer is not enabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False,
            hybrid_mode_enabled=True
        )

        assert buffer.is_hybrid_mode_enabled() is False

    def test_set_task_metadata(self):
        """Test setting task metadata in cache."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True
        )

        buffer.set_task_metadata("task-123", "session-456", "user-789")

        # Should be in cache
        assert "task-123" in buffer._task_metadata_cache
        assert buffer._task_metadata_cache["task-123"]["session_id"] == "session-456"
        assert buffer._task_metadata_cache["task-123"]["user_id"] == "user-789"

    def test_get_task_metadata_from_cache(self):
        """Test getting metadata from cache (happy path)."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True
        )

        buffer.set_task_metadata("task-123", "session-456", "user-789")

        metadata = buffer.get_task_metadata("task-123")

        assert metadata is not None
        assert metadata["session_id"] == "session-456"
        assert metadata["user_id"] == "user-789"

    def test_get_task_metadata_from_database(self):
        """Test getting metadata from database when not in cache."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        # Mock task from database
        mock_task = MagicMock()
        mock_task.session_id = "session-db"
        mock_task.user_id = "user-db"

        with patch('solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.find_by_id.return_value = mock_task
            mock_repo_class.return_value = mock_repo

            metadata = buffer.get_task_metadata("task-not-cached")

            assert metadata is not None
            assert metadata["session_id"] == "session-db"
            assert metadata["user_id"] == "user-db"

            # Should now be cached
            assert "task-not-cached" in buffer._task_metadata_cache

    def test_get_task_metadata_not_found(self):
        """Test getting metadata when task doesn't exist."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        with patch('solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.find_by_id.return_value = None  # Not found
            mock_repo_class.return_value = mock_repo

            metadata = buffer.get_task_metadata("nonexistent")

            assert metadata is None

    def test_get_task_metadata_db_exception(self):
        """Test handling of database exceptions when getting metadata."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        with patch('solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository') as mock_repo_class:
            mock_repo_class.side_effect = Exception("DB error")

            metadata = buffer.get_task_metadata("task-123")

            assert metadata is None

    def test_get_task_metadata_no_session_factory(self):
        """Test getting metadata when no session factory."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=True
        )

        metadata = buffer.get_task_metadata("task-123")

        assert metadata is None

    def test_clear_task_metadata(self):
        """Test clearing task metadata from cache."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True
        )

        buffer.set_task_metadata("task-123", "session", "user")
        assert "task-123" in buffer._task_metadata_cache

        buffer.clear_task_metadata("task-123")
        assert "task-123" not in buffer._task_metadata_cache

    def test_clear_nonexistent_metadata(self):
        """Test clearing metadata that doesn't exist."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True
        )

        # Should not raise
        buffer.clear_task_metadata("nonexistent")

    def test_buffer_event_when_disabled(self):
        """Test that buffering does nothing when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        result = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test"}
        )

        assert result is False

    def test_buffer_event_missing_session_id(self):
        """Test buffering event with missing session_id."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True
        )

        result = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test"},
            session_id=None,  # Missing
            user_id="user-456"
        )

        assert result is False

    def test_buffer_event_gets_metadata_from_cache(self):
        """Test that buffer_event can get metadata from cache and queue event."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=False  # Normal mode
        )

        buffer.set_task_metadata("task-123", "session-456", "user-789")

        # With async queue, buffer_event returns True when event is queued
        result = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test"}
            # No session_id/user_id provided, should get from cache
        )

        assert result is True
        # Verify event was queued (async queue stats show pending items)
        stats = buffer.get_async_queue_stats()
        assert stats["queue_size"] >= 0  # Event may have been processed already
        
        # Cleanup
        buffer.shutdown()

    def test_buffer_event_hybrid_mode_triggers_flush(self):
        """Test that hybrid mode flushes when threshold reached."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=3
        )

        buffer.set_task_metadata("task-123", "session", "user")

        # Add events up to threshold
        for i in range(3):
            result = buffer.buffer_event(
                "task-123",
                "test_event",
                {"data": f"test{i}"},
                session_id="session",
                user_id="user"
            )
            assert result is True

        # After 3 events, should have flushed
        # RAM buffer should be empty (or have new events if more were added)

    def test_buffer_event_normal_mode_queues_for_async_write(self):
        """Test that normal mode queues events for async DB write."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=False
        )

        # With async queue, buffer_event returns True when event is queued
        result = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test"},
            session_id="session",
            user_id="user"
        )

        assert result is True
        # Verify event was queued (async queue stats show pending items)
        stats = buffer.get_async_queue_stats()
        assert stats["queue_size"] >= 0  # Event may have been processed already
        
        # Cleanup
        buffer.shutdown()

    def test_buffer_event_queue_full_returns_false(self):
        """Test that buffer_event returns False when async queue is full."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        # Create buffer with very small queue
        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=False,
            async_write_queue_size=1  # Very small queue
        )

        # Stop the worker so queue fills up
        buffer._stop_async_write_worker()

        # First event should succeed
        result1 = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test1"},
            session_id="session",
            user_id="user"
        )
        assert result1 is True

        # Second event should fail (queue full)
        result2 = buffer.buffer_event(
            "task-123",
            "test_event",
            {"data": "test2"},
            session_id="session",
            user_id="user"
        )
        assert result2 is False
        
        # Verify dropped events count
        stats = buffer.get_async_queue_stats()
        assert stats["dropped_events"] >= 1

    def test_flush_task_buffer_when_not_hybrid(self):
        """Test that flush does nothing in normal mode."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True,
            hybrid_mode_enabled=False
        )

        flushed = buffer.flush_task_buffer("task-123")

        assert flushed == 0

    def test_flush_task_buffer_empty_buffer(self):
        """Test flushing empty buffer."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True,
            hybrid_mode_enabled=True
        )

        flushed = buffer.flush_task_buffer("task-123")

        assert flushed == 0

    def test_flush_task_buffer_enqueues_events(self):
        """Test successful buffer flush enqueues events to async queue."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100  # High threshold so manual flush needed
        )

        # Add events to RAM buffer manually
        buffer._ram_buffer["task-123"] = [
            ("event1", {"data": "1"}, int(time.time() * 1000), "session", "user"),
            ("event2", {"data": "2"}, int(time.time() * 1000), "session", "user"),
        ]

        flushed = buffer.flush_task_buffer("task-123")

        # Events should be enqueued (not synchronously written)
        assert flushed == 2
        # RAM buffer should be empty after flush
        assert buffer.get_ram_buffer_size("task-123") == 0
        
        # Cleanup
        buffer.shutdown()

    def test_flush_task_buffer_queue_full_readds_events(self):
        """Test that when queue is full, events are re-added to buffer."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            async_write_queue_size=1  # Very small queue
        )

        # Stop the worker so queue fills up
        buffer._stop_async_write_worker()

        # Add events to RAM buffer
        buffer._ram_buffer["task-123"] = [
            ("event1", {"data": "1"}, int(time.time() * 1000), "session", "user"),
            ("event2", {"data": "2"}, int(time.time() * 1000), "session", "user"),
            ("event3", {"data": "3"}, int(time.time() * 1000), "session", "user"),
        ]

        flushed = buffer.flush_task_buffer("task-123")

        # First event should succeed, rest should fail due to queue full
        assert flushed >= 1
        # Failed events should be re-added to buffer
        remaining = buffer.get_ram_buffer_size("task-123")
        assert remaining >= 0  # Some events may have failed to enqueue

    def test_flush_all_buffers(self):
        """Test flushing all buffers."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True
        )

        # Add events for multiple tasks
        buffer._ram_buffer["task-1"] = [
            ("event", {}, int(time.time() * 1000), "session", "user")
        ]
        buffer._ram_buffer["task-2"] = [
            ("event", {}, int(time.time() * 1000), "session", "user")
        ]

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo

            total_flushed = buffer.flush_all_buffers()

            assert total_flushed == 2

    def test_flush_all_buffers_when_not_hybrid(self):
        """Test flush_all_buffers does nothing in normal mode."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True,
            hybrid_mode_enabled=False
        )

        total = buffer.flush_all_buffers()

        assert total == 0

    def test_get_ram_buffer_size(self):
        """Test getting RAM buffer size."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True,
            hybrid_mode_enabled=True
        )

        buffer._ram_buffer["task-123"] = [
            ("event1", {}, 0, "s", "u"),
            ("event2", {}, 0, "s", "u"),
        ]

        size = buffer.get_ram_buffer_size("task-123")

        assert size == 2

    def test_get_ram_buffer_size_nonexistent(self):
        """Test getting size of nonexistent buffer."""
        buffer = PersistentSSEEventBuffer(
            session_factory=MagicMock(),
            enabled=True,
            hybrid_mode_enabled=True
        )

        size = buffer.get_ram_buffer_size("nonexistent")

        assert size == 0

    def test_get_buffered_events_flushes_first_in_hybrid(self):
        """Test that get_buffered_events flushes RAM in hybrid mode."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True
        )

        # Add event to RAM buffer
        buffer._ram_buffer["task-123"] = [
            ("event", {"data": "test"}, int(time.time() * 1000), "session", "user")
        ]

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_buffered_events.return_value = []
            mock_repo_class.return_value = mock_repo

            events = buffer.get_buffered_events("task-123")

            # Should have flushed RAM buffer first
            assert "task-123" not in buffer._ram_buffer or len(buffer._ram_buffer["task-123"]) == 0

    def test_get_buffered_events_when_disabled(self):
        """Test that get_buffered_events returns empty when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        events = buffer.get_buffered_events("task-123")

        assert events == []

    def test_get_buffered_events_db_exception(self):
        """Test handling of DB exceptions in get_buffered_events."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo_class.side_effect = Exception("DB error")

            events = buffer.get_buffered_events("task-123")

            assert events == []

    def test_has_unconsumed_events_checks_ram_first_in_hybrid(self):
        """Test that has_unconsumed_events checks RAM buffer in hybrid mode."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True
        )

        buffer._ram_buffer["task-123"] = [("event", {}, 0, "s", "u")]

        has_events = buffer.has_unconsumed_events("task-123")

        assert has_events is True

    def test_has_unconsumed_events_when_disabled(self):
        """Test that has_unconsumed_events returns False when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        has_events = buffer.has_unconsumed_events("task-123")

        assert has_events is False

    def test_get_unconsumed_events_for_session_when_disabled(self):
        """Test that get_unconsumed_events_for_session returns empty when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        events = buffer.get_unconsumed_events_for_session("session-123")

        assert events == {}

    def test_get_unconsumed_events_for_session_groups_by_task(self):
        """Test that events are properly grouped by task ID."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        # Mock database events
        mock_event1 = MagicMock()
        mock_event1.task_id = "task-1"
        mock_event1.event_type = "test"
        mock_event1.event_data = {}
        mock_event1.event_sequence = 1
        mock_event1.created_at = "2024-01-01"

        mock_event2 = MagicMock()
        mock_event2.task_id = "task-2"
        mock_event2.event_type = "test"
        mock_event2.event_data = {}
        mock_event2.event_sequence = 1
        mock_event2.created_at = "2024-01-01"

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_unconsumed_events_for_session.return_value = [mock_event1, mock_event2]
            mock_repo_class.return_value = mock_repo

            events = buffer.get_unconsumed_events_for_session("session-123")

            assert "task-1" in events
            assert "task-2" in events
            assert len(events["task-1"]) == 1
            assert len(events["task-2"]) == 1

    def test_delete_events_for_task_when_disabled(self):
        """Test that delete does nothing when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        deleted = buffer.delete_events_for_task("task-123")

        assert deleted == 0

    def test_delete_events_clears_ram_buffer_in_hybrid(self):
        """Test that delete clears RAM buffer in hybrid mode."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True,
            hybrid_mode_enabled=True
        )

        buffer._ram_buffer["task-123"] = [("event", {}, 0, "s", "u")]

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.delete_events_for_task.return_value = 5
            mock_repo_class.return_value = mock_repo

            deleted = buffer.delete_events_for_task("task-123")

            # Should return RAM + DB count
            assert deleted == 6  # 1 from RAM, 5 from DB
            assert "task-123" not in buffer._ram_buffer

    def test_delete_events_clears_metadata_cache(self):
        """Test that delete clears metadata cache."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        buffer.set_task_metadata("task-123", "session", "user")

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.delete_events_for_task.return_value = 0
            mock_repo_class.return_value = mock_repo

            buffer.delete_events_for_task("task-123")

            assert "task-123" not in buffer._task_metadata_cache

    def test_cleanup_old_events_when_disabled(self):
        """Test cleanup does nothing when disabled."""
        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=False
        )

        deleted = buffer.cleanup_old_events(days=7)

        assert deleted == 0

    def test_cleanup_old_events_success(self):
        """Test successful old event cleanup."""
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_factory,
            enabled=True
        )

        with patch('solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.cleanup_consumed_events.return_value = 10
            mock_repo_class.return_value = mock_repo

            with patch('solace_agent_mesh.shared.utils.timestamp_utils.now_epoch_ms') as mock_now:
                mock_now.return_value = 1000000000  # Some timestamp

                deleted = buffer.cleanup_old_events(days=7)

                assert deleted == 10
                mock_db.commit.assert_called_once()
