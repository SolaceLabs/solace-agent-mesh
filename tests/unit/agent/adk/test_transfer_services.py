"""Tests for cross-agent context transfer service functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from google.adk.events import Event as ADKEvent
from google.genai import types as adk_types

from solace_agent_mesh.agent.adk.services import (
    _extract_compaction_summary,
    _filter_events_for_transfer,
    extract_session_text_for_transfer,
    transfer_session_context,
)


# --- Helpers ---


def _make_text_event(role: str, text: str, author: str = "user") -> ADKEvent:
    return ADKEvent(
        invocation_id="inv-1",
        author=author,
        content=adk_types.Content(
            role=role,
            parts=[adk_types.Part(text=text)],
        ),
    )


def _make_function_call_event() -> ADKEvent:
    """Event with only a function_call part (no text)."""
    part = MagicMock()
    part.text = None
    part.function_call = MagicMock()
    del part.text  # hasattr(part, "text") will return False
    return ADKEvent(
        invocation_id="inv-fc",
        author="model",
        content=adk_types.Content(
            role="model",
            parts=[part],
        ),
    )


def _make_mixed_event(text: str) -> ADKEvent:
    """Event with both a text part and a function_call part."""
    text_part = adk_types.Part(text=text)
    fc_part = MagicMock()
    fc_part.text = None
    del fc_part.text
    return ADKEvent(
        invocation_id="inv-mixed",
        author="model",
        content=adk_types.Content(
            role="model",
            parts=[text_part, fc_part],
        ),
    )


def _make_compaction_event(summary_text: str) -> ADKEvent:
    event = MagicMock(spec=ADKEvent)
    event.actions = MagicMock()
    event.actions.compaction = {
        "compacted_content": {
            "parts": [{"text": summary_text}],
        },
    }
    event.content = None
    return event


def _make_no_content_event() -> ADKEvent:
    return ADKEvent(
        invocation_id="inv-empty",
        author="system",
        content=None,
    )


# --- _filter_events_for_transfer ---


class TestFilterEventsForTransfer:
    def test_keeps_user_text_events(self):
        events = [_make_text_event("user", "Hello")]
        result = _filter_events_for_transfer(events)
        assert len(result) == 1
        assert result[0].content.parts[0].text == "Hello"

    def test_keeps_model_text_events(self):
        events = [_make_text_event("model", "Hi there", author="model")]
        result = _filter_events_for_transfer(events)
        assert len(result) == 1

    def test_removes_function_call_only_events(self):
        events = [_make_function_call_event()]
        result = _filter_events_for_transfer(events)
        assert len(result) == 0

    def test_strips_function_call_parts_keeps_text(self):
        events = [_make_mixed_event("Some text")]
        result = _filter_events_for_transfer(events)
        assert len(result) == 1
        # Only text part should remain
        assert len(result[0].content.parts) == 1
        assert result[0].content.parts[0].text == "Some text"

    def test_removes_no_content_events(self):
        events = [_make_no_content_event()]
        result = _filter_events_for_transfer(events)
        assert len(result) == 0

    def test_removes_non_user_model_roles(self):
        event = ADKEvent(
            invocation_id="inv-sys",
            author="system",
            content=adk_types.Content(
                role="system",
                parts=[adk_types.Part(text="System prompt")],
            ),
        )
        result = _filter_events_for_transfer([event])
        assert len(result) == 0

    def test_keeps_compaction_events(self):
        events = [_make_compaction_event("Summary")]
        result = _filter_events_for_transfer(events)
        assert len(result) == 1

    def test_keeps_state_delta_event_with_text(self):
        """Issue #1: state_delta events with text content should be kept."""
        event = ADKEvent(
            invocation_id="inv-sd",
            author="model",
            content=adk_types.Content(
                role="model",
                parts=[adk_types.Part(text="Some text alongside state delta")],
            ),
        )
        event.actions = MagicMock()
        event.actions.state_delta = {"key": "value"}
        event.actions.compaction = None
        result = _filter_events_for_transfer([event])
        assert len(result) == 1
        assert result[0].content.parts[0].text == "Some text alongside state delta"

    def test_empty_events_list(self):
        result = _filter_events_for_transfer([])
        assert result == []

    def test_mixed_events_ordering_preserved(self):
        events = [
            _make_text_event("user", "First"),
            _make_function_call_event(),
            _make_text_event("model", "Second", author="model"),
            _make_no_content_event(),
            _make_text_event("user", "Third"),
        ]
        result = _filter_events_for_transfer(events)
        assert len(result) == 3
        assert result[0].content.parts[0].text == "First"
        assert result[1].content.parts[0].text == "Second"
        assert result[2].content.parts[0].text == "Third"


