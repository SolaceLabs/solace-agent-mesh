"""
Unit tests for structured invocation finalization branching logic in runner.py.

Covers the decision tree inside _schedule_finalization and the inline
skip_finalization block of run_adk_async_task_thread_wrapper.

Decision tree under test:
  if task_context and task_context.get_flag("structured_invocation"):
      if not is_paused or exception_to_finalize_with:
          -> schedule finalize_deferred_structured_invocation
      else:
          -> log "still paused, waiting"
  else:
      -> schedule finalize_task_with_cleanup (normal path)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from solace_agent_mesh.agent.adk.runner import _schedule_finalization, _log_future_exception


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_component(loop_running: bool = True):
    """Return a minimal mock component with a controllable async loop."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    component.agent_name = "TestAgent"

    mock_loop = Mock()
    mock_loop.is_running.return_value = loop_running
    component.get_async_loop.return_value = mock_loop

    component.structured_invocation_handler = Mock()
    # finalize_deferred_structured_invocation must return an awaitable so that
    # run_coroutine_threadsafe can accept it.
    component.structured_invocation_handler.finalize_deferred_structured_invocation = (
        AsyncMock(return_value=None)
    )

    component.finalize_task_with_cleanup = AsyncMock(return_value=None)

    return component


def _make_task_context(is_si: bool = False):
    """Return a mock TaskExecutionContext."""
    ctx = Mock()
    ctx.get_flag = Mock(side_effect=lambda flag: is_si if flag == "structured_invocation" else False)
    return ctx


A2A_CONTEXT = {"logical_task_id": "task-001", "session_id": "sess-abc"}
LOGICAL_TASK_ID = "task-001"


# ---------------------------------------------------------------------------
# _schedule_finalization — SI path
# ---------------------------------------------------------------------------

class TestScheduleFinalizationSIPath:
    """Tests for the structured-invocation branch of _schedule_finalization."""

    def test_si_completed_calls_finalize_deferred(self):
        """When SI flag is set and task is NOT paused, finalize_deferred_structured_invocation
        MUST be scheduled via run_coroutine_threadsafe."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_called_once()
            # First positional arg is the coroutine, second is the loop
            _coro, loop_arg = mock_rct.call_args.args
            assert loop_arg is component.get_async_loop()

    def test_si_completed_does_not_call_normal_finalization(self):
        """Normal finalize_task_with_cleanup MUST NOT be called on the SI path."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe"):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

        component.finalize_task_with_cleanup.assert_not_called()

    def test_si_with_exception_calls_finalize_deferred(self):
        """When SI flag is set AND there is an exception (even while paused),
        finalize_deferred_structured_invocation MUST still be scheduled."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)
        exc = RuntimeError("something broke")

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=True,   # paused but exception overrides
                exception_to_finalize_with=exc,
            )

            mock_rct.assert_called_once()

    def test_si_finalize_deferred_receives_correct_args(self):
        """finalize_deferred_structured_invocation MUST be called with
        (task_context, a2a_context, exception_to_finalize_with)."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        captured_coro = None

        def capture_rct(coro, loop):
            nonlocal captured_coro
            captured_coro = coro
            return Mock()  # Future-like

        with patch("asyncio.run_coroutine_threadsafe", side_effect=capture_rct):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

        # Drive the coroutine to completion so the mock records its call
        assert captured_coro is not None
        asyncio.get_event_loop().run_until_complete(captured_coro)

        component.structured_invocation_handler.finalize_deferred_structured_invocation.assert_called_once_with(
            task_context, A2A_CONTEXT, None
        )

    def test_si_paused_no_exception_does_not_call_finalize_deferred(self):
        """When SI flag is set but task IS paused (no exception), finalization
        MUST NOT be scheduled — waiting for more peer responses."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=True,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_not_called()

    def test_si_paused_no_exception_does_not_call_normal_finalization(self):
        """On the SI paused-skip path, normal finalize_task_with_cleanup
        MUST NOT be called either."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe"):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=True,
                exception_to_finalize_with=None,
            )

        component.finalize_task_with_cleanup.assert_not_called()

    def test_si_no_loop_logs_error_and_does_not_raise(self):
        """When the async loop is unavailable on the SI path, an error MUST be
        logged and the call MUST NOT raise."""
        component = _make_component(loop_running=False)
        # Simulate loop not running (is_running returns False)
        component.get_async_loop.return_value.is_running.return_value = False
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_not_called()

    def test_si_loop_is_none_logs_error_and_does_not_raise(self):
        """When get_async_loop() returns None on the SI path, MUST NOT raise."""
        component = _make_component()
        component.get_async_loop.return_value = None
        task_context = _make_task_context(is_si=True)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_not_called()


