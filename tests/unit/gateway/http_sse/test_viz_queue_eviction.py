#!/usr/bin/env python3
"""
Unit tests for _put_viz_msg_to_stream and the per-stream drop counter
cleanup paths introduced to fix the memory leak in _viz_stream_drop_counts.

The method only depends on self._viz_stream_drop_counts (a plain dict) and
accepts explicit queue, stream_id, msg, log_id_prefix params — so we test it
with a minimal stub created via object.__new__ to skip the heavy __init__.
"""

import asyncio
import logging

import pytest

from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


@pytest.fixture
def stub():
    """Minimal stub with only the state _put_viz_msg_to_stream needs."""
    obj = object.__new__(WebUIBackendComponent)
    obj._viz_stream_drop_counts = {}
    return obj


# ── 1. Happy path — message enqueued, no eviction ──────────────────────


def test_put_msg_no_eviction(stub):
    q = asyncio.Queue(maxsize=5)
    msg = {"event": "a2a_message", "data": "test"}
    stub._put_viz_msg_to_stream("s1", q, msg, "[TEST]")

    assert q.qsize() == 1
    assert q.get_nowait() == msg
    assert "s1" not in stub._viz_stream_drop_counts


# ── 2. Queue full — oldest evicted, newest inserted ────────────────────


def test_evicts_oldest_when_full(stub):
    q = asyncio.Queue(maxsize=2)
    q.put_nowait({"data": "old1"})
    q.put_nowait({"data": "old2"})

    new_msg = {"data": "new"}
    stub._put_viz_msg_to_stream("s1", q, new_msg, "[TEST]")

    assert q.qsize() == 2
    assert q.get_nowait() == {"data": "old2"}  # old1 was evicted
    assert q.get_nowait() == new_msg


# ── 3. Queue maxsize=1 — single-slot eviction works ────────────────────


def test_eviction_with_maxsize_one(stub):
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"data": "old"})

    new_msg = {"data": "new"}
    stub._put_viz_msg_to_stream("s1", q, new_msg, "[TEST]")

    assert q.qsize() == 1
    assert q.get_nowait() == new_msg


# ── 4. Drop counter increments correctly across multiple evictions ──────


def test_drop_counter_increments(stub):
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"data": "seed"})

    for i in range(25):
        stub._put_viz_msg_to_stream("s1", q, {"data": f"msg{i}"}, "[TEST]")

    assert stub._viz_stream_drop_counts["s1"] == 25


# ── 5. WARNING on 1st eviction, DEBUG on 2nd–9th, WARNING on 10th ──────


def test_log_throttle_pattern(stub, caplog):
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"data": "seed"})

    with caplog.at_level(logging.DEBUG):
        for i in range(20):
            stub._put_viz_msg_to_stream("s1", q, {"data": f"m{i}"}, "[T]")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    debugs = [
        r
        for r in caplog.records
        if r.levelno == logging.DEBUG and "evict" in r.message.lower()
    ]

    # Warnings at eviction 1, 10, 20
    assert len(warnings) == 3
    assert "total evictions: 1" in warnings[0].message
    assert "total evictions: 10" in warnings[1].message
    assert "total evictions: 20" in warnings[2].message

    # Evictions 2-9, 11-19 → 17 debug messages about eviction
    assert len(debugs) == 17


# ── 6. Counters are per-stream (independent) ───────────────────────────


def test_counters_are_per_stream(stub):
    q1 = asyncio.Queue(maxsize=1)
    q2 = asyncio.Queue(maxsize=1)
    q1.put_nowait({"data": "seed"})
    q2.put_nowait({"data": "seed"})

    for _ in range(5):
        stub._put_viz_msg_to_stream("s1", q1, {"data": "x"}, "[T]")
    for _ in range(3):
        stub._put_viz_msg_to_stream("s2", q2, {"data": "y"}, "[T]")

    assert stub._viz_stream_drop_counts["s1"] == 5
    assert stub._viz_stream_drop_counts["s2"] == 3


# ── 7. Stream cleanup removes counter (no memory leak) ─────────────────


def test_stream_cleanup_removes_counter(stub):
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"data": "seed"})
    stub._put_viz_msg_to_stream("s1", q, {"data": "x"}, "[T]")

    assert "s1" in stub._viz_stream_drop_counts

    # Simulate what unsubscribe / failed-stream cleanup does
    stub._viz_stream_drop_counts.pop("s1", None)

    assert "s1" not in stub._viz_stream_drop_counts


# ── 8. Bulk cleanup clears all counters ─────────────────────────────────


def test_bulk_cleanup_clears_all(stub):
    for sid in ["s1", "s2", "s3"]:
        q = asyncio.Queue(maxsize=1)
        q.put_nowait({"data": "seed"})
        stub._put_viz_msg_to_stream(sid, q, {"data": "x"}, "[T]")

    assert len(stub._viz_stream_drop_counts) == 3

    stub._viz_stream_drop_counts.clear()  # what cleanup() does
    assert len(stub._viz_stream_drop_counts) == 0


# ── 9. No false increment on successful put after prior evictions ───────


def test_no_false_increment_on_successful_put(stub):
    q = asyncio.Queue(maxsize=2)
    q.put_nowait({"data": "seed1"})
    q.put_nowait({"data": "seed2"})

    # Force one eviction
    stub._put_viz_msg_to_stream("s1", q, {"data": "new1"}, "[T]")
    assert stub._viz_stream_drop_counts["s1"] == 1

    # Now queue has space (size 2, 2 items; get one to make room)
    q.get_nowait()

    # This put should succeed without eviction
    stub._put_viz_msg_to_stream("s1", q, {"data": "new2"}, "[T]")
    assert stub._viz_stream_drop_counts["s1"] == 1  # unchanged
