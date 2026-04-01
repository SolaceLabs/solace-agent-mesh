"""Unit tests for process_thinking_content_callback."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types as adk_types

from solace_agent_mesh.agent.adk.callbacks import process_thinking_content_callback
from solace_agent_mesh.common.data_parts import ThinkingContentData


def _make_callback_context(thinking_phase_active=False):
    """Create a mock CallbackContext with a2a_context and session state."""
    ctx = MagicMock()
    ctx.state = {"a2a_context": {"task_id": "test-task"}}
    session = MagicMock()
    session.state = {"thinking_phase_active": thinking_phase_active}
    # Wire up _invocation_context.session so get_session_from_callback_context works
    ctx._invocation_context.session = session
    return ctx, session


def _make_llm_response(content_text=None, custom_metadata=None):
    """Create an LlmResponse with optional content and metadata."""
    resp = LlmResponse()
    resp.custom_metadata = custom_metadata
    if content_text is not None:
        resp.content = adk_types.Content(
            role="model",
            parts=[adk_types.Part(text=content_text)],
        )
    else:
        resp.content = None
    return resp


class TestProcessThinkingContentCallback:
    """Tests for process_thinking_content_callback."""

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_returns_none_when_no_custom_metadata(self, mock_publish):
        """Early return when custom_metadata is None."""
        ctx, _ = _make_callback_context()
        resp = _make_llm_response(custom_metadata=None)
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)
        assert result is None
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_returns_none_when_no_a2a_context(self, mock_publish):
        """Early return when a2a_context is missing from state."""
        ctx = MagicMock(spec=CallbackContext)
        ctx.state = {}
        resp = _make_llm_response(custom_metadata={"is_thinking_content": True})
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)
        assert result is None
        mock_publish.assert_not_called()

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_streaming_thinking_chunk_publishes_and_strips(self, mock_publish, mock_get_session):
        """Streaming thinking chunk: publishes data and strips content from response."""
        ctx, session = _make_callback_context()
        mock_get_session.return_value = session
        resp = _make_llm_response(
            content_text="thinking about it...",
            custom_metadata={"is_thinking_content": True},
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        assert result is None
        assert session.state["thinking_phase_active"] is True
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][2]
        assert isinstance(published_data, ThinkingContentData)
        assert published_data.content == "thinking about it..."
        assert published_data.is_complete is False
        # Content should be stripped
        assert len(resp.content.parts) == 0

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_phase_transition_sends_complete_signal(self, mock_publish, mock_get_session):
        """When transitioning from thinking to regular content, sends is_complete signal."""
        ctx, session = _make_callback_context(thinking_phase_active=True)
        mock_get_session.return_value = session
        resp = _make_llm_response(
            content_text="actual response",
            custom_metadata={"is_thinking_content": False},
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        assert result is None
        assert session.state["thinking_phase_active"] is False
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][2]
        assert isinstance(published_data, ThinkingContentData)
        assert published_data.content == ""
        assert published_data.is_complete is True

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_non_streaming_full_thinking_content(self, mock_publish, mock_get_session):
        """Non-streaming: publishes full thinking content with is_complete=True."""
        ctx, session = _make_callback_context()
        mock_get_session.return_value = session
        resp = _make_llm_response(
            custom_metadata={"thinking_content": "full reasoning text"},
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        assert result is None
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][2]
        assert isinstance(published_data, ThinkingContentData)
        assert published_data.content == "full reasoning text"
        assert published_data.is_complete is True
        # Should be removed from metadata
        assert "thinking_content" not in resp.custom_metadata

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_no_double_complete_on_transition_with_full_content(self, mock_publish, mock_get_session):
        """Phase transition should NOT also publish thinking_text_full (elif guard)."""
        ctx, session = _make_callback_context(thinking_phase_active=True)
        mock_get_session.return_value = session
        resp = _make_llm_response(
            content_text="response text",
            custom_metadata={
                "is_thinking_content": False,
                "thinking_content": "full text too",
            },
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        # Should only publish once (the phase transition complete), not twice
        assert mock_publish.call_count == 1
        published_data = mock_publish.call_args[0][2]
        assert published_data.is_complete is True
        assert published_data.content == ""

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_phase_transition_with_null_metadata_sends_complete(self, mock_publish, mock_get_session):
        """Most common real-world case: text chunk after thinking has custom_metadata=None."""
        ctx, session = _make_callback_context(thinking_phase_active=True)
        mock_get_session.return_value = session
        resp = _make_llm_response(
            content_text="actual response text",
            custom_metadata=None,
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        assert result is None
        assert session.state["thinking_phase_active"] is False
        mock_publish.assert_called_once()
        published_data = mock_publish.call_args[0][2]
        assert isinstance(published_data, ThinkingContentData)
        assert published_data.content == ""
        assert published_data.is_complete is True

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.agent.adk.callbacks.get_session_from_callback_context")
    @patch("solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update", new_callable=AsyncMock)
    async def test_no_publish_when_not_thinking_and_no_full_content(self, mock_publish, mock_get_session):
        """No publish when not in thinking phase and no thinking_content."""
        ctx, session = _make_callback_context()
        mock_get_session.return_value = session
        resp = _make_llm_response(
            content_text="normal response",
            custom_metadata={"some_other_key": True},
        )
        host = MagicMock()

        result = await process_thinking_content_callback(ctx, resp, host)

        assert result is None
        mock_publish.assert_not_called()
