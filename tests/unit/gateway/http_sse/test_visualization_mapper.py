"""Tests for the pure `infer_visualization_event_details` mapper.

The mapping logic was extracted from `WebUIBackendComponent` so non-component
callers (notably the eval pipeline) can produce visualization payloads with
the exact same shape chat streams over SSE. These tests pin the contract of
the standalone function — the existing chat-flow tests in
`test_viz_serialization_and_filter.py` cover the in-component delegation.
"""

from __future__ import annotations

from solace_agent_mesh.gateway.http_sse.visualization_mapper import (
    infer_visualization_event_details,
)


_BASE_KEYS = {
    "direction",
    "source_entity",
    "target_entity",
    "debug_type",
    "message_id",
    "task_id",
    "payload_summary",
}


def test_returns_full_detail_shape_with_payload_summary():
    """Every call must return the full detail dict with a payload_summary."""
    result = infer_visualization_event_details("ns/a2a/v1/agent/request/foo", {})
    assert _BASE_KEYS.issubset(result.keys())
    assert "method" in result["payload_summary"]
    assert "params_preview" in result["payload_summary"]


def test_sam_event_short_circuits_with_system_direction():
    payload = {
        "event_type": "agent_started",
        "source_component": "scheduler",
    }
    result = infer_visualization_event_details("any/topic", payload)
    assert result["direction"] == "system_event"
    assert result["debug_type"] == "sam_event"
    assert result["source_entity"] == "scheduler"
    assert result["target_entity"] == "system"
    assert result["payload_summary"]["method"] == "agent_started"


def test_unparseable_payload_falls_back_to_topic_for_request():
    """When the payload can't be parsed as A2A, topic words drive direction."""
    result = infer_visualization_event_details(
        "ns/a2a/v1/agent/request/foo", {"id": "abc"}
    )
    assert result["direction"] == "request"


def test_unparseable_payload_falls_back_to_topic_for_response():
    result = infer_visualization_event_details(
        "ns/a2a/v1/agent/response/foo", {"id": "abc"}
    )
    assert result["direction"] == "response"


def test_unparseable_payload_falls_back_to_topic_for_status():
    result = infer_visualization_event_details(
        "ns/a2a/v1/agent/status/foo", {"id": "abc"}
    )
    assert result["direction"] == "status_update"


def test_payload_summary_truncates_long_strings():
    """params_preview is capped at 100 chars + ellipsis to keep SSE frames small."""
    big = {"params": "x" * 500}
    result = infer_visualization_event_details("any/topic", big)
    preview = result["payload_summary"]["params_preview"]
    assert preview is not None
    assert preview.endswith("...")
    assert len(preview) <= 103  # 100 + "..."


def test_unparseable_summary_marks_serialization_failure_gracefully():
    """If payload contents can't be json-dumped, we still return a string preview."""

    class NotSerializable:
        pass

    result = infer_visualization_event_details(
        "any/topic", {"params": NotSerializable()}
    )
    assert result["payload_summary"]["params_preview"] == "[Could not serialize payload]"
