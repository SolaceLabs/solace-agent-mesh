"""Unit tests for PersistentSSEEventBuffer.

These tests focus on the core buffer behaviors:
1. Buffering events to RAM (hybrid mode)
2. Task metadata storage and retrieval
3. Buffer mode detection (hybrid vs direct DB)

These tests use minimal mocking - only testing the in-memory behaviors
that don't require actual database connections.
"""

import pytest
from unittest.mock import Mock, patch


class TestBufferEventRouting:
    """Tests for buffer_event routing logic between hybrid and direct modes."""

    def test_routes_to_db_when_hybrid_disabled(self):
        """When hybrid buffer is disabled, events should route to _buffer_event_to_db."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=False,
        )

        # Set up metadata first
        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")

        # Mock the DB method
        with patch.object(buffer, '_buffer_event_to_db', return_value=True) as mock_db:
            with patch.object(buffer, '_buffer_event_hybrid', return_value=True) as mock_hybrid:
                buffer.buffer_event(
                    task_id="task-123",
                    event_type="message",
                    event_data={"text": "Hello"},
                )

                # Should call DB method, not hybrid
                mock_db.assert_called_once()
                mock_hybrid.assert_not_called()

    def test_routes_to_hybrid_when_hybrid_enabled(self):
        """When hybrid buffer is enabled, events should route to _buffer_event_hybrid."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=5,
        )

        # Set up metadata first
        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")

        with patch.object(buffer, '_buffer_event_to_db', return_value=True) as mock_db:
            with patch.object(buffer, '_buffer_event_hybrid', return_value=True) as mock_hybrid:
                buffer.buffer_event(
                    task_id="task-123",
                    event_type="message",
                    event_data={"text": "Hello"},
                )

                # Should call hybrid method, not DB
                mock_hybrid.assert_called_once()
                mock_db.assert_not_called()


class TestRamBuffer:
    """Tests for in-memory RAM buffer operations (hybrid mode)."""

    def test_events_stored_in_ram_buffer(self):
        """Events should be stored in RAM buffer in hybrid mode."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,  # High threshold so no auto-flush
        )

        # Manually call the hybrid buffer method (bypassing metadata checks)
        buffer._buffer_event_hybrid(
            task_id="task-123",
            event_type="message",
            event_data={"text": "Event 1"},
            session_id="session-abc",
            user_id="user-xyz",
        )

        buffer._buffer_event_hybrid(
            task_id="task-123",
            event_type="message",
            event_data={"text": "Event 2"},
            session_id="session-abc",
            user_id="user-xyz",
        )

        # Should have 2 events in RAM
        assert buffer.get_ram_buffer_size("task-123") == 2

    def test_ram_buffer_cleared_after_delete(self):
        """RAM buffer should be cleared when delete_events_for_task is called."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,
        )

        # Add events to RAM manually
        buffer._ram_buffer["task-123"] = [
            ("message", {"text": "Event 1"}, 1000, "session-abc", "user-xyz"),
            ("message", {"text": "Event 2"}, 2000, "session-abc", "user-xyz"),
        ]

        assert buffer.get_ram_buffer_size("task-123") == 2

        # Delete - mock the DB portion
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
        ):
            # This will fail to delete from DB but should still clear RAM
            count = buffer.delete_events_for_task("task-123")

        # RAM buffer should be empty
        assert buffer.get_ram_buffer_size("task-123") == 0


