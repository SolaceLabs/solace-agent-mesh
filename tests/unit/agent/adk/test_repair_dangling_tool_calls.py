"""
Unit tests for _repair_dangling_tool_calls_in_session in runner.py.

Tests the session-level repair of dangling tool calls (function_call events
with no matching function_response) that can cause the ADK runner to block
indefinitely when the LLM retries stale peer tool calls.

See: Dangling Tool Call Blocking Final Response Delivery
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from google.adk.events import Event as ADKEvent
from google.adk.sessions import Session as ADKSession
from google.genai import types as adk_types

from solace_agent_mesh.agent.adk.runner import (
    _repair_dangling_tool_calls_in_session,
)


def _make_session(events=None, session_id="test-session", user_id="test-user"):
    """Helper to create a mock ADK session with events."""
    session = Mock(spec=ADKSession)
    session.id = session_id
    session.user_id = user_id
    session.app_name = "test-app"
    session.events = events or []
    return session


def _make_component(agent_name="TestAgent"):
    """Helper to create a mock component."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    component.agent_name = agent_name
    component.session_service = AsyncMock()
    return component


def _make_function_call_event(call_id, tool_name, invocation_id="inv-1"):
    """Helper to create an ADK event with a function_call."""
    fc_part = adk_types.Part.from_function_call(
        name=tool_name,
        args={"task_description": "test task"},
    )
    fc_part.function_call.id = call_id
    return ADKEvent(
        invocation_id=invocation_id,
        author="model",
        content=adk_types.Content(role="model", parts=[fc_part]),
    )


def _make_function_response_event(call_id, tool_name, invocation_id="inv-1"):
    """Helper to create an ADK event with a function_response."""
    fr_part = adk_types.Part.from_function_response(
        name=tool_name,
        response={"status": "success", "result": "done"},
    )
    fr_part.function_response.id = call_id
    return ADKEvent(
        invocation_id=invocation_id,
        author="tool",
        content=adk_types.Content(role="tool", parts=[fr_part]),
    )


def _make_text_event(text, role="user", invocation_id="inv-1"):
    """Helper to create a simple text event."""
    return ADKEvent(
        invocation_id=invocation_id,
        author=role,
        content=adk_types.Content(
            role=role,
            parts=[adk_types.Part(text=text)],
        ),
    )


