"""Regression tests for the SSE visualization filter + fan-out path.

These tests pin the DATAGO incident fix (DATAGO-133967): under high-fan-out
tasks the gateway used to build+serialize the viz payload once per subscriber
and skip excluded payloads only after dumping/parsing them. The loop now
short-circuits excluded payloads and serializes once per A2A message.

The tests use ``object.__new__(WebUIBackendComponent)`` plus minimal stubs so
they can exercise the loop body without spinning up the heavy component
__init__ (FastAPI/uvicorn/SAC App/etc).
"""

from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.gateway.http_sse import component as component_module
from solace_agent_mesh.gateway.http_sse.component import (
    WebUIBackendComponent,
    _should_include_for_visualization,
)


# ─────────────────────────────────────────────────────────────────────────────
# Issue 3: unit tests for _should_include_for_visualization
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not-a-dict",
        123,
        [],
        {},  # missing params
        {"params": "not-a-dict"},
        {"params": {}},  # missing message
        {"params": {"message": "not-a-dict"}},
        {"params": {"message": {}}},  # missing metadata
        {"params": {"message": {"metadata": "not-a-dict"}}},
        {"params": {"message": {"metadata": {}}}},  # absent visualization key
        {"params": {"message": {"metadata": {"visualization": True}}}},
        {"params": {"message": {"metadata": {"visualization": "true"}}}},
        {"params": {"message": {"metadata": {"visualization": "TRUE"}}}},
        {"params": {"message": {"metadata": {"visualization": 0}}}},  # non-str/bool
        {"params": {"message": {"metadata": {"visualization": None}}}},
    ],
)
def test_should_include_returns_true_when_not_explicitly_excluded(payload):
    assert _should_include_for_visualization(payload) is True


@pytest.mark.parametrize(
    "setting",
    ["false", "False", "FALSE", "FaLsE"],
)
def test_should_include_returns_false_for_string_false_case_insensitive(setting):
    payload = {"params": {"message": {"metadata": {"visualization": setting}}}}
    assert _should_include_for_visualization(payload) is False


def test_should_include_returns_false_for_boolean_false():
    payload = {"params": {"message": {"metadata": {"visualization": False}}}}
    assert _should_include_for_visualization(payload) is False


# ─────────────────────────────────────────────────────────────────────────────
# Loop-test scaffolding
# ─────────────────────────────────────────────────────────────────────────────


def _make_loop_stub(streams: dict | None = None):
    """Build a minimal WebUIBackendComponent stub for the viz processor loop."""
    holder = object.__new__(WebUIBackendComponent)
    holder.log_identifier = "[TEST]"
    holder._visualization_message_queue = asyncio.Queue()
    holder._active_visualization_streams = streams or {}
    holder._viz_stream_drop_counts = {}
    holder._visualization_locks_lock = threading.Lock()
    holder._visualization_locks = {}

    holder.stop_signal = MagicMock()
    holder.stop_signal.is_set.return_value = False

    holder.task_context_manager = MagicMock()
    holder.task_context_manager.get_context.return_value = None

    holder._infer_visualization_event_details = MagicMock(
        return_value={
            "direction": "request",
            "source_entity": "client",
            "target_entity": "agent",
            "debug_type": "a2a",
            "message_id": "m1",
            "task_id": None,
            "payload_summary": {"method": "test", "params_preview": None},
        }
    )

    return holder


def _make_stream(topic: str) -> dict:
    """Stream config that subscribes to `topic` exactly (no wildcards)."""
    return {
        "user_id": "user-1",
        "abstract_targets": [
            SimpleNamespace(status="subscribed", type="namespace_a2a_messages")
        ],
        "solace_topics": {topic},
        "sse_queue": asyncio.Queue(maxsize=10),
    }


async def _run_loop_with_msgs(holder, msgs):
    """Push msgs (then a None sentinel) and run the loop until it exits."""
    for m in msgs:
        await holder._visualization_message_queue.put(m)
    await holder._visualization_message_queue.put(None)
    await WebUIBackendComponent._visualization_message_processor_loop(holder)


