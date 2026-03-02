"""
Unit tests for connection cleanup in BaseGatewayComponent._handle_agent_event.

Verifies that _close_external_connections is called in error paths before
remove_context, preventing SSE connection leaks.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from a2a.types import (
    JSONRPCResponse,
    JSONRPCError,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from solace_agent_mesh.gateway.base.task_context import TaskContextManager


TASK_ID = "test-task-123"
RPC_ID = "rpc-001"


def _build_component():
    """Build a mock BaseGatewayComponent with real TaskContextManager."""
    component = Mock(spec=BaseGatewayComponent)
    component.log_identifier = "[TestGateway]"
    component.task_context_manager = TaskContextManager()
    component._send_error_to_external = AsyncMock()
    component._close_external_connections = AsyncMock()
    component._process_parsed_a2a_event = AsyncMock()
    component._handle_agent_event = (
        BaseGatewayComponent._handle_agent_event.__get__(component)
    )
    return component


def _store_context(component, task_id=TASK_ID):
    """Store a minimal external request context for the given task."""
    ctx = {"sse_task_id": task_id, "connection": "mock-sse-conn"}
    component.task_context_manager.store_context(task_id, ctx)
    return ctx


def _valid_rpc_response_payload(task_id=TASK_ID, rpc_id=RPC_ID):
    """Build a valid JSONRPCResponse payload with a TaskStatusUpdateEvent result."""
    event = TaskStatusUpdateEvent(
        task_id=task_id,
        context_id=task_id,
        final=False,
        status=TaskStatus(state=TaskState.working),
    )
    return JSONRPCResponse(id=rpc_id, result=event).model_dump(mode="json")


def _rpc_response_with_null_result(rpc_id=RPC_ID):
    """Build a JSONRPCResponse where both result and error are None."""
    return {"jsonrpc": "2.0", "id": rpc_id, "result": None}


def _rpc_response_with_error(rpc_id=RPC_ID):
    """Build a JSONRPCResponse carrying an error."""
    error = JSONRPCError(code=-32000, message="Agent exploded")
    return JSONRPCResponse(id=rpc_id, error=error).model_dump(mode="json")


def _rpc_response_with_task_id_mismatch(rpc_id=RPC_ID):
    """Build a JSONRPCResponse whose inner task_id mismatches the topic task_id."""
    event = TaskStatusUpdateEvent(
        task_id="wrong-task-id",
        context_id="wrong-task-id",
        final=False,
        status=TaskStatus(state=TaskState.working),
    )
    return JSONRPCResponse(id=rpc_id, result=event).model_dump(mode="json")


class TestHandleAgentEventConnectionCleanup:
    """Verify _close_external_connections is called in all error paths."""

    @pytest.mark.asyncio
    async def test_null_result_closes_connections_before_removing_context(self):
        """Error path 1: result is None — connections must close before context removal."""
        component = _build_component()
        _store_context(component)

        result = await component._handle_agent_event(
            "topic/response", _rpc_response_with_null_result(), TASK_ID
        )

        assert result is False
        component._send_error_to_external.assert_called_once()
        component._close_external_connections.assert_called_once()
        assert component.task_context_manager.get_context(TASK_ID) is None

    @pytest.mark.asyncio
    async def test_task_id_mismatch_closes_connections_before_removing_context(self):
        """Error path 1 variant: task_id mismatch nullifies parsed event."""
        component = _build_component()
        _store_context(component)

        result = await component._handle_agent_event(
            "topic/response", _rpc_response_with_task_id_mismatch(), TASK_ID
        )

        assert result is False
        component._send_error_to_external.assert_called_once()
        component._close_external_connections.assert_called_once()
        assert component.task_context_manager.get_context(TASK_ID) is None

    @pytest.mark.asyncio
    async def test_process_event_exception_closes_connections_before_removing_context(self):
        """Error path 2: _process_parsed_a2a_event raises — connections must close."""
        component = _build_component()
        _store_context(component)
        component._process_parsed_a2a_event.side_effect = RuntimeError("boom")

        result = await component._handle_agent_event(
            "topic/response", _valid_rpc_response_payload(), TASK_ID
        )

        assert result is False
        component._send_error_to_external.assert_called_once()
        component._close_external_connections.assert_called_once()
        assert component.task_context_manager.get_context(TASK_ID) is None

    @pytest.mark.asyncio
    async def test_close_called_after_send_error_and_before_context_gone(self):
        """Verify ordering: send_error → close_connections → context removed."""
        component = _build_component()
        _store_context(component)

        call_order = []
        component._send_error_to_external.side_effect = (
            lambda *a, **kw: call_order.append("send_error")
        )

        original_close = component._close_external_connections

        async def track_close(*a, **kw):
            assert component.task_context_manager.get_context(TASK_ID) is not None, (
                "Context was removed before _close_external_connections"
            )
            call_order.append("close_connections")
            return await original_close(*a, **kw)

        component._close_external_connections = track_close

        await component._handle_agent_event(
            "topic/response", _rpc_response_with_null_result(), TASK_ID
        )

        assert call_order == ["send_error", "close_connections"]
        assert component.task_context_manager.get_context(TASK_ID) is None


class TestHandleAgentEventConnectionCleanupOnProcessException:
    """Same ordering guarantees for the _process_parsed_a2a_event exception path."""

    @pytest.mark.asyncio
    async def test_close_called_after_send_error_and_before_context_gone(self):
        """Verify ordering in exception path: send_error → close → context removed."""
        component = _build_component()
        _store_context(component)
        component._process_parsed_a2a_event.side_effect = ValueError("bad data")

        call_order = []
        component._send_error_to_external.side_effect = (
            lambda *a, **kw: call_order.append("send_error")
        )

        original_close = component._close_external_connections

        async def track_close(*a, **kw):
            assert component.task_context_manager.get_context(TASK_ID) is not None, (
                "Context was removed before _close_external_connections"
            )
            call_order.append("close_connections")
            return await original_close(*a, **kw)

        component._close_external_connections = track_close

        await component._handle_agent_event(
            "topic/response", _valid_rpc_response_payload(), TASK_ID
        )

        assert call_order == ["send_error", "close_connections"]
        assert component.task_context_manager.get_context(TASK_ID) is None

    @pytest.mark.asyncio
    async def test_stream_buffer_context_also_removed(self):
        """Both task context and stream buffer context should be cleaned up."""
        component = _build_component()
        _store_context(component)
        component.task_context_manager.store_context(
            f"{TASK_ID}_stream_buffer", {"buffer": []}
        )
        component._process_parsed_a2a_event.side_effect = RuntimeError("boom")

        await component._handle_agent_event(
            "topic/response", _valid_rpc_response_payload(), TASK_ID
        )

        assert component.task_context_manager.get_context(TASK_ID) is None
        assert (
            component.task_context_manager.get_context(f"{TASK_ID}_stream_buffer")
            is None
        )


class TestHandleAgentEventHappyPath:
    """Verify _close_external_connections is NOT called by _handle_agent_event
    in the happy path (it's the responsibility of _process_parsed_a2a_event)."""

    @pytest.mark.asyncio
    async def test_successful_event_does_not_close_connections(self):
        """Happy path delegates to _process_parsed_a2a_event without closing."""
        component = _build_component()
        _store_context(component)

        result = await component._handle_agent_event(
            "topic/response", _valid_rpc_response_payload(), TASK_ID
        )

        assert result is True
        component._close_external_connections.assert_not_called()
        component._send_error_to_external.assert_not_called()


class TestHandleAgentEventNoContext:
    """Edge case: no context stored for the task_id."""

    @pytest.mark.asyncio
    async def test_missing_context_returns_true_without_closing(self):
        """When no context exists, the method returns early without closing."""
        component = _build_component()

        result = await component._handle_agent_event(
            "topic/response", _valid_rpc_response_payload(), TASK_ID
        )

        assert result is True
        component._close_external_connections.assert_not_called()
        component._send_error_to_external.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_false_without_closing(self):
        """Completely invalid payload fails before reaching cleanup paths."""
        component = _build_component()

        result = await component._handle_agent_event(
            "topic/response", {"garbage": True}, TASK_ID
        )

        assert result is False
        component._close_external_connections.assert_not_called()
        component._send_error_to_external.assert_not_called()


class TestHandleAgentEventWithRPCError:
    """When the RPC response carries an error, it goes through _process_parsed_a2a_event."""

    @pytest.mark.asyncio
    async def test_rpc_error_delegates_to_process_parsed_event(self):
        """An error in the RPC response is parsed and delegated, not handled locally."""
        component = _build_component()
        _store_context(component)

        result = await component._handle_agent_event(
            "topic/response", _rpc_response_with_error(), TASK_ID
        )

        assert result is True
        component._process_parsed_a2a_event.assert_called_once()
        component._close_external_connections.assert_not_called()