# ---------------------------------------------------------------------------
# _schedule_finalization — normal (non-SI) path
# ---------------------------------------------------------------------------

class TestScheduleFinalizationNormalPath:
    """Tests for the normal (non-SI) branch of _schedule_finalization."""

    def test_non_si_calls_finalize_task_with_cleanup(self):
        """When SI flag is NOT set, finalize_task_with_cleanup MUST be scheduled."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=False)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_called_once()

    def test_non_si_does_not_call_finalize_deferred(self):
        """finalize_deferred_structured_invocation MUST NOT be called on the normal path."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=False)

        with patch("asyncio.run_coroutine_threadsafe"):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

        component.structured_invocation_handler.finalize_deferred_structured_invocation.assert_not_called()

    def test_non_si_none_task_context_calls_finalize_task_with_cleanup(self):
        """When task_context is None, the SI flag check is False and normal
        finalization MUST be scheduled."""
        component = _make_component(loop_running=True)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=None,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_called_once()

    def test_non_si_finalize_task_receives_correct_args(self):
        """finalize_task_with_cleanup MUST receive (a2a_context, is_paused, exception)."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=False)
        exc = ValueError("fail")

        captured_coro = None

        def capture_rct(coro, loop):
            nonlocal captured_coro
            captured_coro = coro
            return Mock()

        with patch("asyncio.run_coroutine_threadsafe", side_effect=capture_rct):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=True,
                exception_to_finalize_with=exc,
            )

        assert captured_coro is not None
        asyncio.get_event_loop().run_until_complete(captured_coro)

        component.finalize_task_with_cleanup.assert_called_once_with(
            A2A_CONTEXT, True, exc
        )

    def test_non_si_no_loop_does_not_raise(self):
        """When the async loop is unavailable on the normal path, MUST NOT raise."""
        component = _make_component(loop_running=False)
        task_context = _make_task_context(is_si=False)

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_rct.assert_not_called()


# ---------------------------------------------------------------------------
# Inline SI block inside run_adk_async_task_thread_wrapper
# (lines ~1676-1724) — tested by patching _schedule_finalization and
# asyncio.run_coroutine_threadsafe, then driving the wrapper to the
# finalization section via mocks that make it exit early after the try block.
# ---------------------------------------------------------------------------

class TestRunADKWrapperSIFinalizationBranch:
    """Tests that the inline SI block inside run_adk_async_task_thread_wrapper
    behaves identically to _schedule_finalization for the SI case.

    We skip_finalization=False, mock out everything that runs before the
    finalization block, and assert on what asyncio.run_coroutine_threadsafe
    receives.
    """

    def _make_full_component(self, loop_running: bool = True):
        """Component with all attributes used by the wrapper function."""
        component = Mock()
        component.log_identifier = "[TestAgent]"
        component.agent_name = "TestAgent"
        component.auto_summarization_config = {"enabled": False}
        component.active_tasks_lock = MagicMock()
        component.session_service = AsyncMock()

        task_ctx = _make_task_context(is_si=True)
        component.active_tasks = {"task-001": task_ctx}

        mock_loop = Mock()
        mock_loop.is_running.return_value = loop_running
        component.get_async_loop.return_value = mock_loop

        component.structured_invocation_handler = Mock()
        component.structured_invocation_handler.finalize_deferred_structured_invocation = (
            AsyncMock(return_value=None)
        )
        component.finalize_task_with_cleanup = AsyncMock(return_value=None)

        return component, task_ctx

    @pytest.mark.asyncio
    async def test_wrapper_si_not_paused_calls_finalize_deferred(self):
        """When the inline SI block fires (SI flag True, not paused),
        finalize_deferred_structured_invocation MUST be scheduled."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper
        from google.adk.runners import RunConfig
        from google.adk.sessions import Session as ADKSession
        from google.genai import types as adk_types

        component, task_ctx = self._make_full_component(loop_running=True)

        # Patch the heavy ADK machinery so we can control is_paused
        with (
            patch(
                "solace_agent_mesh.agent.adk.runner._append_a2a_context_event",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._repair_dangling_tool_calls_in_session",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._run_with_compaction_retry",
                new_callable=AsyncMock,
                return_value=(False, Mock()),   # is_paused=False, adk_session=Mock()
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._send_deferred_compaction_notification",
                new_callable=AsyncMock,
            ),
            patch("asyncio.run_coroutine_threadsafe") as mock_rct,
        ):
            adk_session = Mock(spec=ADKSession)
            adk_content = Mock(spec=adk_types.Content)
            run_config = Mock(spec=RunConfig)

            await run_adk_async_task_thread_wrapper(
                component=component,
                adk_session=adk_session,
                adk_content=adk_content,
                run_config=run_config,
                a2a_context={"logical_task_id": "task-001"},
                skip_finalization=False,
            )

            mock_rct.assert_called_once()
            _coro, loop_arg = mock_rct.call_args.args
            assert loop_arg is component.get_async_loop()

    @pytest.mark.asyncio
    async def test_wrapper_si_paused_no_exception_skips_finalize(self):
        """When inline SI block fires with is_paused=True and no exception,
        finalize_deferred_structured_invocation MUST NOT be scheduled."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper
        from google.adk.runners import RunConfig
        from google.adk.sessions import Session as ADKSession
        from google.genai import types as adk_types

        component, task_ctx = self._make_full_component(loop_running=True)

        with (
            patch(
                "solace_agent_mesh.agent.adk.runner._append_a2a_context_event",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._repair_dangling_tool_calls_in_session",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._run_with_compaction_retry",
                new_callable=AsyncMock,
                return_value=(True, Mock()),   # is_paused=True
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._send_deferred_compaction_notification",
                new_callable=AsyncMock,
            ),
            patch("asyncio.run_coroutine_threadsafe") as mock_rct,
        ):
            adk_session = Mock(spec=ADKSession)
            adk_content = Mock(spec=adk_types.Content)
            run_config = Mock(spec=RunConfig)

            await run_adk_async_task_thread_wrapper(
                component=component,
                adk_session=adk_session,
                adk_content=adk_content,
                run_config=run_config,
                a2a_context={"logical_task_id": "task-001"},
                skip_finalization=False,
            )

            mock_rct.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrapper_skip_finalization_suppresses_all_finalization(self):
        """When skip_finalization=True, no finalization path (SI or normal)
        MUST be triggered regardless of the task state."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper
        from google.adk.runners import RunConfig
        from google.adk.sessions import Session as ADKSession
        from google.genai import types as adk_types

        component, task_ctx = self._make_full_component(loop_running=True)

        with (
            patch(
                "solace_agent_mesh.agent.adk.runner._append_a2a_context_event",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._repair_dangling_tool_calls_in_session",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._run_with_compaction_retry",
                new_callable=AsyncMock,
                return_value=(False, Mock()),
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._send_deferred_compaction_notification",
                new_callable=AsyncMock,
            ),
            patch("asyncio.run_coroutine_threadsafe") as mock_rct,
            patch(
                "solace_agent_mesh.agent.adk.runner._schedule_finalization"
            ) as mock_sf,
        ):
            adk_session = Mock(spec=ADKSession)
            adk_content = Mock(spec=adk_types.Content)
            run_config = Mock(spec=RunConfig)

            await run_adk_async_task_thread_wrapper(
                component=component,
                adk_session=adk_session,
                adk_content=adk_content,
                run_config=run_config,
                a2a_context={"logical_task_id": "task-001"},
                skip_finalization=True,
            )

            mock_rct.assert_not_called()
            mock_sf.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrapper_non_si_routes_to_schedule_finalization(self):
        """When the SI flag is NOT set, the wrapper MUST call _schedule_finalization
        instead of scheduling finalize_deferred_structured_invocation inline."""
        from solace_agent_mesh.agent.adk.runner import run_adk_async_task_thread_wrapper
        from google.adk.runners import RunConfig
        from google.adk.sessions import Session as ADKSession
        from google.genai import types as adk_types

        component, _ = self._make_full_component(loop_running=True)
        # Override the task context to be non-SI
        non_si_ctx = _make_task_context(is_si=False)
        component.active_tasks = {"task-001": non_si_ctx}

        with (
            patch(
                "solace_agent_mesh.agent.adk.runner._append_a2a_context_event",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._repair_dangling_tool_calls_in_session",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._run_with_compaction_retry",
                new_callable=AsyncMock,
                return_value=(False, Mock()),
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._send_deferred_compaction_notification",
                new_callable=AsyncMock,
            ),
            patch(
                "solace_agent_mesh.agent.adk.runner._schedule_finalization"
            ) as mock_sf,
        ):
            adk_session = Mock(spec=ADKSession)
            adk_content = Mock(spec=adk_types.Content)
            run_config = Mock(spec=RunConfig)

            await run_adk_async_task_thread_wrapper(
                component=component,
                adk_session=adk_session,
                adk_content=adk_content,
                run_config=run_config,
                a2a_context={"logical_task_id": "task-001"},
                skip_finalization=False,
            )

            mock_sf.assert_called_once_with(
                component=component,
                task_context=non_si_ctx,
                a2a_context={"logical_task_id": "task-001"},
                logical_task_id="task-001",
                is_paused=False,
                exception_to_finalize_with=None,
            )


