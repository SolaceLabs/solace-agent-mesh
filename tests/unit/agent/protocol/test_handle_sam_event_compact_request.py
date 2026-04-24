"""Unit tests for handle_sam_event's session.compact_request branch.

Covers the trust boundary and input clamping:
- Rejects events with missing ``gateway_id`` or non-gateway ``source_component``.
- Clamps ``compaction_percentage`` to [0.1, 0.9].
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_component(agent_name: str = "myagent"):
    component = MagicMock()
    component.log_identifier = "[TEST]"
    component.get_config.side_effect = lambda key: (
        agent_name if key == "agent_name" else None
    )
    return component


def _make_message(payload):
    msg = MagicMock()
    msg.get_payload.return_value = payload
    return msg


def _compact_request_payload(**overrides):
    data = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "agent_id": "myagent",
        "correlation_id": "corr-1",
        "compaction_percentage": 0.25,
        "gateway_id": "test-gateway",
    }
    data.update(overrides.pop("data", {}))
    payload = {
        "event_type": "session.compact_request",
        "source_component": "test_gateway",
        "data": data,
    }
    payload.update(overrides)
    return payload


def test_rejects_when_gateway_id_missing():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(data={"gateway_id": None})
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_create_task:
        handle_sam_event(component, message, "topic")

    mock_create_task.assert_not_called()
    message.call_acknowledgements.assert_called()


def test_rejects_when_source_component_does_not_end_with_gateway():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(source_component="some_agent")
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_create_task:
        handle_sam_event(component, message, "topic")

    mock_create_task.assert_not_called()
    message.call_acknowledgements.assert_called()


def test_rejects_when_source_component_not_string():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(source_component=None)
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_create_task:
        handle_sam_event(component, message, "topic")

    mock_create_task.assert_not_called()


def test_clamps_percentage_above_upper_bound():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(data={"compaction_percentage": 9.9})
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_create_task, patch(
        "solace_agent_mesh.agent.protocol.event_handlers.handle_compact_session"
    ) as mock_handle:
        handle_sam_event(component, message, "topic")

    # The coroutine returned by handle_compact_session is passed to create_task;
    # inspect the kwargs we passed.
    mock_handle.assert_called_once()
    call = mock_handle.call_args
    # Positional args: (component, session_id, user_id, correlation_id, pct)
    assert call.args[-1] == pytest.approx(0.9)
    mock_create_task.assert_called_once()


def test_clamps_percentage_below_lower_bound():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(data={"compaction_percentage": -1.0})
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ), patch(
        "solace_agent_mesh.agent.protocol.event_handlers.handle_compact_session"
    ) as mock_handle:
        handle_sam_event(component, message, "topic")

    mock_handle.assert_called_once()
    assert mock_handle.call_args.args[-1] == pytest.approx(0.1)


def test_non_numeric_percentage_falls_back_to_default():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component()
    payload = _compact_request_payload(data={"compaction_percentage": "not-a-number"})
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ), patch(
        "solace_agent_mesh.agent.protocol.event_handlers.handle_compact_session"
    ) as mock_handle:
        handle_sam_event(component, message, "topic")

    mock_handle.assert_called_once()
    assert mock_handle.call_args.args[-1] == pytest.approx(0.25)


def test_ignores_request_for_different_agent():
    from solace_agent_mesh.agent.protocol.event_handlers import handle_sam_event

    component = _make_component(agent_name="otheragent")
    payload = _compact_request_payload()
    message = _make_message(payload)

    with patch(
        "solace_agent_mesh.agent.protocol.event_handlers.asyncio.create_task"
    ) as mock_create_task:
        handle_sam_event(component, message, "topic")

    mock_create_task.assert_not_called()
