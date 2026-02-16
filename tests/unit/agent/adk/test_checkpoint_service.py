"""
Unit tests for CheckpointService.

Uses an in-memory SQLite database for isolation and speed.
"""

import json
import time

import pytest
from sqlalchemy import create_engine

from solace_agent_mesh.agent.adk.checkpoint_models import (
    CheckpointBase,
    AgentPausedTask,
    AgentPeerSubTask,
    AgentParallelInvocation,
)
from solace_agent_mesh.agent.adk.checkpoint_service import CheckpointService


@pytest.fixture
def checkpoint_service():
    """Create a CheckpointService backed by an in-memory SQLite DB."""
    engine = create_engine("sqlite:///:memory:")
    CheckpointBase.metadata.create_all(engine)
    return CheckpointService(engine)


def _make_task_context_stub(
    task_id="task-1",
    agent_name="test-agent",
    invocation_id="inv-1",
    num_peer_calls=2,
    timeout_seconds=60,
):
    """Build a dict that mimics TaskExecutionContext.to_checkpoint_dict() output."""
    peer_sub_tasks = {}
    for i in range(num_peer_calls):
        sub_task_id = f"corr_sub-{i}"
        peer_sub_tasks[sub_task_id] = {
            "adk_function_call_id": f"fc-{i}",
            "peer_tool_name": f"tool-{i}",
            "peer_agent_name": f"agent-{i}",
            "invocation_id": invocation_id,
            "timeout_seconds": timeout_seconds,
        }

    return {
        "task_id": task_id,
        "a2a_context": {
            "effective_session_id": "sess-1",
            "user_id": "user-1",
            "logical_task_id": task_id,
        },
        "current_invocation_id": invocation_id,
        "run_based_response_buffer": "some buffer text",
        "produced_artifacts": [{"filename": "report.pdf", "version": 1}],
        "artifact_signals_to_return": [],
        "active_peer_sub_tasks": peer_sub_tasks,
        "parallel_tool_calls": {
            invocation_id: {
                "total": num_peer_calls,
                "completed": 0,
                "results": [],
            }
        },
        "flags": {"some_flag": True},
        "security_context": {"token": "secret"},
        "token_usage": {
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_cached_input_tokens": 10,
            "by_model": {},
            "by_source": {},
        },
    }


class FakeTaskContext:
    """Minimal mock that exposes to_checkpoint_dict()."""

    def __init__(self, checkpoint_dict):
        self._data = checkpoint_dict

    def to_checkpoint_dict(self):
        return self._data


# ── checkpoint_task ──────────────────────────────────────────────────


