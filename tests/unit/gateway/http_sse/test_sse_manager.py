#!/usr/bin/env python3
"""
Comprehensive unit tests for SSEManager to increase coverage from 28% to 75%+.

Tests cover:
- SSEManager initialization and lifecycle
- Connection management (create, remove, cleanup)
- Event distribution (send_event with various scenarios)
- Queue management and processing
- Error handling and edge cases
- Lock management and cleanup
- JSON sanitization
- Context manager functionality
"""

import pytest
import asyncio
import threading
import json
import math
import datetime
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Dict, Any

from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager
from solace_agent_mesh.gateway.http_sse.sse_event_buffer import SSEEventBuffer


class TestSSEManagerInitialization:
    """Test SSEManager initialization and basic setup."""

    def test_init_with_valid_parameters(self):
        """Test SSEManager initialization with valid parameters."""
        # Setup
        max_queue_size = 100
        event_buffer = MagicMock(spec=SSEEventBuffer)

        # Execute
        manager = SSEManager(max_queue_size, event_buffer)

        # Verify
        assert manager._max_queue_size == max_queue_size
        assert manager._event_buffer == event_buffer
        assert manager._connections == {}
        assert manager.log_identifier == "[SSEManager]"
        # Verify the single threading lock exists
        assert hasattr(manager._lock, 'acquire') and hasattr(manager._lock, 'release')
        # Verify connection tracking set is initialized
        assert manager._tasks_with_prior_connection == set()

    def test_init_with_zero_queue_size(self):
        """Test SSEManager initialization with zero queue size."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        
        # Execute
        manager = SSEManager(0, event_buffer)
        
        # Verify
        assert manager._max_queue_size == 0

    def test_init_with_large_queue_size(self):
        """Test SSEManager initialization with large queue size."""
        # Setup
        max_queue_size = 10000
        event_buffer = MagicMock(spec=SSEEventBuffer)
        
        # Execute
        manager = SSEManager(max_queue_size, event_buffer)
        
        # Verify
        assert manager._max_queue_size == max_queue_size


class TestSSEManagerLockManagement:
    """Test lock management functionality.

    Note: SSEManager now uses a single threading.Lock for cross-event-loop
    synchronization instead of per-event-loop asyncio.Lock. These tests verify
    the new threading lock behavior.
    """

    def test_single_threading_lock_used(self):
        """Test that SSEManager uses a single threading lock for synchronization."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)

        # Verify - should have a single threading lock
        assert hasattr(manager, '_lock')
        assert isinstance(manager._lock, type(threading.Lock()))

    def test_lock_is_shared_across_operations(self):
        """Test that all operations share the same lock."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)

        # Get reference to the lock
        lock = manager._lock

        async def test_async():
            # Execute - create a connection (uses the lock internally)
            await manager.create_sse_connection("test-task")

        asyncio.run(test_async())

        # Verify - lock should still be the same object
        assert manager._lock is lock

    def test_cleanup_old_locks_is_noop(self):
        """Test cleanup_old_locks is a no-op with single threading lock."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)

        # Get reference to the lock before cleanup
        lock_before = manager._lock

        # Execute
        manager.cleanup_old_locks()

        # Verify - lock should be unchanged
        assert manager._lock is lock_before

    def test_lock_provides_thread_safety(self):
        """Test that the threading lock provides thread safety."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)

        # Verify lock can be acquired and released
        acquired = manager._lock.acquire(blocking=False)
        assert acquired is True
        manager._lock.release()

        # Verify lock blocks when already held
        manager._lock.acquire()
        second_acquire = manager._lock.acquire(blocking=False)
        assert second_acquire is False
        manager._lock.release()


class TestSSEManagerConnectionManagement:
    """Test connection creation, removal, and management."""

    @pytest.mark.asyncio
    async def test_create_sse_connection_new_task(self):
        """Test creating SSE connection for a new task."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Execute
        queue = await manager.create_sse_connection(task_id)
        
        # Verify
        assert isinstance(queue, asyncio.Queue)
        assert queue.maxsize == 100
        assert task_id in manager._connections
        assert queue in manager._connections[task_id]
        assert len(manager._connections[task_id]) == 1
        event_buffer.get_and_remove_buffer.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_create_sse_connection_with_buffered_events(self):
        """Test creating SSE connection when buffered events exist."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        buffered_events = [
            {"event": "message", "data": "event1"},
            {"event": "message", "data": "event2"}
        ]
        event_buffer.get_and_remove_buffer.return_value = buffered_events
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Execute
        queue = await manager.create_sse_connection(task_id)
        
        # Verify
        assert queue.qsize() == 2
        event1 = await queue.get()
        event2 = await queue.get()
        assert event1 == {"event": "message", "data": "event1"}
        assert event2 == {"event": "message", "data": "event2"}

    @pytest.mark.asyncio
    async def test_create_sse_connection_multiple_for_same_task(self):
        """Test creating multiple SSE connections for the same task."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Execute
        queue1 = await manager.create_sse_connection(task_id)
        queue2 = await manager.create_sse_connection(task_id)
        
        # Verify
        assert queue1 != queue2
        assert len(manager._connections[task_id]) == 2
        assert queue1 in manager._connections[task_id]
        assert queue2 in manager._connections[task_id]

    @pytest.mark.asyncio
    async def test_remove_sse_connection_existing_queue(self):
        """Test removing an existing SSE connection."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        
        # Execute
        await manager.remove_sse_connection(task_id, queue)
        
        # Verify
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_remove_sse_connection_one_of_multiple(self):
        """Test removing one connection when multiple exist for a task."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue1 = await manager.create_sse_connection(task_id)
        queue2 = await manager.create_sse_connection(task_id)
        
        # Execute
        await manager.remove_sse_connection(task_id, queue1)
        
        # Verify
        assert task_id in manager._connections
        assert len(manager._connections[task_id]) == 1
        assert queue2 in manager._connections[task_id]
        assert queue1 not in manager._connections[task_id]

    @pytest.mark.asyncio
    async def test_remove_sse_connection_already_removed(self):
        """Test removing a connection that was already removed."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        await manager.remove_sse_connection(task_id, queue)
        
        # Execute - should not raise exception
        await manager.remove_sse_connection(task_id, queue)
        
        # Verify - no exception raised

    @pytest.mark.asyncio
    async def test_remove_sse_connection_nonexistent_task(self):
        """Test removing connection for non-existent task."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "nonexistent-task"
        fake_queue = asyncio.Queue()
        
        # Execute - should not raise exception
        await manager.remove_sse_connection(task_id, fake_queue)
        
        # Verify - no exception raised