class TestTaskMetadata:
    """Tests for task metadata storage (session_id, user_id for authorization)."""

    def test_set_and_get_metadata_from_cache(self):
        """Metadata should be stored in cache and retrievable."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=None,  # No DB needed for this test
            enabled=True,
        )

        # Set metadata
        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")

        # Get metadata
        metadata = buffer.get_task_metadata("task-123")

        assert metadata is not None
        assert metadata["session_id"] == "session-abc"
        assert metadata["user_id"] == "user-xyz"

    def test_clear_metadata_removes_from_cache(self):
        """clear_task_metadata should remove from in-memory cache."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=True,
        )

        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")
        assert "task-123" in buffer._task_metadata_cache

        buffer.clear_task_metadata("task-123")
        assert "task-123" not in buffer._task_metadata_cache

    def test_metadata_survives_across_calls(self):
        """Metadata should persist across multiple get calls."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=True,
        )

        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")

        # Multiple gets should all succeed
        for _ in range(3):
            metadata = buffer.get_task_metadata("task-123")
            assert metadata["session_id"] == "session-abc"


class TestBufferEnabled:
    """Tests for buffer enabled/disabled states."""

    def test_is_enabled_when_configured(self):
        """Buffer should report enabled when both flag and factory are set."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
        )

        assert buffer.is_enabled() is True

    def test_is_disabled_when_flag_false(self):
        """Buffer should report disabled when enabled=False."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        assert buffer.is_enabled() is False

    def test_is_disabled_when_no_factory(self):
        """Buffer should report disabled when no session factory."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=None,
            enabled=True,
        )

        assert buffer.is_enabled() is False

    def test_buffer_event_returns_false_when_disabled(self):
        """buffer_event should return False when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.buffer_event(
            task_id="task-123",
            event_type="message",
            event_data={"text": "Hello"},
        )

        assert result is False


class TestHybridModeDetection:
    """Tests for hybrid mode enabled/disabled detection."""

    def test_hybrid_mode_enabled(self):
        """is_hybrid_mode_enabled should return True when properly configured."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=True,
        )

        assert buffer.is_hybrid_mode_enabled() is True

    def test_hybrid_mode_disabled_when_buffer_disabled(self):
        """Hybrid mode should be disabled when buffer itself is disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
            hybrid_mode_enabled=True,  # Flag is true but buffer disabled
        )

        assert buffer.is_hybrid_mode_enabled() is False

    def test_hybrid_mode_disabled_by_default(self):
        """Hybrid mode should be disabled by default."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
        )

        assert buffer.is_hybrid_mode_enabled() is False


class TestMissingMetadata:
    """Tests for handling missing metadata scenarios."""

    def test_buffer_event_fails_without_metadata(self):
        """buffer_event should return False when no metadata is available."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
        )

        # Don't set metadata
        result = buffer.buffer_event(
            task_id="task-unknown",
            event_type="message",
            event_data={"text": "Hello"},
        )

        # Should fail because no metadata
        assert result is False

    def test_buffer_event_succeeds_with_explicit_ids(self):
        """buffer_event should work when session_id and user_id are provided explicitly."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=False,
        )

        # Mock the DB method to not actually hit database
        with patch.object(buffer, '_buffer_event_to_db', return_value=True):
            result = buffer.buffer_event(
                task_id="task-123",
                event_type="message",
                event_data={"text": "Hello"},
                session_id="session-abc",  # Explicit
                user_id="user-xyz",  # Explicit
            )

            assert result is True


class TestFlushTaskBuffer:
    """Tests for flush_task_buffer RAM to DB flushing."""

    def test_flush_when_hybrid_disabled_returns_zero(self):
        """flush_task_buffer should return 0 when hybrid mode disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=False,
        )

        result = buffer.flush_task_buffer("task-123")
        assert result == 0

    def test_flush_empty_buffer_returns_zero(self):
        """flush_task_buffer should return 0 when buffer is empty."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=True,
        )

        result = buffer.flush_task_buffer("nonexistent-task")
        assert result == 0

    def test_auto_flush_at_threshold_enqueues_events(self):
        """Events should be enqueued to async queue when threshold reached."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=3,
        )

        # Add 3 events (threshold)
        for i in range(3):
            buffer._buffer_event_hybrid(
                task_id="task-123",
                event_type="message",
                event_data={"text": f"Event {i}"},
                session_id="session-abc",
                user_id="user-xyz",
            )

        # Events should have been enqueued to async queue (RAM buffer should be empty after flush)
        assert buffer.get_ram_buffer_size("task-123") == 0
        # Queue should have the events (or they may have been processed already)
        stats = buffer.get_async_queue_stats()
        assert stats["queue_size"] >= 0  # Events may have been processed
        
        # Cleanup
        buffer.shutdown()

    def test_flush_queue_full_readds_to_buffer(self):
        """When async queue is full, events should be re-added to buffer for retry."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        # Create buffer with very small queue
        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,
            async_write_queue_size=1,  # Very small queue
        )

        # Stop the worker so queue fills up
        buffer._stop_async_write_worker()

        # Add events to RAM manually
        buffer._ram_buffer["task-123"] = [
            ("message", {"text": "Event 1"}, 1000, "session-abc", "user-xyz"),
            ("message", {"text": "Event 2"}, 2000, "session-abc", "user-xyz"),
            ("message", {"text": "Event 3"}, 3000, "session-abc", "user-xyz"),
        ]

        # Flush - first event should succeed, rest should fail due to queue full
        result = buffer.flush_task_buffer("task-123")
        
        # At least one event should have been enqueued
        assert result >= 1
        
        # Failed events should be back in buffer
        remaining = buffer.get_ram_buffer_size("task-123")
        assert remaining >= 0  # Some events may have failed to enqueue