# ---------------------------------------------------------------------------
# _log_future_exception callback
# ---------------------------------------------------------------------------

class TestLogFutureException:
    """Tests for the _log_future_exception callback used by add_done_callback."""

    def test_logs_error_when_future_has_exception(self):
        """When the future completed with an exception, the callback MUST log it."""
        component = _make_component()
        future = Mock()
        future.exception.return_value = RuntimeError("finalization blew up")

        with patch("solace_agent_mesh.agent.adk.runner.log") as mock_log:
            _log_future_exception(future, component, "task-001")

            mock_log.error.assert_called_once()
            args = mock_log.error.call_args
            assert "task-001" in str(args)
            assert "finalization blew up" in str(args)

    def test_no_log_when_future_succeeds(self):
        """When the future completed without exception, nothing should be logged."""
        component = _make_component()
        future = Mock()
        future.exception.return_value = None

        with patch("solace_agent_mesh.agent.adk.runner.log") as mock_log:
            _log_future_exception(future, component, "task-001")

            mock_log.error.assert_not_called()

    def test_callback_is_registered_on_si_finalization_future(self):
        """_schedule_finalization MUST register add_done_callback on the future
        returned by run_coroutine_threadsafe for SI tasks."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=True)

        mock_future = Mock()
        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_future.add_done_callback.assert_called_once()

    def test_callback_is_registered_on_normal_finalization_future(self):
        """_schedule_finalization MUST register add_done_callback on the future
        for normal (non-SI) tasks too."""
        component = _make_component(loop_running=True)
        task_context = _make_task_context(is_si=False)

        mock_future = Mock()
        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            _schedule_finalization(
                component=component,
                task_context=task_context,
                a2a_context=A2A_CONTEXT,
                logical_task_id=LOGICAL_TASK_ID,
                is_paused=False,
                exception_to_finalize_with=None,
            )

            mock_future.add_done_callback.assert_called_once()
