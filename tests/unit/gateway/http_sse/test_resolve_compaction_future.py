"""Unit tests for WebUIBackendComponent.resolve_compaction_future.

These tests cover the agent-id mismatch guard: a spoofed/duplicate
``session.compact_response`` whose ``source_component`` doesn't match the
registered ``expected_agent_id`` must NOT resolve the pending future, and
must NOT pop the entry (so a legitimate response can still resolve it).
"""

import asyncio

import pytest

from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


class _Holder:
    """Minimal host object exposing the attributes the method reads."""

    def __init__(self):
        self._compaction_futures = {}
        self.log_identifier = "[TEST]"


def _resolve(holder, event_data, source_component):
    # Bind the unbound method to our holder so we don't have to construct
    # the full WebUIBackendComponent (heavy) for these pure-logic tests.
    return WebUIBackendComponent.resolve_compaction_future(
        holder, event_data, source_component
    )


@pytest.mark.asyncio
async def test_mismatched_source_does_not_resolve_and_retains_entry():
    holder = _Holder()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    holder._compaction_futures["corr-1"] = {
        "future": future,
        "expected_agent_id": "agent-A",
    }

    _resolve(
        holder,
        event_data={"correlation_id": "corr-1", "success": True},
        source_component="agent-B_agent",
    )

    # Future must remain pending (not resolved, not cancelled).
    assert not future.done()
    # Entry must remain so the legitimate response can still resolve it.
    assert "corr-1" in holder._compaction_futures


@pytest.mark.asyncio
async def test_matching_source_resolves_and_pops_entry():
    holder = _Holder()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    holder._compaction_futures["corr-2"] = {
        "future": future,
        "expected_agent_id": "agent-A",
    }

    payload = {"correlation_id": "corr-2", "success": True, "summary": "ok"}
    _resolve(holder, event_data=payload, source_component="agent-A_agent")

    assert future.done()
    assert future.result() == payload
    assert "corr-2" not in holder._compaction_futures


@pytest.mark.asyncio
async def test_mismatch_then_legitimate_response_still_resolves():
    """Entry-retention guarantee: a spoof must not starve the real response."""
    holder = _Holder()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    holder._compaction_futures["corr-3"] = {
        "future": future,
        "expected_agent_id": "agent-A",
    }

    # Spoofed response first.
    _resolve(
        holder,
        event_data={"correlation_id": "corr-3", "success": True},
        source_component="attacker_agent",
    )
    assert not future.done()
    assert "corr-3" in holder._compaction_futures

    # Legitimate response after.
    real = {"correlation_id": "corr-3", "success": True}
    _resolve(holder, event_data=real, source_component="agent-A_agent")
    assert future.done()
    assert future.result() == real


@pytest.mark.asyncio
async def test_payload_agent_id_cannot_bypass_guard():
    """payload_agent_id is attacker-controlled and must NOT match."""
    holder = _Holder()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    holder._compaction_futures["corr-4"] = {
        "future": future,
        "expected_agent_id": "agent-A",
    }

    _resolve(
        holder,
        event_data={
            "correlation_id": "corr-4",
            "agent_id": "agent-A",  # attacker claim in payload
            "success": True,
        },
        source_component="attacker_agent",
    )
    assert not future.done()
    assert "corr-4" in holder._compaction_futures


def test_missing_correlation_id_is_noop():
    holder = _Holder()
    _resolve(holder, event_data={}, source_component="anyone_agent")
    assert holder._compaction_futures == {}


def test_unknown_correlation_id_is_noop():
    holder = _Holder()
    _resolve(
        holder,
        event_data={"correlation_id": "never-registered"},
        source_component="agent-A_agent",
    )
    assert holder._compaction_futures == {}