class TestSSEManagerJSONSanitization:
    """Test JSON sanitization functionality."""

    def test_sanitize_json_basic_types(self):
        """Test sanitization of basic JSON types."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        # Test cases
        test_cases = [
            ("string", "string"),
            (123, 123),
            (123.45, 123.45),
            (True, True),
            (False, False),
            (None, None),
        ]
        
        for input_val, expected in test_cases:
            result = manager._sanitize_json(input_val)
            assert result == expected

    def test_sanitize_json_nan_infinity(self):
        """Test sanitization of NaN and infinity values."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        # Test cases
        test_cases = [
            (float('nan'), None),
            (float('inf'), None),
            (float('-inf'), None),
        ]
        
        for input_val, expected in test_cases:
            result = manager._sanitize_json(input_val)
            assert result == expected

    def test_sanitize_json_datetime_objects(self):
        """Test sanitization of datetime objects."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        # Test datetime
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        result = manager._sanitize_json(dt)
        assert result == dt.isoformat()
        
        # Test date
        date = datetime.date(2023, 1, 1)
        result = manager._sanitize_json(date)
        assert result == date.isoformat()

    def test_sanitize_json_dict(self):
        """Test sanitization of dictionary objects."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        input_dict = {
            "string": "value",
            "number": 123,
            "nan": float('nan'),
            "datetime": datetime.datetime(2023, 1, 1),
            "nested": {
                "inf": float('inf'),
                "valid": "data"
            }
        }
        
        result = manager._sanitize_json(input_dict)
        
        assert result["string"] == "value"
        assert result["number"] == 123
        assert result["nan"] is None
        assert result["datetime"] == "2023-01-01T00:00:00"
        assert result["nested"]["inf"] is None
        assert result["nested"]["valid"] == "data"

    def test_sanitize_json_list(self):
        """Test sanitization of list objects."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        input_list = [
            "string",
            123,
            float('nan'),
            datetime.datetime(2023, 1, 1),
            {"nested": float('inf')}
        ]
        
        result = manager._sanitize_json(input_list)
        
        assert result[0] == "string"
        assert result[1] == 123
        assert result[2] is None
        assert result[3] == "2023-01-01T00:00:00"
        assert result[4]["nested"] is None

    def test_sanitize_json_custom_object(self):
        """Test sanitization of custom objects."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        class CustomObject:
            def __str__(self):
                return "custom_object_string"
        
        custom_obj = CustomObject()
        result = manager._sanitize_json(custom_obj)
        
        assert result == "custom_object_string"