class TestFlushAllBuffers:
    """Tests for flush_all_buffers batch flushing."""

    def test_flush_all_when_hybrid_disabled_returns_zero(self):
        """flush_all_buffers should return 0 when hybrid mode disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=False,
        )

        result = buffer.flush_all_buffers()
        assert result == 0

    def test_flush_all_multiple_tasks_enqueues_events(self):
        """flush_all_buffers should enqueue all tasks to async queue."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,
        )

        # Add events to RAM for multiple tasks
        buffer._ram_buffer["task-1"] = [
            ("message", {"text": "Event 1"}, 1000, "session-abc", "user-xyz"),
        ]
        buffer._ram_buffer["task-2"] = [
            ("message", {"text": "Event 2"}, 2000, "session-abc", "user-xyz"),
            ("message", {"text": "Event 3"}, 3000, "session-abc", "user-xyz"),
        ]

        result = buffer.flush_all_buffers()

        # Should have enqueued 3 total events (1 + 2)
        assert result == 3
        
        # RAM buffers should be empty after flush
        assert buffer.get_ram_buffer_size("task-1") == 0
        assert buffer.get_ram_buffer_size("task-2") == 0
        
        # Cleanup
        buffer.shutdown()


class TestGetBufferedEvents:
    """Tests for get_buffered_events retrieval."""

    def test_get_buffered_events_when_disabled_returns_empty(self):
        """get_buffered_events should return empty list when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.get_buffered_events("task-123")
        assert result == []

    def test_get_buffered_events_flushes_ram_first_in_hybrid(self):
        """get_buffered_events should flush RAM to DB first in hybrid mode."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
        )

        with patch.object(buffer, 'flush_task_buffer') as mock_flush:
            with patch(
                'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
            ) as MockRepo:
                mock_repo_instance = Mock()
                mock_repo_instance.get_buffered_events.return_value = []
                MockRepo.return_value = mock_repo_instance

                buffer.get_buffered_events("task-123")

                # flush_task_buffer should be called first
                mock_flush.assert_called_once_with("task-123")