# ─────────────────────────────────────────────────────────────────────────────
# Issue 1: behavioral test for early-`continue` short-circuit
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_excluded_payload_skips_all_streams_included_payload_reaches_them():
    """Excluded payloads (visualization=false) must not enqueue to ANY stream;
    a non-excluded payload routed to the same stream MUST reach it. This pins
    the DATAGO regression fix at component.py:1118."""
    topic = "test/topic"
    stream = _make_stream(topic)
    holder = _make_loop_stub({"s1": stream})

    excluded_payload = {
        "params": {"message": {"metadata": {"visualization": "false"}}}
    }
    included_payload = {
        "params": {"message": {"metadata": {"visualization": "true"}}}
    }

    await _run_loop_with_msgs(
        holder,
        [
            {"topic": topic, "payload": excluded_payload},
            {"topic": topic, "payload": included_payload},
        ],
    )

    # Exactly one viz_msg should have been enqueued (the included one).
    assert stream["sse_queue"].qsize() == 1
    enqueued = stream["sse_queue"].get_nowait()
    assert enqueued["event"] == "a2a_message"
    parsed = json.loads(enqueued["data"])
    assert parsed["full_payload"] is included_payload


# ─────────────────────────────────────────────────────────────────────────────
# Issue 2: serialize-once-then-fan-out test
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_json_dumps_called_once_per_message_for_n_streams():
    """With ≥2 eligible streams, json.dumps must run exactly once per A2A
    message (NOT once per stream). Pins the fan-out optimization at
    component.py:1124-1149 — a regression here would silently bring back the
    O(streams × payload_size) CPU cost that overflowed per-stream queues."""
    topic = "test/topic"
    streams = {
        "s1": _make_stream(topic),
        "s2": _make_stream(topic),
        "s3": _make_stream(topic),
    }
    holder = _make_loop_stub(streams)

    payload = {"params": {"message": {"metadata": {}}}}

    real_dumps = json.dumps
    with patch.object(
        component_module.json, "dumps", side_effect=real_dumps
    ) as dumps_spy:
        await _run_loop_with_msgs(
            holder, [{"topic": topic, "payload": payload}]
        )

    # Exactly one serialization for the single A2A message, regardless of
    # how many streams it fans out to.
    assert dumps_spy.call_count == 1

    # And every eligible stream got the SAME viz_msg dict.
    msgs = [streams[sid]["sse_queue"].get_nowait() for sid in ("s1", "s2", "s3")]
    assert all(m == msgs[0] for m in msgs)
    # All streams share the same object instance — confirms a single build,
    # not three identical-but-separate dicts.
    assert msgs[0] is msgs[1] is msgs[2]


# ─────────────────────────────────────────────────────────────────────────────
# Issue 4: serialization-failure branch
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_serialization_failure_skips_streams_and_continues_loop():
    """A non-JSON-serializable payload (set, etc.) must raise TypeError inside
    json.dumps, be caught by the narrow (TypeError, ValueError) handler, and
    cause the loop to skip ALL streams for THAT message but continue to the
    next event. Pins component.py:1144-1149."""
    topic = "test/topic"
    stream = _make_stream(topic)
    holder = _make_loop_stub({"s1": stream})

    # `set` is not JSON-serializable → json.dumps raises TypeError.
    bad_payload = {
        "params": {"message": {"metadata": {}}},
        "extra": {1, 2, 3},
    }
    good_payload = {"params": {"message": {"metadata": {}}}}

    await _run_loop_with_msgs(
        holder,
        [
            {"topic": topic, "payload": bad_payload},
            {"topic": topic, "payload": good_payload},
        ],
    )

    # Only the good payload should have been delivered; the bad one is dropped.
    assert stream["sse_queue"].qsize() == 1
    delivered = stream["sse_queue"].get_nowait()
    parsed = json.loads(delivered["data"])
    assert parsed["full_payload"] is good_payload
