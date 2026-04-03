"""Unit tests for ResultHandler and _sanitize_error_message.

Tests cover:
- ``_sanitize_error_message`` edge cases (empty, multi-line, truncation, whitespace)
- ``_handle_success`` DB update and event signalling
- ``_handle_error`` DB update, event signalling, and log sanitization
"""

import asyncio
from contextlib import contextmanager
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

from a2a.types import Task, JSONRPCError
from solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler import (
    ResultHandler,
    _sanitize_error_message,
    _MAX_USER_ERROR_LENGTH,
)
from solace_agent_mesh.gateway.http_sse.repository.models import ExecutionStatus, ScheduledTaskExecutionModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_result_handler():
    """Build a ResultHandler with a mocked session factory.

    Returns (handler, mock_session).
    """
    mock_session = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.add = MagicMock()

    @contextmanager
    def mock_session_factory():
        yield mock_session

    handler = ResultHandler(
        session_factory=mock_session_factory,
        namespace="ns1",
        instance_id="inst-1",
    )
    return handler, mock_session


# ===========================================================================
# _sanitize_error_message
# ===========================================================================

class TestSanitizeErrorMessage:
    """Tests for the module-level ``_sanitize_error_message`` function."""

    def test_none_returns_default(self):
        assert _sanitize_error_message(None) == "Task execution failed"

    def test_empty_string_returns_default(self):
        assert _sanitize_error_message("") == "Task execution failed"

    def test_multiline_returns_first_line(self):
        msg = "First line\nSecond line\nThird line"
        assert _sanitize_error_message(msg) == "First line"

    def test_long_input_truncated_with_ellipsis(self):
        long_msg = "a" * (_MAX_USER_ERROR_LENGTH + 100)
        result = _sanitize_error_message(long_msg)
        assert len(result) == _MAX_USER_ERROR_LENGTH + 3  # +3 for "..."
        assert result.endswith("...")

    def test_short_single_line_returned_as_is(self):
        msg = "Something went wrong"
        assert _sanitize_error_message(msg) == "Something went wrong"

    def test_whitespace_only_first_line_returns_default(self):
        msg = "   \nActual error on second line"
        assert _sanitize_error_message(msg) == "Task execution failed"


# ===========================================================================
# _handle_success
# ===========================================================================

class TestHandleSuccess:
    """Tests for ``ResultHandler._handle_success``."""

    @pytest.mark.asyncio
    async def test_task_result_updates_execution_and_signals_event(self):
        """A Task result with status.message should update the DB and signal completion."""
        handler, mock_session = _build_result_handler()

        execution_id = "exec-1"

        # Set up completion event
        event = asyncio.Event()
        handler.completion_events[execution_id] = event
        handler.execution_sessions[execution_id] = "session-123"

        # Build a Task result with a status message
        mock_message = MagicMock()
        mock_status = MagicMock()
        mock_status.message = mock_message
        task_result = MagicMock(spec=Task)
        task_result.status = mock_status

        mock_repo = MagicMock()
        mock_repo.find_execution_by_id.return_value = None  # skip _save_chat_task

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            return_value=mock_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=1000,
        ):
            mock_a2a.get_text_from_message.return_value = "Agent says hello"
            mock_a2a.get_file_parts_from_message.return_value = []
            mock_a2a.get_task_history.return_value = []
            mock_a2a.get_task_status.return_value = "completed"
            mock_a2a.get_task_metadata.return_value = None
            mock_a2a.get_task_artifacts.return_value = []

            await handler._handle_success(execution_id, task_result)

        # Verify DB update
        mock_repo.update_execution.assert_called_once()
        call_args = mock_repo.update_execution.call_args
        assert call_args[0][0] is mock_session  # session
        assert call_args[0][1] == execution_id
        update_data = call_args[0][2]
        assert update_data["status"] == ExecutionStatus.COMPLETED
        assert "agent_response" in update_data["result_summary"]
        assert update_data["result_summary"]["agent_response"] == "Agent says hello"

        # Verify event was signalled
        assert event.is_set()

        # Verify execution_sessions cleaned up
        assert execution_id not in handler.execution_sessions

    @pytest.mark.asyncio
    async def test_non_task_result_completes_without_error(self):
        """A non-Task result should still complete and signal the event."""
        handler, mock_session = _build_result_handler()

        execution_id = "exec-2"
        event = asyncio.Event()
        handler.completion_events[execution_id] = event

        non_task_result = {"some": "dict"}  # Not a Task instance

        mock_repo = MagicMock()
        mock_repo.find_execution_by_id.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            return_value=mock_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=2000,
        ):
            await handler._handle_success(execution_id, non_task_result)

        # Should still complete
        mock_repo.update_execution.assert_called_once()
        update_data = mock_repo.update_execution.call_args[0][2]
        assert update_data["status"] == ExecutionStatus.COMPLETED

        # Event signalled
        assert event.is_set()