# --- extract_session_text_for_transfer ---


class TestExtractSessionTextForTransfer:
    def test_returns_none_for_no_session(self):
        assert extract_session_text_for_transfer(None) is None

    def test_returns_none_for_empty_events(self):
        session = MagicMock()
        session.events = []
        assert extract_session_text_for_transfer(session) is None

    def test_basic_transcript(self):
        session = MagicMock()
        session.events = [
            _make_text_event("user", "What is 2+2?"),
            _make_text_event("model", "4", author="model"),
        ]
        result = extract_session_text_for_transfer(session, source_agent_display_name="Math Agent")
        assert result is not None
        assert "User: What is 2+2?" in result
        assert "Assistant: 4" in result
        assert "[Context from previous conversation with Math Agent]" in result
        assert "[End of previous context]" in result

    def test_filters_out_tool_only_events(self):
        session = MagicMock()
        session.events = [
            _make_text_event("user", "Hello"),
            _make_function_call_event(),
            _make_text_event("model", "Hi", author="model"),
        ]
        result = extract_session_text_for_transfer(session)
        assert result is not None
        assert "User: Hello" in result
        assert "Assistant: Hi" in result
        # No function call content should appear
        assert "function" not in result.lower()

    def test_includes_compaction_summary(self):
        session = MagicMock()
        session.events = [
            _make_compaction_event("Earlier they discussed weather"),
            _make_text_event("user", "Follow up question"),
        ]
        result = extract_session_text_for_transfer(session)
        assert result is not None
        assert "[Summary of earlier conversation]" in result
        assert "Earlier they discussed weather" in result
        assert "[Recent conversation]" in result
        assert "User: Follow up question" in result

    def test_returns_none_when_only_tool_events(self):
        session = MagicMock()
        session.events = [_make_function_call_event(), _make_no_content_event()]
        assert extract_session_text_for_transfer(session) is None


# --- transfer_session_context ---


