"""
Unit tests for TaskExecutionContext checkpoint serialization.

Tests the to_checkpoint_dict() / from_checkpoint_dict() round-trip,
verifying all checkpoint-worthy fields are preserved and non-serializable
fields are properly excluded/recreated.
"""

import asyncio
import threading

import pytest

from solace_agent_mesh.agent.sac.task_execution_context import TaskExecutionContext


def _make_populated_context():
    """Create a TaskExecutionContext with representative data in all fields."""
    ctx = TaskExecutionContext(
        task_id="task-abc",
        a2a_context={
            "effective_session_id": "sess-123",
            "user_id": "user-456",
            "logical_task_id": "task-abc",
            "agent_name": "my-agent",
        },
    )

    # Populate serializable fields
    ctx.run_based_response_buffer = "Hello from the agent"
    ctx.produced_artifacts = [
        {"filename": "report.pdf", "version": 1},
        {"filename": "data.csv", "version": 2},
    ]
    ctx.artifact_signals_to_return = [
        {"type": "artifact_return", "filename": "report.pdf", "version": 1}
    ]
    ctx._current_invocation_id = "inv-xyz"
    ctx._flags = {"deep_research_sent": True, "custom_flag": 42}
    ctx._security_context = {"oauth_token": "bearer-xxx", "provider": "google"}

    # Token usage
    ctx.total_input_tokens = 1500
    ctx.total_output_tokens = 800
    ctx.total_cached_input_tokens = 200
    ctx.token_usage_by_model = {
        "gpt-4": {"input_tokens": 1500, "output_tokens": 800, "cached_input_tokens": 200}
    }
    ctx.token_usage_by_source = {
        "agent": {"input_tokens": 1000, "output_tokens": 600, "cached_input_tokens": 200},
        "tool:web_search": {"input_tokens": 500, "output_tokens": 200, "cached_input_tokens": 0},
    }

    # Peer sub-tasks
    ctx.active_peer_sub_tasks = {
        "corr_sub-0": {
            "adk_function_call_id": "fc-0",
            "peer_tool_name": "search_tool",
            "peer_agent_name": "search-agent",
            "invocation_id": "inv-xyz",
        },
        "corr_sub-1": {
            "adk_function_call_id": "fc-1",
            "peer_tool_name": "calc_tool",
            "peer_agent_name": "calc-agent",
            "invocation_id": "inv-xyz",
        },
    }

    # Parallel tool calls
    ctx.parallel_tool_calls = {
        "inv-xyz": {
            "total": 2,
            "completed": 0,
            "results": [],
        }
    }

    # Non-serializable fields (should NOT appear in checkpoint)
    ctx.streaming_buffer = "should be excluded"
    ctx._first_text_seen_in_turn = True
    ctx._need_spacing_before_next_text = True

    return ctx


