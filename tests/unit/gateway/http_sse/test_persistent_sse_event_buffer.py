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