class TestSSEManagerEventDistribution:
    """Test event distribution functionality."""

    @pytest.mark.asyncio
    async def test_send_event_to_active_connections(self):
        """Test sending event to active connections."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue1 = await manager.create_sse_connection(task_id)
        queue2 = await manager.create_sse_connection(task_id)
        
        event_data = {"message": "test event", "timestamp": "2023-01-01"}
        
        # Execute
        await manager.send_event(task_id, event_data, "message")
        
        # Verify
        assert queue1.qsize() == 1
        assert queue2.qsize() == 1
        
        event1 = await queue1.get()
        event2 = await queue2.get()
        
        expected_payload = {
            "event": "message",
            "data": json.dumps(event_data, allow_nan=False)
        }
        
        assert event1 == expected_payload
        assert event2 == expected_payload

    @pytest.mark.asyncio
    async def test_send_event_no_connections_buffers_event(self):
        """Test sending event when no connections exist buffers the event."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        event_data = {"message": "test event"}
        
        # Execute
        await manager.send_event(task_id, event_data, "message")
        
        # Verify
        expected_payload = {
            "event": "message",
            "data": json.dumps(event_data, allow_nan=False)
        }
        event_buffer.buffer_event.assert_called_once_with(task_id, expected_payload)

    @pytest.mark.asyncio
    async def test_send_event_json_serialization_error(self):
        """Test send_event handles JSON serialization errors."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        await manager.create_sse_connection(task_id)
        
        # Create object that can't be serialized
        class UnserializableObject:
            def __init__(self):
                self.circular_ref = self
        
        event_data = {"obj": UnserializableObject()}
        
        # Execute - should not raise exception
        await manager.send_event(task_id, event_data, "message")
        
        # Verify - event should not be sent due to serialization error

    @pytest.mark.asyncio
    async def test_send_event_queue_full_removes_connection(self):
        """Test send_event removes connection when queue is full."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(1, event_buffer)  # Small queue size
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        
        # Fill the queue
        await queue.put("existing_item")
        
        event_data = {"message": "test event"}
        
        # Execute
        await manager.send_event(task_id, event_data, "message")
        
        # Verify - connection should be removed due to full queue
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_send_event_timeout_removes_connection(self):
        """Test send_event removes connection on timeout."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Create a mock queue that times out
        mock_queue = AsyncMock()
        mock_queue.put.side_effect = asyncio.TimeoutError()
        
        manager._connections[task_id] = [mock_queue]
        
        event_data = {"message": "test event"}
        
        # Execute
        await manager.send_event(task_id, event_data, "message")
        
        # Verify - connection should be removed due to timeout
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_send_event_with_default_event_type(self):
        """Test send_event uses default event type."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        event_data = {"message": "test event"}
        
        # Execute - don't specify event_type
        await manager.send_event(task_id, event_data)
        
        # Verify
        event = await queue.get()
        assert event["event"] == "message"  # Default event type

    @pytest.mark.asyncio
    async def test_send_event_with_custom_event_type(self):
        """Test send_event with custom event type."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        event_data = {"message": "test event"}
        
        # Execute
        await manager.send_event(task_id, event_data, "custom_event")
        
        # Verify
        event = await queue.get()
        assert event["event"] == "custom_event"

    @pytest.mark.asyncio
    async def test_send_event_partial_connection_failures(self):
        """Test send_event handles partial connection failures."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Create one good queue and one that will fail
        good_queue = await manager.create_sse_connection(task_id)
        
        bad_queue = AsyncMock()
        bad_queue.put.side_effect = Exception("Connection error")
        manager._connections[task_id].append(bad_queue)
        
        event_data = {"message": "test event"}
        
        # Execute
        await manager.send_event(task_id, event_data, "message")
        
        # Verify - good queue should receive event, bad queue should be removed
        assert good_queue.qsize() == 1
        assert len(manager._connections[task_id]) == 1
        assert good_queue in manager._connections[task_id]