class TestCheckpointTask:
    def test_basic_checkpoint(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        # Verify paused task record
        restored = checkpoint_service.restore_task("task-1")
        assert restored is not None
        assert restored["task_id"] == "task-1"
        assert restored["a2a_context"]["user_id"] == "user-1"
        assert restored["run_based_response_buffer"] == "some buffer text"
        assert restored["flags"] == {"some_flag": True}
        assert restored["security_context"] == {"token": "secret"}
        assert restored["token_usage"]["total_input_tokens"] == 100

    def test_peer_sub_tasks_created(self, checkpoint_service):
        data = _make_task_context_stub(num_peer_calls=3)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        # Verify each sub-task is claimable
        for i in range(3):
            sub_task_id = f"corr_sub-{i}"
            result = checkpoint_service.get_peer_sub_task(sub_task_id)
            assert result is not None
            assert result["logical_task_id"] == "task-1"

    def test_parallel_invocation_created(self, checkpoint_service):
        data = _make_task_context_stub(num_peer_calls=2)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        results = checkpoint_service.get_parallel_results("task-1", "inv-1")
        assert results == []  # No results yet


# ── claim_peer_sub_task ──────────────────────────────────────────────


class TestClaimPeerSubTask:
    def test_claim_returns_correlation_data(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        result = checkpoint_service.claim_peer_sub_task("corr_sub-0")
        assert result is not None
        assert result["peer_tool_name"] == "tool-0"
        assert result["logical_task_id"] == "task-1"
        assert result["invocation_id"] == "inv-1"

    def test_claim_is_destructive(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        # First claim succeeds
        result = checkpoint_service.claim_peer_sub_task("corr_sub-0")
        assert result is not None

        # Second claim returns None (already claimed)
        result2 = checkpoint_service.claim_peer_sub_task("corr_sub-0")
        assert result2 is None

    def test_claim_nonexistent_returns_none(self, checkpoint_service):
        result = checkpoint_service.claim_peer_sub_task("nonexistent")
        assert result is None


# ── record_parallel_result ───────────────────────────────────────────


class TestRecordParallelResult:
    def test_increment_and_accumulate(self, checkpoint_service):
        data = _make_task_context_stub(num_peer_calls=3)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        result1 = {"adk_function_call_id": "fc-0", "payload": {"result": "ok1"}}
        completed, total = checkpoint_service.record_parallel_result(
            "task-1", "inv-1", result1
        )
        assert completed == 1
        assert total == 3

        result2 = {"adk_function_call_id": "fc-1", "payload": {"result": "ok2"}}
        completed, total = checkpoint_service.record_parallel_result(
            "task-1", "inv-1", result2
        )
        assert completed == 2
        assert total == 3

        result3 = {"adk_function_call_id": "fc-2", "payload": {"result": "ok3"}}
        completed, total = checkpoint_service.record_parallel_result(
            "task-1", "inv-1", result3
        )
        assert completed == 3
        assert total == 3

        # Verify accumulated results
        results = checkpoint_service.get_parallel_results("task-1", "inv-1")
        assert len(results) == 3
        assert results[0]["payload"]["result"] == "ok1"

    def test_nonexistent_invocation_returns_zero(self, checkpoint_service):
        completed, total = checkpoint_service.record_parallel_result(
            "no-task", "no-inv", {}
        )
        assert completed == 0
        assert total == 0


# ── restore_task ─────────────────────────────────────────────────────


class TestRestoreTask:
    def test_restore_nonexistent_returns_none(self, checkpoint_service):
        result = checkpoint_service.restore_task("nonexistent")
        assert result is None

    def test_restore_roundtrip(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        restored = checkpoint_service.restore_task("task-1")
        assert restored["task_id"] == "task-1"
        assert restored["current_invocation_id"] == "inv-1"
        assert restored["produced_artifacts"] == [
            {"filename": "report.pdf", "version": 1}
        ]


# ── cleanup_task ─────────────────────────────────────────────────────


class TestCleanupTask:
    def test_cleanup_removes_all_records(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        checkpoint_service.cleanup_task("task-1")

        assert checkpoint_service.restore_task("task-1") is None
        assert checkpoint_service.claim_peer_sub_task("corr_sub-0") is None
        assert checkpoint_service.get_parallel_results("task-1", "inv-1") == []


# ── timeout handling ─────────────────────────────────────────────────


class TestTimeoutHandling:
    def test_reset_timeout_deadline(self, checkpoint_service):
        data = _make_task_context_stub()
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        new_deadline = time.time() + 120
        assert checkpoint_service.reset_timeout_deadline("corr_sub-0", new_deadline)

    def test_reset_nonexistent_returns_false(self, checkpoint_service):
        assert not checkpoint_service.reset_timeout_deadline("nonexistent", 0)

    def test_sweep_expired_timeouts(self, checkpoint_service):
        # Create task with non-zero timeout, then manually expire
        data = _make_task_context_stub(timeout_seconds=60)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        # Manually set deadlines to the past
        past_deadline = time.time() - 10
        for i in range(2):
            checkpoint_service.reset_timeout_deadline(f"corr_sub-{i}", past_deadline)

        expired = checkpoint_service.sweep_expired_timeouts("test-agent")
        assert len(expired) == 2  # Both sub-tasks should be expired
        assert expired[0]["logical_task_id"] == "task-1"

    def test_sweep_respects_agent_name(self, checkpoint_service):
        data = _make_task_context_stub(timeout_seconds=60)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        # Manually expire
        past_deadline = time.time() - 10
        for i in range(2):
            checkpoint_service.reset_timeout_deadline(f"corr_sub-{i}", past_deadline)

        # Sweep with wrong agent name finds nothing
        expired = checkpoint_service.sweep_expired_timeouts("other-agent")
        assert len(expired) == 0

    def test_sweep_ignores_non_expired(self, checkpoint_service):
        data = _make_task_context_stub(timeout_seconds=3600)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        expired = checkpoint_service.sweep_expired_timeouts("test-agent")
        assert len(expired) == 0


# ── get_peer_sub_tasks_for_task ──────────────────────────────────────


class TestGetPeerSubTasksForTask:
    def test_returns_all_sub_tasks(self, checkpoint_service):
        data = _make_task_context_stub(num_peer_calls=3)
        ctx = FakeTaskContext(data)
        checkpoint_service.checkpoint_task(ctx, "test-agent")

        sub_tasks = checkpoint_service.get_peer_sub_tasks_for_task("task-1")
        assert len(sub_tasks) == 3
        for entry in sub_tasks:
            assert "sub_task_id" in entry
            assert "correlation_data" in entry
            assert entry["correlation_data"]["invocation_id"] == "inv-1"

    def test_returns_empty_for_nonexistent_task(self, checkpoint_service):
        sub_tasks = checkpoint_service.get_peer_sub_tasks_for_task("nonexistent")
        assert sub_tasks == []