class TestToCheckpointDict:
    def test_includes_all_serializable_fields(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        assert d["task_id"] == "task-abc"
        assert d["a2a_context"]["user_id"] == "user-456"
        assert d["current_invocation_id"] == "inv-xyz"
        assert d["run_based_response_buffer"] == "Hello from the agent"
        assert len(d["produced_artifacts"]) == 2
        assert len(d["artifact_signals_to_return"]) == 1
        assert d["flags"]["deep_research_sent"] is True
        assert d["security_context"]["oauth_token"] == "bearer-xxx"

    def test_token_usage_structure(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        token_usage = d["token_usage"]
        assert token_usage["total_input_tokens"] == 1500
        assert token_usage["total_output_tokens"] == 800
        assert token_usage["total_cached_input_tokens"] == 200
        assert "gpt-4" in token_usage["by_model"]
        assert "agent" in token_usage["by_source"]
        assert "tool:web_search" in token_usage["by_source"]

    def test_peer_sub_tasks_copied(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        assert len(d["active_peer_sub_tasks"]) == 2
        assert d["active_peer_sub_tasks"]["corr_sub-0"]["peer_tool_name"] == "search_tool"

    def test_parallel_tool_calls_copied(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        assert "inv-xyz" in d["parallel_tool_calls"]
        assert d["parallel_tool_calls"]["inv-xyz"]["total"] == 2

    def test_non_serializable_excluded(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        # These fields should NOT be in the checkpoint dict
        assert "streaming_buffer" not in d
        assert "_first_text_seen_in_turn" not in d
        assert "_need_spacing_before_next_text" not in d
        assert "_original_solace_message" not in d
        assert "cancellation_event" not in d
        assert "event_loop" not in d
        assert "lock" not in d

    def test_deep_copy_isolation(self):
        ctx = _make_populated_context()
        d = ctx.to_checkpoint_dict()

        # Mutating the dict should not affect the context
        d["flags"]["new_key"] = "new_value"
        assert "new_key" not in ctx._flags

        d["active_peer_sub_tasks"]["corr_sub-0"]["mutated"] = True
        assert "mutated" not in ctx.active_peer_sub_tasks["corr_sub-0"]

        d["a2a_context"]["injected"] = "bad"
        assert "injected" not in ctx.a2a_context


class TestFromCheckpointDict:
    def test_basic_reconstruction(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)

        assert restored.task_id == "task-abc"
        assert restored.a2a_context["user_id"] == "user-456"
        assert restored._current_invocation_id == "inv-xyz"
        assert restored.run_based_response_buffer == "Hello from the agent"

    def test_produced_artifacts_restored(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert len(restored.produced_artifacts) == 2
        assert restored.produced_artifacts[0]["filename"] == "report.pdf"

    def test_artifact_signals_restored(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert len(restored.artifact_signals_to_return) == 1

    def test_flags_restored(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert restored._flags["deep_research_sent"] is True
        assert restored._flags["custom_flag"] == 42

    def test_security_context_restored(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert restored._security_context["oauth_token"] == "bearer-xxx"

    def test_token_usage_restored(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert restored.total_input_tokens == 1500
        assert restored.total_output_tokens == 800
        assert restored.total_cached_input_tokens == 200
        assert "gpt-4" in restored.token_usage_by_model
        assert "tool:web_search" in restored.token_usage_by_source

    def test_non_serializable_recreated(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)

        # These should be fresh instances, not from the checkpoint
        assert isinstance(restored.cancellation_event, asyncio.Event)
        assert not restored.cancellation_event.is_set()
        assert hasattr(restored.lock, "acquire") and hasattr(restored.lock, "release")
        assert restored.event_loop is None
        assert restored._original_solace_message is None

    def test_transient_state_reset(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)

        # Streaming buffer and turn tracking should be fresh
        assert restored.streaming_buffer == ""
        assert restored._first_text_seen_in_turn is False
        assert restored._need_spacing_before_next_text is False

    def test_active_peer_sub_tasks_empty(self):
        """
        active_peer_sub_tasks should NOT be restored from checkpoint dict
        because they live in separate DB tables.
        """
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert restored.active_peer_sub_tasks == {}

    def test_parallel_tool_calls_empty(self):
        """
        parallel_tool_calls should NOT be restored from checkpoint dict
        because they live in separate DB tables.
        """
        original = _make_populated_context()
        d = original.to_checkpoint_dict()

        restored = TaskExecutionContext.from_checkpoint_dict(d)
        assert restored.parallel_tool_calls == {}


class TestRoundTrip:
    def test_full_round_trip_preserves_key_fields(self):
        original = _make_populated_context()
        d = original.to_checkpoint_dict()
        restored = TaskExecutionContext.from_checkpoint_dict(d)

        # Compare all checkpoint-worthy fields
        assert restored.task_id == original.task_id
        assert restored.a2a_context == original.a2a_context
        assert restored._current_invocation_id == original._current_invocation_id
        assert (
            restored.run_based_response_buffer
            == original.run_based_response_buffer
        )
        assert restored.produced_artifacts == original.produced_artifacts
        assert (
            restored.artifact_signals_to_return
            == original.artifact_signals_to_return
        )
        assert restored._flags == original._flags
        assert restored._security_context == original._security_context
        assert restored.total_input_tokens == original.total_input_tokens
        assert restored.total_output_tokens == original.total_output_tokens
        assert (
            restored.total_cached_input_tokens
            == original.total_cached_input_tokens
        )
        assert restored.token_usage_by_model == original.token_usage_by_model
        assert restored.token_usage_by_source == original.token_usage_by_source

    def test_empty_context_round_trip(self):
        """Minimal context with no peer calls should round-trip cleanly."""
        ctx = TaskExecutionContext(
            task_id="minimal-task",
            a2a_context={"user_id": "u1"},
        )
        d = ctx.to_checkpoint_dict()
        restored = TaskExecutionContext.from_checkpoint_dict(d)

        assert restored.task_id == "minimal-task"
        assert restored.a2a_context == {"user_id": "u1"}
        assert restored.run_based_response_buffer == ""
        assert restored.produced_artifacts == []
        assert restored.total_input_tokens == 0