class TestSSEManagerBackgroundTaskBuffering:
    """Test background task buffering behavior."""

    @pytest.mark.asyncio
    async def test_background_task_buffers_before_first_connection(self):
        """Test that background tasks buffer events before any connection is made."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "background-task-123"

        # Mark task as background task
        manager._background_task_cache[task_id] = True

        event_data = {"message": "test event"}

        # Execute - no connection made yet
        await manager.send_event(task_id, event_data, "message")

        # Verify - event should be buffered, not dropped
        expected_payload = {
            "event": "message",
            "data": json.dumps(event_data, allow_nan=False)
        }
        event_buffer.buffer_event.assert_called_once_with(task_id, expected_payload)

    @pytest.mark.asyncio
    async def test_background_task_drops_after_disconnection(self):
        """Test that background tasks drop events after client disconnects."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "background-task-123"

        # Mark task as background task
        manager._background_task_cache[task_id] = True

        # Create connection (simulates client connecting)
        queue = await manager.create_sse_connection(task_id)

        # Remove connection (simulates client disconnecting)
        await manager.remove_sse_connection(task_id, queue)

        event_data = {"message": "test event"}

        # Execute - client has connected and disconnected
        await manager.send_event(task_id, event_data, "message")

        # Verify - event should be dropped, not buffered
        event_buffer.buffer_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_connection_marks_task_as_having_prior_connection(self):
        """Test that creating a connection marks the task in the tracking set."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"

        # Verify - task not in tracking set initially
        assert task_id not in manager._tasks_with_prior_connection

        # Execute
        await manager.create_sse_connection(task_id)

        # Verify - task is now in tracking set
        assert task_id in manager._tasks_with_prior_connection

    @pytest.mark.asyncio
    async def test_close_all_for_task_clears_tracking(self):
        """Test that close_all_for_task clears the connection tracking."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"

        await manager.create_sse_connection(task_id)
        assert task_id in manager._tasks_with_prior_connection

        # Execute
        await manager.close_all_for_task(task_id)

        # Verify - tracking is cleared
        assert task_id not in manager._tasks_with_prior_connection

    @pytest.mark.asyncio
    async def test_close_all_clears_tracking(self):
        """Test that close_all clears all connection tracking."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)

        # Create connections for multiple tasks
        await manager.create_sse_connection("task-1")
        await manager.create_sse_connection("task-2")

        assert len(manager._tasks_with_prior_connection) == 2

        # Execute
        await manager.close_all()

        # Verify - all tracking is cleared
        assert len(manager._tasks_with_prior_connection) == 0


class TestSSEManagerConnectionLifecycle:
    """Test connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_connection_sends_none_signal(self):
        """Test close_connection sends None signal to queue."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"

        queue = await manager.create_sse_connection(task_id)
        
        # Execute
        await manager.close_connection(task_id, queue)
        
        # Verify
        close_signal = await queue.get()
        assert close_signal is None
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_close_connection_queue_full(self):
        """Test close_connection handles queue full scenario."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(1, event_buffer)  # Small queue
        task_id = "test-task-123"
        
        queue = await manager.create_sse_connection(task_id)
        await queue.put("existing_item")  # Fill queue
        
        # Execute - should not raise exception
        await manager.close_connection(task_id, queue)
        
        # Verify - connection should still be removed
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_close_connection_timeout(self):
        """Test close_connection handles timeout scenario."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Create mock queue that times out
        mock_queue = AsyncMock()
        mock_queue.put.side_effect = asyncio.TimeoutError()
        manager._connections[task_id] = [mock_queue]
        
        # Execute - should not raise exception
        await manager.close_connection(task_id, mock_queue)
        
        # Verify - connection should still be removed
        assert task_id not in manager._connections

    @pytest.mark.asyncio
    async def test_close_all_for_task_with_active_connections(self):
        """Test close_all_for_task with active connections."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        queue1 = await manager.create_sse_connection(task_id)
        queue2 = await manager.create_sse_connection(task_id)
        
        # Execute
        await manager.close_all_for_task(task_id)
        
        # Verify
        assert task_id not in manager._connections
        event_buffer.remove_buffer.assert_called_once_with(task_id)
        
        # Both queues should receive close signal
        close_signal1 = await queue1.get()
        close_signal2 = await queue2.get()
        assert close_signal1 is None
        assert close_signal2 is None

    @pytest.mark.asyncio
    async def test_close_all_for_task_no_connections(self):
        """Test close_all_for_task when no connections exist."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Execute
        await manager.close_all_for_task(task_id)
        
        # Verify - buffer should NOT be removed (race condition case)
        event_buffer.remove_buffer.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_all_for_task_queue_errors(self):
        """Test close_all_for_task handles queue errors gracefully."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Create mock queues with various errors
        queue1 = AsyncMock()
        queue1.put.side_effect = asyncio.QueueFull()
        
        queue2 = AsyncMock()
        queue2.put.side_effect = asyncio.TimeoutError()
        
        queue3 = AsyncMock()
        queue3.put.side_effect = Exception("General error")
        
        manager._connections[task_id] = [queue1, queue2, queue3]
        
        # Execute - should not raise exception
        await manager.close_all_for_task(task_id)
        
        # Verify - task should be cleaned up despite errors
        assert task_id not in manager._connections
        event_buffer.remove_buffer.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_close_all_global_cleanup(self):
        """Test close_all performs global cleanup."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        
        # Create connections for multiple tasks
        task1 = "task-1"
        task2 = "task-2"
        
        queue1 = await manager.create_sse_connection(task1)
        queue2 = await manager.create_sse_connection(task2)
        queue3 = await manager.create_sse_connection(task2)  # Second connection for task2
        
        # Execute
        await manager.close_all()
        
        # Verify
        assert len(manager._connections) == 0
        
        # All queues should receive close signal
        close_signal1 = await queue1.get()
        close_signal2 = await queue2.get()
        close_signal3 = await queue3.get()
        assert close_signal1 is None
        assert close_signal2 is None
        assert close_signal3 is None

    @pytest.mark.asyncio
    async def test_close_all_with_queue_errors(self):
        """Test close_all handles queue errors gracefully."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        # Create mock queues with errors
        task_id = "test-task"
        error_queue = AsyncMock()
        error_queue.put.side_effect = Exception("Queue error")
        
        manager._connections[task_id] = [error_queue]
        
        # Execute - should not raise exception
        await manager.close_all()
        
        # Verify - connections should be cleared despite errors
        assert len(manager._connections) == 0

    @pytest.mark.asyncio
    async def test_close_all_calls_cleanup_old_locks(self):
        """Test close_all calls cleanup_old_locks."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        with patch.object(manager, 'cleanup_old_locks') as mock_cleanup:
            # Execute
            await manager.close_all()
            
            # Verify
            mock_cleanup.assert_called_once()


class TestSSEManagerEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_connection_operations(self):
        """Test concurrent connection creation and removal."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        async def create_and_remove():
            queue = await manager.create_sse_connection(task_id)
            await asyncio.sleep(0.01)  # Small delay
            await manager.remove_sse_connection(task_id, queue)
        
        # Execute multiple concurrent operations
        tasks = [create_and_remove() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify - should not crash and connections should be clean
        assert task_id not in manager._connections or len(manager._connections[task_id]) == 0

    @pytest.mark.asyncio
    async def test_send_event_to_removed_task(self):
        """Test sending event to a task that was removed."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        task_id = "removed-task"
        
        event_data = {"message": "test event"}
        
        # Execute - should buffer event since no connections exist
        await manager.send_event(task_id, event_data, "message")
        
        # Verify
        expected_payload = {
            "event": "message",
            "data": json.dumps(event_data, allow_nan=False)
        }
        event_buffer.buffer_event.assert_called_once_with(task_id, expected_payload)

    @pytest.mark.asyncio
    async def test_memory_cleanup_on_connection_removal(self):
        """Test that memory is properly cleaned up when connections are removed."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        event_buffer.get_and_remove_buffer.return_value = None
        manager = SSEManager(100, event_buffer)
        task_id = "test-task-123"
        
        # Create and remove many connections
        for i in range(100):
            queue = await manager.create_sse_connection(f"{task_id}-{i}")
            await manager.remove_sse_connection(f"{task_id}-{i}", queue)
        
        # Verify - no connections should remain
        assert len(manager._connections) == 0

    def test_sanitize_json_deeply_nested_structure(self):
        """Test JSON sanitization with deeply nested structures."""
        # Setup
        event_buffer = MagicMock(spec=SSEEventBuffer)
        manager = SSEManager(100, event_buffer)
        
        # Create deeply nested structure with problematic values
        nested_data = {
            "level1": {
                "level2": {
                    "level3": [
                        {
                            "nan_value": float('nan'),
                            "inf_value": float('inf'),
                            "datetime": datetime.datetime(2023, 1, 1),
                            "normal": "value"
                        }
                    ]
                }
            }
        }
        
        result = manager._sanitize_json(nested_data)
        
        # Verify deep sanitization
        level3_item = result["level1"]["level2"]["level3"][0]
        assert level3_item["nan_value"] is None
        assert level3_item["inf_value"] is None
        assert level3_item["datetime"] == "2023-01-01T00:00:00"
        assert level3_item["normal"] == "value"

