"""
Unit tests for task timeout in BaseGatewayComponent and GenericGatewayComponent.

Tests focus on observable outcomes:
- Context is cleaned up after timeout
- Error is delivered with correct content
- Cleanup completes even when individual steps fail
- Timeout is a no-op when disabled or context already removed
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from a2a.types import JSONRPCError

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
from solace_agent_mesh.gateway.base.task_context import TaskContextManager


TASK_ID = "test-task-timeout-123"


def _build_generic_component(timeout_seconds=300):
    """Build a mock GenericGatewayComponent with real TaskContextManager."""
    component = Mock(spec=GenericGatewayComponent)
    component.log_identifier = "[TestGenericGateway]"
    component.task_timeout_seconds = timeout_seconds
    component.task_context_manager = TaskContextManager()

    # Bind real methods
    for cls, methods in [
        (BaseGatewayComponent, [
            "_task_timeout_timer_id",
            "_start_task_timeout",
            "_cancel_task_timeout",
            "_on_task_timeout",
            "_handle_task_timeout",
        ]),
        (GenericGatewayComponent, [
            "_handle_task_timeout",
        ]),
    ]:
        for method_name in methods:
            setattr(component, method_name, getattr(cls, method_name).__get__(component))

    # Mock infrastructure
    component.add_timer = Mock()
    component.cancel_timer = Mock()
    component.get_async_loop = Mock()

    # Mock methods called during timeout handling
    component._send_error_to_external = AsyncMock()
    component.cancel_task = AsyncMock()
    component._close_external_connections = AsyncMock()

    return component


def _store_context(component, task_id=TASK_ID, with_stream_buffer=False):
    """Store a task context and optionally a stream buffer."""
    ctx = {"a2a_session_id": "session-1", "user_identity": {"id": "user@test.com"}}
    component.task_context_manager.store_context(task_id, ctx)
    if with_stream_buffer:
        component.task_context_manager.store_context(
            f"{task_id}_stream_buffer", "buffered text"
        )
    return ctx


class TestTimeoutDisabled:
    """When task_timeout_seconds=0, timeout has no effect."""

    def test_start_and_cancel_leave_context_intact(self):
        component = _build_generic_component(timeout_seconds=0)
        _store_context(component)

        component._start_task_timeout(TASK_ID)
        component._cancel_task_timeout(TASK_ID)

        # Context still exists — nothing was touched
        assert component.task_context_manager.get_context(TASK_ID) is not None


class TestTimeoutCleanup:
    """Timeout removes task context and stream buffer."""

    @pytest.mark.asyncio
    async def test_context_removed_after_timeout(self):
        component = _build_generic_component()
        _store_context(component)

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(TASK_ID) is None

    @pytest.mark.asyncio
    async def test_stream_buffer_removed_after_timeout(self):
        component = _build_generic_component()
        _store_context(component, with_stream_buffer=True)

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer") is None

    @pytest.mark.asyncio
    async def test_other_task_context_not_affected(self):
        component = _build_generic_component()
        _store_context(component, task_id=TASK_ID)
        other_ctx = {"keep": "this"}
        component.task_context_manager.store_context("other-task", other_ctx)

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context("other-task") is not None


class TestTimeoutErrorContent:
    """Timeout delivers a properly structured error."""

    @pytest.mark.asyncio
    async def test_error_has_timeout_code(self):
        component = _build_generic_component(timeout_seconds=120)
        _store_context(component)

        await component._handle_task_timeout(TASK_ID)

        error_arg = component._send_error_to_external.call_args[0][1]
        assert isinstance(error_arg, JSONRPCError)
        assert error_arg.code == -32001

    @pytest.mark.asyncio
    async def test_error_message_includes_timeout_duration(self):
        component = _build_generic_component(timeout_seconds=120)
        _store_context(component)

        await component._handle_task_timeout(TASK_ID)

        error_arg = component._send_error_to_external.call_args[0][1]
        assert "120" in error_arg.message

    @pytest.mark.asyncio
    async def test_error_has_timeout_task_status(self):
        component = _build_generic_component()
        _store_context(component)

        await component._handle_task_timeout(TASK_ID)

        error_arg = component._send_error_to_external.call_args[0][1]
        assert isinstance(error_arg.data, dict)
        assert error_arg.data["taskStatus"] == "timeout"

    @pytest.mark.asyncio
    async def test_error_converts_to_timed_out_category(self):
        """Verify _a2a_error_to_sam_error maps timeout to TIMED_OUT category."""
        from solace_agent_mesh.gateway.adapter.types import SamError

        component = _build_generic_component()
        # Bind real _a2a_error_to_sam_error
        component._a2a_error_to_sam_error = (
            GenericGatewayComponent._a2a_error_to_sam_error.__get__(component)
        )

        timeout_error = JSONRPCError(
            code=-32001,
            message="Task timed out after 300 seconds of inactivity",
            data={"taskStatus": "timeout"},
        )

        sam_error = component._a2a_error_to_sam_error(timeout_error)

        assert sam_error.category == "TIMED_OUT"
        assert "timed out" in sam_error.message

    @pytest.mark.asyncio
    async def test_context_has_task_id_injected(self):
        component = _build_generic_component()
        _store_context(component)

        await component._handle_task_timeout(TASK_ID)

        ctx_arg = component._send_error_to_external.call_args[0][0]
        assert ctx_arg["a2a_task_id_for_event"] == TASK_ID


class TestTimeoutRaceCondition:
    """When task completes normally before timeout fires, timeout is a no-op."""

    @pytest.mark.asyncio
    async def test_noop_when_context_already_removed(self):
        """Race condition: task completed normally before timeout fires."""
        component = _build_generic_component()
        # Don't store context — simulates normal completion already cleaned up
        # Store a different task to verify it's not affected
        component.task_context_manager.store_context("other-task", {"keep": "this"})

        await component._handle_task_timeout(TASK_ID)

        # Other task's context is untouched — timeout didn't corrupt anything
        assert component.task_context_manager.get_context("other-task") is not None
        # No context was created for the timed-out task
        assert component.task_context_manager.get_context(TASK_ID) is None


class TestTimeoutResilience:
    """Cleanup completes even when individual steps fail."""

    @pytest.mark.asyncio
    async def test_cleanup_completes_when_send_error_fails(self):
        component = _build_generic_component()
        _store_context(component, with_stream_buffer=True)
        component._send_error_to_external.side_effect = RuntimeError("adapter broken")

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(TASK_ID) is None
        assert component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer") is None

    @pytest.mark.asyncio
    async def test_cleanup_completes_when_cancel_task_fails(self):
        component = _build_generic_component()
        _store_context(component, with_stream_buffer=True)
        component.cancel_task.side_effect = RuntimeError("cancel failed")

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(TASK_ID) is None
        assert component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer") is None

    @pytest.mark.asyncio
    async def test_cleanup_completes_when_close_connections_fails(self):
        component = _build_generic_component()
        _store_context(component, with_stream_buffer=True)
        component._close_external_connections.side_effect = RuntimeError("close failed")

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(TASK_ID) is None
        assert component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer") is None

    @pytest.mark.asyncio
    async def test_cleanup_completes_when_all_steps_fail(self):
        component = _build_generic_component()
        _store_context(component, with_stream_buffer=True)
        component._send_error_to_external.side_effect = RuntimeError("error failed")
        component.cancel_task.side_effect = RuntimeError("cancel failed")
        component._close_external_connections.side_effect = RuntimeError("close failed")

        await component._handle_task_timeout(TASK_ID)

        assert component.task_context_manager.get_context(TASK_ID) is None
        assert component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer") is None


class TestBaseHandleTaskTimeout:
    """Base class _handle_task_timeout is a safe no-op."""

    @pytest.mark.asyncio
    async def test_does_not_crash(self):
        component = Mock(spec=BaseGatewayComponent)
        component.log_identifier = "[TestBase]"
        component._handle_task_timeout = (
            BaseGatewayComponent._handle_task_timeout.__get__(component)
        )

        # Should log warning and return, not raise
        await component._handle_task_timeout(TASK_ID)