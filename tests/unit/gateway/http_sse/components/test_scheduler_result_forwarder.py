"""Tests for SchedulerResultForwarderComponent."""

import queue
from unittest.mock import MagicMock

import pytest

from solace_agent_mesh.gateway.http_sse.components.scheduler_result_forwarder import (
    SchedulerResultForwarderComponent,
)


def _make_component():
    """Create a SchedulerResultForwarderComponent without running __init__."""
    comp = object.__new__(SchedulerResultForwarderComponent)
    comp.target_queue = MagicMock()
    comp.log_identifier = "test"
    return comp


class TestSchedulerResultForwarderInvoke:
    """Tests for the invoke method."""

    def test_non_dict_data_is_skipped(self):
        """Non-dict data should return None and never touch the queue."""
        comp = _make_component()

        result = comp.invoke(message=None, data="not-a-dict")

        assert result is None
        comp.target_queue.put_nowait.assert_not_called()

    def test_queue_full_does_not_crash(self):
        """If put_nowait raises (e.g. queue full), invoke handles it gracefully."""
        comp = _make_component()
        comp.target_queue.put_nowait.side_effect = queue.Full("queue is full")

        result = comp.invoke(message=None, data={"topic": "test/topic"})

        assert result is None
        comp.target_queue.put_nowait.assert_called_once_with({"topic": "test/topic"})

    def test_valid_dict_data_is_forwarded(self):
        """A valid dict payload should be placed on the target queue."""
        comp = _make_component()
        payload = {"topic": "scheduler/response", "payload": {"status": "ok"}}

        result = comp.invoke(message=None, data=payload)

        assert result is None
        comp.target_queue.put_nowait.assert_called_once_with(payload)