# ===========================================================================
# _handle_error
# ===========================================================================

class TestHandleError:
    """Tests for ``ResultHandler._handle_error``."""

    @pytest.mark.asyncio
    async def test_error_updates_execution_with_sanitized_message(self):
        """A JSONRPCError should update the DB with FAILED status and sanitized error."""
        handler, mock_session = _build_result_handler()

        execution_id = "exec-3"
        event = asyncio.Event()
        handler.completion_events[execution_id] = event

        error = MagicMock(spec=JSONRPCError)
        error.message = "Something failed"
        error.code = -32000

        mock_repo = MagicMock()
        mock_repo.find_execution_by_id.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            return_value=mock_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=3000,
        ):
            await handler._handle_error(execution_id, error)

        mock_repo.update_execution.assert_called_once()
        call_args = mock_repo.update_execution.call_args
        update_data = call_args[0][2]
        assert update_data["status"] == ExecutionStatus.FAILED
        assert update_data["error_message"] == "Something failed"
        assert update_data["result_summary"] == {"error_code": -32000}

        # Event signalled
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_multiline_error_is_sanitized_in_db_and_log(self):
        """A multi-line error with stack trace content should be sanitized."""
        handler, mock_session = _build_result_handler()

        execution_id = "exec-4"
        event = asyncio.Event()
        handler.completion_events[execution_id] = event

        raw_message = (
            "NullPointerException: something broke\n"
            "  at com.example.Foo.bar(Foo.java:42)\n"
            "  at com.example.Main.main(Main.java:10)"
        )
        error = MagicMock(spec=JSONRPCError)
        error.message = raw_message
        error.code = -32603

        mock_repo = MagicMock()
        mock_repo.find_execution_by_id.return_value = None

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            return_value=mock_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=4000,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.log"
        ) as mock_log:
            await handler._handle_error(execution_id, error)

        # DB should have sanitized (first line only) error
        update_data = mock_repo.update_execution.call_args[0][2]
        assert update_data["error_message"] == "NullPointerException: something broke"
        assert "\n" not in update_data["error_message"]

        # The raw multi-line error should NOT appear in log calls
        for call in mock_log.warning.call_args_list:
            formatted = call[0][0] % call[0][1:] if len(call[0]) > 1 else call[0][0]
            assert "Foo.java:42" not in formatted
            assert "Main.java:10" not in formatted


# ===========================================================================
# register_execution
# ===========================================================================

class TestRegisterExecution:
    """Tests for ``ResultHandler.register_execution``."""

    @pytest.mark.asyncio
    async def test_creates_event_and_tracks_pending(self):
        handler, _ = _build_result_handler()

        event = await handler.register_execution("exec-10", "a2a-10")

        assert isinstance(event, asyncio.Event)
        assert not event.is_set()
        assert handler.pending_executions["a2a-10"] == "exec-10"
        assert handler.completion_events["exec-10"] is event

    @pytest.mark.asyncio
    async def test_tracks_session_id_when_provided(self):
        handler, _ = _build_result_handler()

        await handler.register_execution("exec-11", "a2a-11", session_id="sess-11")

        assert handler.execution_sessions["exec-11"] == "sess-11"

    @pytest.mark.asyncio
    async def test_no_session_tracking_when_session_id_is_none(self):
        handler, _ = _build_result_handler()

        await handler.register_execution("exec-12", "a2a-12", session_id=None)

        assert "exec-12" not in handler.execution_sessions


# ===========================================================================
# wait_for_completion
# ===========================================================================