class TestTransferSessionContext:
    @pytest.fixture
    def mock_session_service(self):
        service = MagicMock()
        service.get_session = AsyncMock()
        service.create_session = AsyncMock()
        service.append_event = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_returns_false_when_no_source_session(self, mock_session_service):
        mock_session_service.get_session.return_value = None
        result = await transfer_session_context(
            session_service=mock_session_service,
            source_agent_name="agent-a",
            target_agent_name="agent-b",
            user_id="user1",
            session_id="sess1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_source_has_no_events(self, mock_session_service):
        source = MagicMock()
        source.events = []
        mock_session_service.get_session.return_value = source
        result = await transfer_session_context(
            session_service=mock_session_service,
            source_agent_name="agent-a",
            target_agent_name="agent-b",
            user_id="user1",
            session_id="sess1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_only_tool_events(self, mock_session_service):
        source = MagicMock()
        source.events = [_make_function_call_event()]
        mock_session_service.get_session.return_value = source
        result = await transfer_session_context(
            session_service=mock_session_service,
            source_agent_name="agent-a",
            target_agent_name="agent-b",
            user_id="user1",
            session_id="sess1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_successful_transfer(self, mock_session_service):
        source = MagicMock()
        source.events = [_make_text_event("user", "Hello")]
        source.state = {}

        target = MagicMock()
        target.id = "sess1"
        target.user_id = "user1"

        # First call returns source, second returns target
        mock_session_service.get_session.side_effect = [source, target]

        mock_append = AsyncMock()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.agent.adk.services.append_event_with_retry",
                mock_append,
            )
            result = await transfer_session_context(
                session_service=mock_session_service,
                source_agent_name="agent-a",
                target_agent_name="agent-b",
                user_id="user1",
                session_id="sess1",
                source_agent_display_name="Agent A",
            )
        assert result is True

        # First call is the context marker event
        marker_call = mock_append.call_args_list[0]
        marker_event = marker_call.kwargs.get("event") or marker_call[1].get("event")
        assert "Agent A" in marker_event.content.parts[0].text

        # Subsequent calls are the cloned source events
        cloned_call = mock_append.call_args_list[1]
        cloned_event = cloned_call.kwargs.get("event") or cloned_call[1].get("event")
        assert cloned_event.content.parts[0].text == "Hello"

    @pytest.mark.asyncio
    async def test_creates_target_session_if_not_exists(self, mock_session_service):
        source = MagicMock()
        source.events = [_make_text_event("user", "Hello")]
        source.state = {"key": "val", "compaction_time": 123}

        new_target = MagicMock()
        new_target.id = "sess1"
        new_target.user_id = "user1"

        # get_session: source found, target not found
        mock_session_service.get_session.side_effect = [source, None]
        mock_session_service.create_session.return_value = new_target

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.agent.adk.services.append_event_with_retry",
                AsyncMock(),
            )
            result = await transfer_session_context(
                session_service=mock_session_service,
                source_agent_name="agent-a",
                target_agent_name="agent-b",
                user_id="user1",
                session_id="sess1",
            )

        assert result is True
        mock_session_service.create_session.assert_called_once()
        create_kwargs = mock_session_service.create_session.call_args
        passed_state = create_kwargs.kwargs.get("state") or create_kwargs[1].get("state")
        assert passed_state == {"key": "val"}
        assert "compaction_time" not in passed_state

    @pytest.mark.asyncio
    async def test_race_condition_create_falls_back_to_get(self, mock_session_service):
        """Issue #9a: create_session raises, falls back to get_session."""
        source = MagicMock()
        source.events = [_make_text_event("user", "Hello")]
        source.state = {}

        target = MagicMock()
        target.id = "sess1"
        target.user_id = "user1"

        # get_session: source found, target not found, then found on retry
        mock_session_service.get_session.side_effect = [source, None, target]
        mock_session_service.create_session.side_effect = RuntimeError("duplicate key")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.agent.adk.services.append_event_with_retry",
                AsyncMock(),
            )
            result = await transfer_session_context(
                session_service=mock_session_service,
                source_agent_name="agent-a",
                target_agent_name="agent-b",
                user_id="user1",
                session_id="sess1",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_marker_event_failure_returns_false(self, mock_session_service):
        """Issue #9b: append_event_with_retry raises on marker event."""
        source = MagicMock()
        source.events = [_make_text_event("user", "Hello")]
        source.state = {}

        target = MagicMock()
        target.id = "sess1"
        target.user_id = "user1"

        mock_session_service.get_session.side_effect = [source, target]

        mock_append = AsyncMock(side_effect=RuntimeError("DB error"))
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "solace_agent_mesh.agent.adk.services.append_event_with_retry",
                mock_append,
            )
            result = await transfer_session_context(
                session_service=mock_session_service,
                source_agent_name="agent-a",
                target_agent_name="agent-b",
                user_id="user1",
                session_id="sess1",
            )

        assert result is False


# --- _extract_compaction_summary ---


class TestExtractCompactionSummary:
    def test_object_form_extraction(self):
        """Issue #8: test object/attribute branch of _extract_compaction_summary."""
        part = MagicMock()
        part.text = "Summary from object form"

        cc = MagicMock()
        cc.parts = [part]

        compaction = MagicMock()
        compaction.compacted_content = cc

        event = MagicMock()
        event.actions = MagicMock()
        event.actions.compaction = compaction

        result = _extract_compaction_summary(event)
        assert result == "Summary from object form"

    def test_object_form_no_text(self):
        part = MagicMock()
        part.text = ""

        cc = MagicMock()
        cc.parts = [part]

        compaction = MagicMock()
        compaction.compacted_content = cc

        event = MagicMock()
        event.actions = MagicMock()
        event.actions.compaction = compaction

        result = _extract_compaction_summary(event)
        assert result is None
