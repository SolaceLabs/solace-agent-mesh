"""
Unit tests for A2A proxy streaming response batching functionality.

Tests cover:
- Configuration precedence (proxy-level vs per-agent override)
- Buffer management operations (append, flush, get)
- Text extraction from various event structures
- Batched event creation with metadata preservation
- Flush trigger logic (threshold, disabled, final)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from a2a.types import (
    Message,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    TextPart,
    DataPart,
    Part,
)

from solace_agent_mesh.agent.proxies.a2a.component import A2AProxyComponent
from solace_agent_mesh.agent.proxies.base.proxy_task_context import ProxyTaskContext


class TestStreamBatchingConfiguration:
    """Tests for batching threshold configuration resolution."""

    def test_proxy_level_default(self):
        """Test that proxy-level default is used when no agent override."""
        component = MagicMock(spec=A2AProxyComponent)
        component.get_config = MagicMock(return_value=1000)
        component._agent_config_by_name = {"test-agent": {}}
        component._get_agent_config = MagicMock(return_value={})

        # Call the real method
        result = A2AProxyComponent._get_stream_batching_threshold(component, "test-agent")

        assert result == 1000
        component.get_config.assert_called_once_with("stream_batching_threshold_bytes", 0)

    def test_per_agent_override(self):
        """Test that per-agent override takes precedence over proxy default."""
        component = MagicMock(spec=A2AProxyComponent)
        component.get_config = MagicMock(return_value=1000)
        agent_config = {"stream_batching_threshold_bytes": 500}
        component._get_agent_config = MagicMock(return_value=agent_config)

        result = A2AProxyComponent._get_stream_batching_threshold(component, "test-agent")

        assert result == 500
        # Should NOT call get_config since agent override exists
        component.get_config.assert_not_called()

    def test_per_agent_override_zero(self):
        """Test that per-agent override of 0 (disabled) is respected."""
        component = MagicMock(spec=A2AProxyComponent)
        component.get_config = MagicMock(return_value=1000)
        agent_config = {"stream_batching_threshold_bytes": 0}
        component._get_agent_config = MagicMock(return_value=agent_config)

        result = A2AProxyComponent._get_stream_batching_threshold(component, "test-agent")

        assert result == 0
        component.get_config.assert_not_called()

    def test_agent_not_found(self):
        """Test fallback to proxy default when agent not found."""
        component = MagicMock(spec=A2AProxyComponent)
        component.get_config = MagicMock(return_value=1000)
        component._get_agent_config = MagicMock(return_value=None)

        result = A2AProxyComponent._get_stream_batching_threshold(component, "unknown-agent")

        assert result == 1000
        component.get_config.assert_called_once_with("stream_batching_threshold_bytes", 0)


class TestBufferManagement:
    """Tests for ProxyTaskContext buffer operations."""

    def test_append_to_buffer(self):
        """Test appending text to streaming buffer."""
        context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )

        context.append_to_streaming_buffer("Hello")
        assert context.streaming_buffer == "Hello"

        context.append_to_streaming_buffer(" World")
        assert context.streaming_buffer == "Hello World"

    def test_get_buffer_content(self):
        """Test getting buffer content without clearing."""
        context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        context.streaming_buffer = "Test content"

        content = context.get_streaming_buffer_content()

        assert content == "Test content"
        # Buffer should not be cleared
        assert context.streaming_buffer == "Test content"

    def test_flush_buffer(self):
        """Test flushing buffer returns content and clears it."""
        context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        context.streaming_buffer = "Test content"

        flushed = context.flush_streaming_buffer()

        assert flushed == "Test content"
        # Buffer should be cleared
        assert context.streaming_buffer == ""

    def test_flush_empty_buffer(self):
        """Test flushing empty buffer returns empty string."""
        context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )

        flushed = context.flush_streaming_buffer()

        assert flushed == ""
        assert context.streaming_buffer == ""


class TestTextExtraction:
    """Tests for extracting text from TaskStatusUpdateEvent."""

    def test_extract_single_text_part(self):
        """Test extracting text from event with single TextPart."""
        message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="Hello World"))]
        )
        event = TaskStatusUpdateEvent(
            task_id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.working, message=message),
            final=False
        )

        component = MagicMock(spec=A2AProxyComponent)
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.get_parts_from_message.return_value = [TextPart(text="Hello World")]
            result = A2AProxyComponent._extract_text_from_status_update(component, event)

        assert result == "Hello World"

    def test_extract_multiple_text_parts(self):
        """Test extracting and concatenating multiple TextParts."""
        message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="test"))]
        )
        event = TaskStatusUpdateEvent(
            task_id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.working, message=message),
            final=False
        )

        component = MagicMock(spec=A2AProxyComponent)
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.get_parts_from_message.return_value = [
                TextPart(text="Hello "),
                TextPart(text="World"),
            ]
            result = A2AProxyComponent._extract_text_from_status_update(component, event)

        assert result == "Hello World"

    def test_extract_no_text_parts(self):
        """Test extracting from event with no TextParts (DataParts only)."""
        message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="test"))]
        )
        event = TaskStatusUpdateEvent(
            task_id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.working, message=message),
            final=False
        )

        component = MagicMock(spec=A2AProxyComponent)
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.get_parts_from_message.return_value = [
                DataPart(kind="data", data={"type": "progress"})
            ]
            result = A2AProxyComponent._extract_text_from_status_update(component, event)

        assert result is None

    def test_extract_no_message(self):
        """Test extracting from event with no message."""
        event = TaskStatusUpdateEvent(
            task_id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.working, message=None),
            final=False
        )

        component = MagicMock(spec=A2AProxyComponent)
        result = A2AProxyComponent._extract_text_from_status_update(component, event)

        assert result is None

    def test_extract_empty_parts_list(self):
        """Test extracting from event with empty parts list."""
        message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="test"))]
        )
        event = TaskStatusUpdateEvent(
            task_id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.working, message=message),
            final=False
        )

        component = MagicMock(spec=A2AProxyComponent)
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.get_parts_from_message.return_value = []
            result = A2AProxyComponent._extract_text_from_status_update(component, event)

        assert result is None


class TestBatchedEventCreation:
    """Tests for creating batched TaskStatusUpdateEvent."""

    def test_create_batched_event(self):
        """Test creating batched event preserves metadata."""
        task_context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        original_event = TaskStatusUpdateEvent(
            task_id="downstream-task",
            context_id="downstream-ctx",
            status=TaskStatus(state=TaskState.working),
            final=False,
            metadata={"custom": "data"}
        )

        component = MagicMock(spec=A2AProxyComponent)
        # Create a real Message object instead of a mock
        mock_message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="Batched text"))]
        )

        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.create_agent_text_message.return_value = mock_message
            result = A2AProxyComponent._create_batched_status_update(
                component, "Batched text", original_event, task_context
            )

        # Verify task IDs are updated to SAM's task ID
        assert result.task_id == "test-task"
        assert result.context_id == "test-session"
        # Verify metadata is preserved
        assert result.metadata == {"custom": "data"}
        # Verify it's not final
        assert result.final is False
        # Verify text message was created
        mock_a2a.create_agent_text_message.assert_called_once_with(
            text="Batched text",
            task_id="test-task",
            context_id="test-session"
        )

    def test_create_batched_event_no_metadata(self):
        """Test creating batched event when original has no metadata."""
        task_context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        original_event = TaskStatusUpdateEvent(
            task_id="downstream-task",
            context_id="downstream-ctx",
            status=TaskStatus(state=TaskState.working),
            final=False,
            metadata=None
        )

        component = MagicMock(spec=A2AProxyComponent)
        mock_message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="Text"))]
        )
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.create_agent_text_message.return_value = mock_message
            result = A2AProxyComponent._create_batched_status_update(
                component, "Text", original_event, task_context
            )

        assert result.metadata is None


class TestFlushRemainingBuffer:
    """Tests for flushing remaining buffer before task cleanup."""

    @pytest.mark.asyncio
    async def test_flush_with_content(self):
        """Test flushing buffer with content publishes event."""
        task_context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        task_context.streaming_buffer = "Remaining content"

        component = MagicMock(spec=A2AProxyComponent)
        component.log_identifier = "[TestProxy]"
        component._publish_status_update = AsyncMock()

        mock_message = Message(
            message_id="msg-1",
            role="agent",
            parts=[Part(root=TextPart(text="Remaining content"))]
        )
        with patch("solace_agent_mesh.agent.proxies.a2a.component.a2a") as mock_a2a:
            mock_a2a.create_agent_text_message.return_value = mock_message
            await A2AProxyComponent._flush_remaining_buffer(
                component, task_context, "test-agent"
            )

        # Verify buffer was flushed
        assert task_context.streaming_buffer == ""
        # Verify event was published
        component._publish_status_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self):
        """Test flushing empty buffer does nothing."""
        task_context = ProxyTaskContext(
            task_id="test-task",
            a2a_context={"session_id": "test-session"}
        )
        task_context.streaming_buffer = ""

        component = MagicMock(spec=A2AProxyComponent)
        component._publish_status_update = AsyncMock()

        await A2AProxyComponent._flush_remaining_buffer(
            component, task_context, "test-agent"
        )

        # Verify no event was published
        component._publish_status_update.assert_not_called()