class TestWaitForCompletion:
    """Tests for ``ResultHandler.wait_for_completion``."""

    @pytest.mark.asyncio
    async def test_blocks_until_event_is_set(self):
        handler, _ = _build_result_handler()

        event = await handler.register_execution("exec-20", "a2a-20")

        async def _set_later():
            await asyncio.sleep(0.05)
            event.set()

        asyncio.get_event_loop().create_task(_set_later())
        await asyncio.wait_for(handler.wait_for_completion("exec-20"), timeout=2.0)

        assert event.is_set()

    @pytest.mark.asyncio
    async def test_returns_immediately_for_unknown_execution_id(self):
        handler, _ = _build_result_handler()

        # Should not raise or hang
        await asyncio.wait_for(
            handler.wait_for_completion("unknown-exec"),
            timeout=1.0,
        )


# ===========================================================================
# handle_response
# ===========================================================================

class TestHandleResponse:
    """Tests for ``ResultHandler.handle_response``."""

    @pytest.mark.asyncio
    async def test_routes_to_handle_success_when_result_present(self):
        handler, _ = _build_result_handler()
        await handler.register_execution("exec-30", "a2a-30")

        mock_rpc_response = MagicMock()
        mock_result = MagicMock(spec=Task)

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.JSONRPCResponse"
        ) as MockRPCResp, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a:
            MockRPCResp.model_validate.return_value = mock_rpc_response
            mock_a2a.get_response_id.return_value = "a2a-30"
            mock_a2a.get_response_result.return_value = mock_result
            mock_a2a.get_response_error.return_value = None

            with patch.object(handler, "_handle_success", new_callable=AsyncMock) as mock_success:
                await handler.handle_response({
                    "topic": "ns1a2a/v1/scheduler/response/foo",
                    "payload": {},
                })

                mock_success.assert_awaited_once_with("exec-30", mock_result)

    @pytest.mark.asyncio
    async def test_routes_to_handle_error_when_error_present(self):
        handler, _ = _build_result_handler()
        await handler.register_execution("exec-31", "a2a-31")

        mock_rpc_response = MagicMock()
        mock_error = MagicMock(spec=JSONRPCError)

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.JSONRPCResponse"
        ) as MockRPCResp, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a:
            MockRPCResp.model_validate.return_value = mock_rpc_response
            mock_a2a.get_response_id.return_value = "a2a-31"
            mock_a2a.get_response_result.return_value = None
            mock_a2a.get_response_error.return_value = mock_error

            with patch.object(handler, "_handle_error", new_callable=AsyncMock) as mock_err:
                await handler.handle_response({
                    "topic": "ns1a2a/v1/scheduler/response/bar",
                    "payload": {},
                })

                mock_err.assert_awaited_once_with("exec-31", mock_error)

    @pytest.mark.asyncio
    async def test_ignores_non_scheduler_topic(self):
        handler, _ = _build_result_handler()

        with patch.object(handler, "_handle_success", new_callable=AsyncMock) as mock_s, \
             patch.object(handler, "_handle_error", new_callable=AsyncMock) as mock_e:
            await handler.handle_response({
                "topic": "ns1a2a/v1/some-other/response/foo",
                "payload": {},
            })

            mock_s.assert_not_awaited()
            mock_e.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_missing_a2a_task_id_gracefully(self):
        handler, _ = _build_result_handler()

        mock_rpc_response = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.JSONRPCResponse"
        ) as MockRPCResp, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a:
            MockRPCResp.model_validate.return_value = mock_rpc_response
            mock_a2a.get_response_id.return_value = None

            with patch.object(handler, "_handle_success", new_callable=AsyncMock) as mock_s:
                await handler.handle_response({
                    "topic": "ns1a2a/v1/scheduler/response/x",
                    "payload": {},
                })

                mock_s.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_unknown_a2a_task_id(self):
        handler, _ = _build_result_handler()
        # Do NOT register any execution

        mock_rpc_response = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.JSONRPCResponse"
        ) as MockRPCResp, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a:
            MockRPCResp.model_validate.return_value = mock_rpc_response
            mock_a2a.get_response_id.return_value = "unknown-a2a-id"

            with patch.object(handler, "_handle_success", new_callable=AsyncMock) as mock_s:
                await handler.handle_response({
                    "topic": "ns1a2a/v1/scheduler/response/y",
                    "payload": {},
                })

                mock_s.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_removes_from_pending_after_processing(self):
        handler, _ = _build_result_handler()
        await handler.register_execution("exec-35", "a2a-35")

        mock_rpc_response = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.JSONRPCResponse"
        ) as MockRPCResp, patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.a2a"
        ) as mock_a2a:
            MockRPCResp.model_validate.return_value = mock_rpc_response
            mock_a2a.get_response_id.return_value = "a2a-35"
            mock_a2a.get_response_result.return_value = MagicMock(spec=Task)
            mock_a2a.get_response_error.return_value = None

            with patch.object(handler, "_handle_success", new_callable=AsyncMock):
                await handler.handle_response({
                    "topic": "ns1a2a/v1/scheduler/response/z",
                    "payload": {},
                })

        assert "a2a-35" not in handler.pending_executions