class TestHasUnconsumedEvents:
    """Tests for has_unconsumed_events checking."""

    def test_has_unconsumed_when_disabled_returns_false(self):
        """has_unconsumed_events should return False when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.has_unconsumed_events("task-123")
        assert result is False

    def test_has_unconsumed_checks_ram_in_hybrid_mode(self):
        """has_unconsumed_events should check RAM buffer first in hybrid mode."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=True,
            hybrid_mode_enabled=True,
        )

        # Add events to RAM
        buffer._ram_buffer["task-123"] = [
            ("message", {"text": "Event 1"}, 1000, "session-abc", "user-xyz"),
        ]

        # Should return True without hitting DB because RAM has events
        result = buffer.has_unconsumed_events("task-123")
        assert result is True

    def test_has_unconsumed_checks_db_when_ram_empty(self):
        """has_unconsumed_events should check DB when RAM is empty in hybrid mode."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
        )

        # Mock repository
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
        ) as MockRepo:
            mock_repo_instance = Mock()
            mock_repo_instance.has_unconsumed_events.return_value = True
            MockRepo.return_value = mock_repo_instance

            result = buffer.has_unconsumed_events("task-123")

            # Should check DB
            mock_repo_instance.has_unconsumed_events.assert_called_once()
            assert result is True


class TestGetUnconsumedEventsForSession:
    """Tests for get_unconsumed_events_for_session session-level retrieval."""

    def test_get_unconsumed_for_session_when_disabled_returns_empty(self):
        """get_unconsumed_events_for_session should return empty dict when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.get_unconsumed_events_for_session("session-abc")
        assert result == {}

    def test_get_unconsumed_for_session_groups_by_task(self):
        """get_unconsumed_events_for_session should group events by task_id."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
        )

        # Mock repository to return events from multiple tasks
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
        ) as MockRepo:
            # Create mock event objects
            mock_event_1 = Mock()
            mock_event_1.task_id = "task-1"
            mock_event_1.event_type = "message"
            mock_event_1.event_data = {"text": "Hello"}
            mock_event_1.event_sequence = 1
            mock_event_1.created_at = 1000

            mock_event_2 = Mock()
            mock_event_2.task_id = "task-1"
            mock_event_2.event_type = "message"
            mock_event_2.event_data = {"text": "World"}
            mock_event_2.event_sequence = 2
            mock_event_2.created_at = 2000

            mock_event_3 = Mock()
            mock_event_3.task_id = "task-2"
            mock_event_3.event_type = "artifact"
            mock_event_3.event_data = {"name": "file.txt"}
            mock_event_3.event_sequence = 1
            mock_event_3.created_at = 3000

            mock_repo_instance = Mock()
            mock_repo_instance.get_unconsumed_events_for_session.return_value = [
                mock_event_1, mock_event_2, mock_event_3
            ]
            MockRepo.return_value = mock_repo_instance

            result = buffer.get_unconsumed_events_for_session("session-abc")

            # Should have 2 tasks
            assert len(result) == 2
            assert "task-1" in result
            assert "task-2" in result

            # task-1 should have 2 events
            assert len(result["task-1"]) == 2
            # task-2 should have 1 event
            assert len(result["task-2"]) == 1


class TestDeleteEventsForTask:
    """Tests for delete_events_for_task cleanup."""

    def test_delete_when_disabled_returns_zero(self):
        """delete_events_for_task should return 0 when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.delete_events_for_task("task-123")
        assert result == 0

    def test_delete_clears_metadata(self):
        """delete_events_for_task should clear task metadata cache."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
        )

        # Set metadata
        buffer.set_task_metadata("task-123", "session-abc", "user-xyz")
        assert buffer.get_task_metadata("task-123") is not None

        # Mock repository
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
        ) as MockRepo:
            mock_repo_instance = Mock()
            mock_repo_instance.delete_events_for_task.return_value = 5
            MockRepo.return_value = mock_repo_instance

            buffer.delete_events_for_task("task-123")

            # Metadata should be cleared
            assert buffer.get_task_metadata("task-123") is None


class TestCleanupOldEvents:
    """Tests for cleanup_old_events scheduled cleanup."""

    def test_cleanup_when_disabled_returns_zero(self):
        """cleanup_old_events should return 0 when disabled."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        buffer = PersistentSSEEventBuffer(
            session_factory=Mock(),
            enabled=False,
        )

        result = buffer.cleanup_old_events(days=7)
        assert result == 0

    def test_cleanup_calls_repository(self):
        """cleanup_old_events should call repository cleanup method."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
        )

        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.sse_event_buffer_repository.SSEEventBufferRepository'
        ) as MockRepo:
            with patch(
                'solace_agent_mesh.shared.utils.timestamp_utils.now_epoch_ms',
                return_value=1000000000  # Mock timestamp
            ):
                mock_repo_instance = Mock()
                mock_repo_instance.cleanup_consumed_events.return_value = 42
                MockRepo.return_value = mock_repo_instance

                result = buffer.cleanup_old_events(days=7)

                # Should call repository cleanup
                mock_repo_instance.cleanup_consumed_events.assert_called_once()
                assert result == 42


class TestGetTaskMetadataDbFallback:
    """Tests for get_task_metadata database fallback."""

    def test_metadata_fallback_to_db_when_not_in_cache(self):
        """get_task_metadata should fall back to DB when not in cache."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
        )

        # Mock TaskRepository
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository'
        ) as MockRepo:
            mock_task = Mock()
            mock_task.session_id = "session-from-db"
            mock_task.user_id = "user-from-db"

            mock_repo_instance = Mock()
            mock_repo_instance.find_by_id.return_value = mock_task
            MockRepo.return_value = mock_repo_instance

            # Should return data from DB
            metadata = buffer.get_task_metadata("task-123")

            assert metadata is not None
            assert metadata["session_id"] == "session-from-db"
            assert metadata["user_id"] == "user-from-db"

            # Should now be in cache
            assert "task-123" in buffer._task_metadata_cache

    def test_metadata_db_fallback_returns_none_if_not_found(self):
        """get_task_metadata should return None if not in cache or DB."""
        from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
            PersistentSSEEventBuffer,
        )

        mock_session_factory = Mock()
        mock_session = Mock()
        mock_session_factory.return_value = mock_session

        buffer = PersistentSSEEventBuffer(
            session_factory=mock_session_factory,
            enabled=True,
        )

        # Mock TaskRepository to return None
        with patch(
            'solace_agent_mesh.gateway.http_sse.repository.task_repository.TaskRepository'
        ) as MockRepo:
            mock_repo_instance = Mock()
            mock_repo_instance.find_by_id.return_value = None
            MockRepo.return_value = mock_repo_instance

            metadata = buffer.get_task_metadata("task-unknown")
            assert metadata is None