class TestRepairDanglingToolCallsInSession:
    """Tests for _repair_dangling_tool_calls_in_session function."""

    @pytest.mark.asyncio
    async def test_no_events_does_nothing(self):
        """Empty session events should not trigger any repair."""
        component = _make_component()
        session = _make_session(events=[])

        await _repair_dangling_tool_calls_in_session(
            component, session, "task-1"
        )

        # No append_event_with_retry call should be made
        # (the function returns early before importing it)

    @pytest.mark.asyncio
    async def test_none_session_does_nothing(self):
        """None session should not trigger any repair."""
        component = _make_component()

        await _repair_dangling_tool_calls_in_session(
            component, None, "task-1"
        )

    @pytest.mark.asyncio
    async def test_no_dangling_calls_does_nothing(self):
        """Session with matched function_call/response pairs should not trigger repair."""
        component = _make_component()
        events = [
            _make_text_event("Hello"),
            _make_function_call_event("call-1", "peer_TestAgent"),
            _make_function_response_event("call-1", "peer_TestAgent"),
            _make_text_event("Here is the result", role="model"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            # No repair event should be appended since all calls have responses
            mock_append.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_dangling_call_is_repaired(self):
        """A single dangling tool call should be repaired with a synthetic response."""
        component = _make_component()
        events = [
            _make_text_event("Hello"),
            _make_function_call_event("call-1", "peer_JiraConfluenceAgent"),
            # No matching function_response for call-1!
            _make_text_event("New user message"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            # Should have called append_event_with_retry once
            assert mock_append.call_count == 1

            # Verify the repair event
            call_kwargs = mock_append.call_args[1]
            repair_event = call_kwargs["event"]
            assert repair_event.content.role == "tool"
            assert len(repair_event.content.parts) == 1

            repair_part = repair_event.content.parts[0]
            assert repair_part.function_response is not None
            assert repair_part.function_response.id == "call-1"
            assert repair_part.function_response.name == "peer_JiraConfluenceAgent"
            assert "error" in repair_part.function_response.response["status"]
            assert "previous turn" in repair_part.function_response.response["message"]
            assert "Do NOT retry" in repair_part.function_response.response["message"]

    @pytest.mark.asyncio
    async def test_multiple_dangling_calls_are_repaired(self):
        """Multiple dangling tool calls should all be repaired in a single event."""
        component = _make_component()
        events = [
            _make_text_event("Hello"),
            # First dangling call
            _make_function_call_event("call-1", "peer_JiraConfluenceAgent"),
            # Second dangling call (different tool)
            _make_function_call_event("call-2", "peer_SalesforceAgent"),
            # No responses for either!
            _make_text_event("New user message"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            assert mock_append.call_count == 1

            call_kwargs = mock_append.call_args[1]
            repair_event = call_kwargs["event"]
            assert repair_event.content.role == "tool"
            assert len(repair_event.content.parts) == 2

            # Verify both calls are repaired
            repaired_ids = {
                p.function_response.id for p in repair_event.content.parts
            }
            assert repaired_ids == {"call-1", "call-2"}

            repaired_names = {
                p.function_response.name for p in repair_event.content.parts
            }
            assert repaired_names == {
                "peer_JiraConfluenceAgent",
                "peer_SalesforceAgent",
            }

    @pytest.mark.asyncio
    async def test_mixed_matched_and_dangling_calls(self):
        """Only dangling calls should be repaired; matched calls should be left alone."""
        component = _make_component()
        events = [
            _make_text_event("Hello"),
            # Matched call
            _make_function_call_event("call-1", "load_artifact"),
            _make_function_response_event("call-1", "load_artifact"),
            # Dangling call
            _make_function_call_event("call-2", "peer_JiraConfluenceAgent"),
            # No response for call-2!
            _make_text_event("New user message"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            assert mock_append.call_count == 1

            call_kwargs = mock_append.call_args[1]
            repair_event = call_kwargs["event"]
            assert len(repair_event.content.parts) == 1
            assert (
                repair_event.content.parts[0].function_response.id == "call-2"
            )
            assert (
                repair_event.content.parts[0].function_response.name
                == "peer_JiraConfluenceAgent"
            )

    @pytest.mark.asyncio
    async def test_parallel_tool_calls_in_single_event(self):
        """Multiple function_calls in a single event should be handled correctly."""
        component = _make_component()

        # Create an event with multiple function calls (parallel tool calls)
        fc_part_1 = adk_types.Part.from_function_call(
            name="load_artifact",
            args={"filename": "test.png"},
        )
        fc_part_1.function_call.id = "call-1"
        fc_part_2 = adk_types.Part.from_function_call(
            name="peer_MultiModalAgent",
            args={"task_description": "analyze"},
        )
        fc_part_2.function_call.id = "call-2"

        multi_call_event = ADKEvent(
            invocation_id="inv-1",
            author="model",
            content=adk_types.Content(
                role="model", parts=[fc_part_1, fc_part_2]
            ),
        )

        events = [
            _make_text_event("Hello"),
            multi_call_event,
            # Only call-1 has a response
            _make_function_response_event("call-1", "load_artifact"),
            # call-2 is dangling!
            _make_text_event("New user message"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            assert mock_append.call_count == 1

            call_kwargs = mock_append.call_args[1]
            repair_event = call_kwargs["event"]
            assert len(repair_event.content.parts) == 1
            assert (
                repair_event.content.parts[0].function_response.id == "call-2"
            )
            assert (
                repair_event.content.parts[0].function_response.name
                == "peer_MultiModalAgent"
            )

    @pytest.mark.asyncio
    async def test_append_failure_is_logged_not_raised(self):
        """If appending the repair event fails, the error should be logged but not raised."""
        component = _make_component()
        events = [
            _make_function_call_event("call-1", "peer_TestAgent"),
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection failed"),
        ):
            # Should not raise
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

    @pytest.mark.asyncio
    async def test_events_with_no_content_are_skipped(self):
        """Events with no content should be safely skipped."""
        component = _make_component()
        events = [
            ADKEvent(invocation_id="inv-1", author="system"),  # No content
            _make_function_call_event("call-1", "peer_TestAgent"),
            ADKEvent(invocation_id="inv-2", author="system"),  # No content
        ]
        session = _make_session(events=events)

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            # call-1 is dangling, should be repaired
            assert mock_append.call_count == 1

    @pytest.mark.asyncio
    async def test_repair_event_uses_correct_session_params(self):
        """The repair event should be appended with correct session parameters."""
        component = _make_component(agent_name="OrchestratorAgent")
        events = [
            _make_function_call_event("call-1", "peer_TestAgent"),
        ]
        session = _make_session(
            events=events,
            session_id="session-abc",
            user_id="user-xyz",
        )

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-42"
            )

            call_kwargs = mock_append.call_args[1]
            assert call_kwargs["app_name"] == "OrchestratorAgent"
            assert call_kwargs["user_id"] == "user-xyz"
            assert call_kwargs["session_id"] == "session-abc"
            assert call_kwargs["session"] is session

    @pytest.mark.asyncio
    async def test_function_call_without_id_is_skipped(self):
        """Function calls without an ID should be safely skipped."""
        component = _make_component()

        # Create a function call part without an ID
        fc_part = adk_types.Part.from_function_call(
            name="test_tool",
            args={},
        )
        fc_part.function_call.id = None  # No ID

        event = ADKEvent(
            invocation_id="inv-1",
            author="model",
            content=adk_types.Content(role="model", parts=[fc_part]),
        )
        session = _make_session(events=[event])

        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            new_callable=AsyncMock,
        ) as mock_append:
            await _repair_dangling_tool_calls_in_session(
                component, session, "task-1"
            )

            # No repair needed since the call has no ID
            mock_append.assert_not_called()