# ===========================================================================
# _is_scheduler_response
# ===========================================================================

class TestIsSchedulerResponse:
    """Tests for ``ResultHandler._is_scheduler_response``."""

    def test_matching_topic_returns_true(self):
        handler, _ = _build_result_handler()
        assert handler._is_scheduler_response("ns1a2a/v1/scheduler/response/task-1") is True

    def test_non_matching_topic_returns_false(self):
        handler, _ = _build_result_handler()
        assert handler._is_scheduler_response("ns1a2a/v1/other/response/task-1") is False

    def test_empty_topic_returns_false(self):
        handler, _ = _build_result_handler()
        assert handler._is_scheduler_response("") is False

    def test_partial_prefix_returns_false(self):
        handler, _ = _build_result_handler()
        assert handler._is_scheduler_response("ns1a2a/v1/scheduler/resp") is False


# ===========================================================================
# get_pending_count
# ===========================================================================

class TestGetPendingCount:
    """Tests for ``ResultHandler.get_pending_count``."""

    def test_returns_zero_when_empty(self):
        handler, _ = _build_result_handler()
        assert handler.get_pending_count() == 0

    @pytest.mark.asyncio
    async def test_returns_correct_count_after_registrations(self):
        handler, _ = _build_result_handler()
        await handler.register_execution("e1", "a1")
        await handler.register_execution("e2", "a2")
        await handler.register_execution("e3", "a3")
        assert handler.get_pending_count() == 3


# ===========================================================================
# Completion event signalled on error (prevents hanging)
# ===========================================================================

class TestCompletionEventSignaledOnError:
    """Test that completion events are signalled even when handlers raise exceptions."""

    @pytest.mark.asyncio
    async def test_handle_success_signals_event_on_exception(self):
        handler, _ = _build_result_handler()

        execution_id = "exec-60"
        event = asyncio.Event()
        handler.completion_events[execution_id] = event

        # Force ScheduledTaskRepository to raise inside _handle_success
        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            side_effect=RuntimeError("DB is down"),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.log",
        ):
            await handler._handle_success(execution_id, MagicMock(spec=Task))

        assert event.is_set()

    @pytest.mark.asyncio
    async def test_handle_error_signals_event_on_exception(self):
        handler, _ = _build_result_handler()

        execution_id = "exec-61"
        event = asyncio.Event()
        handler.completion_events[execution_id] = event

        error = MagicMock(spec=JSONRPCError)
        error.message = "Oops"
        error.code = -1

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.ScheduledTaskRepository",
            side_effect=RuntimeError("DB is down"),
        ), patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.log",
        ):
            await handler._handle_error(execution_id, error)

        assert event.is_set()


# ===========================================================================
# _save_chat_task
# ===========================================================================

