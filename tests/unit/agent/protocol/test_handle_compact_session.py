"""Unit tests for handle_compact_session in event_handlers.py.

Exercises the async compaction handler that runs after a gateway's
``session.compact_request`` event is accepted. Covers the success path,
early exits (session missing, no events, nothing to compact), summary
truncation, exception handling, and the remaining-token calculation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solace_agent_mesh.agent.protocol.event_handlers import (
    handle_compact_session,
    handle_sam_event,
)


def _make_component(agent_name: str = "myagent", namespace: str = "ns1"):
    component = MagicMock()
    component.log_identifier = "[TEST]"
    component.get_config.side_effect = lambda key: {
        "agent_name": agent_name,
        "namespace": namespace,
    }.get(key)
    component.publish_a2a_message = MagicMock()

    # Real asyncio.Lock so `async with lock:` works
    lock = asyncio.Lock()
    component.session_compaction_state = MagicMock()
    component.session_compaction_state.get_lock = AsyncMock(return_value=lock)

    component.session_service = MagicMock()
    component.session_service.get_session = AsyncMock()

    # adk_agent.model as a bare string exercises the ``else str(...)`` branch
    component.adk_agent = MagicMock()
    component.adk_agent.model = "gpt-4o"
    return component


def _make_event(is_compaction: bool = False):
    ev = MagicMock()
    ev.actions = MagicMock()
    ev.actions.compaction = True if is_compaction else None
    return ev


def _published_response(component):
    """Return (payload, topic) of the single publish_a2a_message call."""
    assert component.publish_a2a_message.call_count == 1
    args, _ = component.publish_a2a_message.call_args
    return args[0], args[1]


@pytest.mark.asyncio
async def test_success_publishes_response_with_tokens_and_counts():
    component = _make_component()
    pre_events = [_make_event(), _make_event()]
    post_events = [_make_event(is_compaction=True), _make_event(), _make_event()]

    pre_session = MagicMock(id="s1", events=pre_events)
    post_session = MagicMock(id="s1", events=post_events)
    component.session_service.get_session.side_effect = [pre_session, post_session]

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event",
        new=AsyncMock(return_value=(3, "a summary", 120, 45)),
    ), patch(
        "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
        side_effect=lambda s, log_identifier="": s,
    ), patch(
        "solace_agent_mesh.agent.adk.runner.calculate_session_context_tokens",
        return_value=777,
    ) as mock_calc_tokens:
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    payload, topic = _published_response(component)
    assert payload["event_type"] == "session.compact_response"
    assert topic.endswith("session/compact_response")
    data = payload["data"]
    assert data["success"] is True
    assert data["events_compacted"] == 3
    assert data["summary"] == "a summary"
    assert data["remaining_events"] == 3
    assert data["remaining_tokens"] == 777
    assert data["compaction_prompt_tokens"] == 120
    assert data["compaction_completion_tokens"] == 45
    assert data["correlation_id"] == "corr-1"
    assert data["error_message"] is None

    # Compaction-flagged events must be excluded from the token calculation
    passed_events = mock_calc_tokens.call_args.args[0]
    assert len(passed_events) == 2
    assert all(e.actions.compaction is None for e in passed_events)
    assert mock_calc_tokens.call_args.kwargs["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_session_not_found_publishes_failure():
    component = _make_component()
    component.session_service.get_session = AsyncMock(return_value=None)

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event"
    ) as mock_create:
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    mock_create.assert_not_called()
    payload, _ = _published_response(component)
    assert payload["data"]["success"] is False
    assert "not found" in payload["data"]["error_message"].lower()


@pytest.mark.asyncio
async def test_empty_events_publishes_failure():
    component = _make_component()
    component.session_service.get_session = AsyncMock(
        return_value=MagicMock(events=[])
    )

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event"
    ) as mock_create:
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    mock_create.assert_not_called()
    payload, _ = _published_response(component)
    assert payload["data"]["success"] is False


@pytest.mark.asyncio
async def test_zero_events_compacted_publishes_not_enough_turns():
    component = _make_component()
    component.session_service.get_session = AsyncMock(
        return_value=MagicMock(events=[_make_event()])
    )

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event",
        new=AsyncMock(return_value=(0, "", 0, 0)),
    ):
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    payload, _ = _published_response(component)
    assert payload["data"]["success"] is False
    assert "turns" in payload["data"]["error_message"].lower()


@pytest.mark.asyncio
async def test_summary_truncated_to_500_chars():
    component = _make_component()
    long_summary = "x" * 1000
    pre = MagicMock(events=[_make_event()])
    post = MagicMock(events=[_make_event()])
    component.session_service.get_session = AsyncMock(side_effect=[pre, post])

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event",
        new=AsyncMock(return_value=(2, long_summary, 10, 5)),
    ), patch(
        "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
        side_effect=lambda s, log_identifier="": s,
    ), patch(
        "solace_agent_mesh.agent.adk.runner.calculate_session_context_tokens",
        return_value=10,
    ):
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    payload, _ = _published_response(component)
    assert len(payload["data"]["summary"]) == 500


@pytest.mark.asyncio
async def test_exception_during_compaction_publishes_failure():
    component = _make_component()
    component.session_service.get_session = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    payload, _ = _published_response(component)
    assert payload["data"]["success"] is False
    assert "boom" in payload["data"]["error_message"]


@pytest.mark.asyncio
async def test_model_object_with_model_attr_used_for_token_calc():
    component = _make_component()
    model_obj = MagicMock()
    model_obj.model = "claude-opus"
    component.adk_agent.model = model_obj

    pre = MagicMock(events=[_make_event()])
    post = MagicMock(events=[_make_event()])
    component.session_service.get_session = AsyncMock(side_effect=[pre, post])

    with patch(
        "solace_agent_mesh.agent.adk.runner.create_compaction_event",
        new=AsyncMock(return_value=(1, "s", 0, 0)),
    ), patch(
        "solace_agent_mesh.agent.adk.services._filter_session_by_latest_compaction",
        side_effect=lambda s, log_identifier="": s,
    ), patch(
        "solace_agent_mesh.agent.adk.runner.calculate_session_context_tokens",
        return_value=42,
    ) as mock_calc:
        await handle_compact_session(component, "s1", "u1", "corr-1", 0.3)

    assert mock_calc.call_args.kwargs["model"] == "claude-opus"


# ---------------------------------------------------------------------------
# Additional handle_sam_event coverage for the compact_request branch
# ---------------------------------------------------------------------------


def _make_sync_component(agent_name: str = "myagent"):
    c = MagicMock()
    c.log_identifier = "[TEST]"
    c.get_config.side_effect = lambda key: agent_name if key == "agent_name" else None
    return c


def _make_message(payload):
    m = MagicMock()
    m.get_payload.return_value = payload
    return m


def _request_payload(**data_overrides):
    data = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "agent_id": "myagent",
        "correlation_id": "corr-1",
        "compaction_percentage": 0.25,
        "gateway_id": "gw-1",
    }
    data.update(data_overrides)
    return {
        "event_type": "session.compact_request",
        "source_component": "test_gateway",
        "data": data,
    }


@pytest.mark.parametrize(
    "missing_key",
    ["session_id", "user_id", "agent_id", "correlation_id"],
)
def test_missing_required_field_rejected(missing_key):
    component = _make_sync_component()
    message = _make_message(_request_payload(**{missing_key: None}))

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_task, patch(
        "solace_agent_mesh.agent.protocol.event_handlers.handle_compact_session"
    ) as mock_handle:
        handle_sam_event(component, message, "topic")

    mock_task.assert_not_called()
    mock_handle.assert_not_called()
    message.call_acknowledgements.assert_called()


def test_valid_request_schedules_handle_compact_session():
    component = _make_sync_component()
    message = _make_message(_request_payload())

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_task, patch(
        "solace_agent_mesh.agent.protocol.event_handlers.handle_compact_session"
    ) as mock_handle:
        handle_sam_event(component, message, "topic")

    mock_handle.assert_called_once()
    args = mock_handle.call_args.args
    assert args[0] is component
    assert args[1] == "sess-1"
    assert args[2] == "user-1"
    assert args[3] == "corr-1"
    assert args[4] == pytest.approx(0.25)
    mock_task.assert_called_once()