class TestSaveChatTask:
    """Tests for ``ResultHandler._save_chat_task``."""

    def test_creates_chat_task_with_user_and_agent_bubbles(self):
        import json as _json

        handler, mock_session = _build_result_handler()

        # Build a mock execution with a parent scheduled task
        mock_task = MagicMock()
        mock_task.task_message = [{"type": "text", "text": "What is the weather?"}]
        mock_task.created_by = "user-42"
        mock_task.target_agent_name = "weather-agent"

        execution = MagicMock(spec=ScheduledTaskExecutionModel)
        execution.id = "exec-70"
        execution.a2a_task_id = "a2a-70"
        execution.scheduled_task = mock_task

        messages = [{"role": "agent", "text": "It is sunny."}]

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=9000,
        ):
            handler._save_chat_task(mock_session, execution, messages)

        mock_session.add.assert_called_once()
        chat_task = mock_session.add.call_args[0][0]

        assert chat_task.id == "a2a-70"
        assert chat_task.session_id == "scheduled_exec-70"
        assert chat_task.user_id == "user-42"
        assert chat_task.user_message == "What is the weather?"
        assert chat_task.created_time == 9000
        assert chat_task.updated_time == 9000

        bubbles = _json.loads(chat_task.message_bubbles)
        assert len(bubbles) == 2
        assert bubbles[0]["type"] == "user"
        assert bubbles[0]["text"] == "What is the weather?"
        assert bubbles[1]["type"] == "agent"
        assert bubbles[1]["text"] == "It is sunny."
        assert bubbles[1]["isError"] is False

        metadata = _json.loads(chat_task.task_metadata)
        assert metadata["status"] == "completed"
        assert metadata["agent_name"] == "weather-agent"
        assert metadata["source"] == "scheduler"

    def test_creates_chat_task_with_artifacts(self):
        import json as _json

        handler, mock_session = _build_result_handler()

        mock_task = MagicMock()
        mock_task.task_message = [{"type": "text", "text": "Generate a report"}]
        mock_task.created_by = "user-43"
        mock_task.target_agent_name = "report-agent"

        execution = MagicMock(spec=ScheduledTaskExecutionModel)
        execution.id = "exec-71"
        execution.a2a_task_id = "a2a-71"
        execution.scheduled_task = mock_task

        messages = [{"role": "agent", "text": "Here is your report."}]
        artifacts = [
            {
                "kind": "artifact",
                "status": "completed",
                "name": "report.pdf",
                "file": {"name": "report.pdf", "mime_type": "application/pdf", "uri": "artifact://s1/report.pdf"},
            }
        ]

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=9001,
        ):
            handler._save_chat_task(mock_session, execution, messages, artifacts=artifacts)

        chat_task = mock_session.add.call_args[0][0]
        bubbles = _json.loads(chat_task.message_bubbles)

        # Agent bubble should contain artifact marker text and artifact part
        agent_bubble = bubbles[1]
        assert "\u00abartifact_return:report.pdf\u00bb" in agent_bubble["text"]
        assert len(agent_bubble["parts"]) == 2  # text part + artifact part
        assert agent_bubble["parts"][1]["kind"] == "artifact"
        assert agent_bubble["parts"][1]["name"] == "report.pdf"

    def test_no_bubbles_does_not_add_chat_task(self):
        handler, mock_session = _build_result_handler()

        mock_task = MagicMock()
        mock_task.task_message = []
        mock_task.created_by = "user-44"

        execution = MagicMock(spec=ScheduledTaskExecutionModel)
        execution.id = "exec-72"
        execution.a2a_task_id = "a2a-72"
        execution.scheduled_task = mock_task

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=9002,
        ):
            handler._save_chat_task(mock_session, execution, messages=[])

        mock_session.add.assert_not_called()

    def test_is_error_flag_propagated_to_agent_bubble(self):
        import json as _json

        handler, mock_session = _build_result_handler()

        mock_task = MagicMock()
        mock_task.task_message = [{"type": "text", "text": "Do something"}]
        mock_task.created_by = "user-45"
        mock_task.target_agent_name = "some-agent"

        execution = MagicMock(spec=ScheduledTaskExecutionModel)
        execution.id = "exec-73"
        execution.a2a_task_id = "a2a-73"
        execution.scheduled_task = mock_task

        messages = [{"role": "agent", "text": "Something went wrong"}]

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.result_handler.now_epoch_ms",
            return_value=9003,
        ):
            handler._save_chat_task(mock_session, execution, messages, is_error=True)

        chat_task = mock_session.add.call_args[0][0]
        bubbles = _json.loads(chat_task.message_bubbles)
        assert bubbles[1]["isError"] is True

        metadata = _json.loads(chat_task.task_metadata)
        assert metadata["status"] == "error"
