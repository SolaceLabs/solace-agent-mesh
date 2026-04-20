"""Unit tests for _inject_scheduler_conversation_history in event_handlers.py."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the google.adk and google.genai modules are importable even when
# the real packages are not installed.
_adk_events = MagicMock()
_adk_event_actions = MagicMock()
_genai_types = MagicMock()
_adk_services = MagicMock()
_adk_services.append_event_with_retry = AsyncMock()

sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.adk", MagicMock())
sys.modules.setdefault("google.adk.events", _adk_events)
sys.modules.setdefault("google.adk.events.event_actions", _adk_event_actions)
sys.modules.setdefault("google.genai", MagicMock())
sys.modules.setdefault("google.genai.types", _genai_types)

from solace_agent_mesh.agent.protocol.event_handlers import (
    _inject_scheduler_conversation_history,
)


def _make_component(session_exists=True):
    component = MagicMock()
    component.log_identifier = "[Test]"
    if session_exists:
        component.session_service.get_session = AsyncMock(return_value=MagicMock())
    else:
        component.session_service.get_session = AsyncMock(return_value=None)
    return component


class TestEmptyHistory:
    """The function should return immediately for empty or missing history."""

    @pytest.mark.asyncio
    async def test_none_history(self):
        component = _make_component()
        await _inject_scheduler_conversation_history(
            component, "agent", "user", "sess-1", None, "task-1"
        )
        component.session_service.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_list_history(self):
        component = _make_component()
        await _inject_scheduler_conversation_history(
            component, "agent", "user", "sess-1", [], "task-1"
        )
        component.session_service.get_session.assert_not_called()


class TestSessionNotFound:
    """When the ADK session is not found, the function should return without error."""

    @pytest.mark.asyncio
    async def test_session_not_found_returns_early(self):
        component = _make_component(session_exists=False)
        history = [{"role": "user", "content": "hello"}]
        # Should not raise
        await _inject_scheduler_conversation_history(
            component, "agent", "user", "sess-1", history, "task-1"
        )


class TestRoleMappingAndInjection:
    """Verify user/assistant entries are mapped and injected correctly."""

    @pytest.mark.asyncio
    async def test_injects_user_and_assistant(self):
        component = _make_component()
        history = [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ]
        mock_append = AsyncMock()
        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            mock_append,
        ):
            await _inject_scheduler_conversation_history(
                component, "agent", "user", "sess-1", history, "task-1"
            )
        assert mock_append.await_count == 2


class TestInvalidEntriesSkipped:
    """Entries with invalid roles or missing content should be skipped."""

    @pytest.mark.asyncio
    async def test_skips_invalid_entries(self):
        component = _make_component()
        history = [
            {"role": "unknown", "content": "skip me"},
            {"role": "user", "content": ""},
            {"role": "user", "content": "valid"},
        ]
        mock_append = AsyncMock()
        with patch(
            "solace_agent_mesh.agent.adk.services.append_event_with_retry",
            mock_append,
        ):
            await _inject_scheduler_conversation_history(
                component, "agent", "user", "sess-1", history, "task-1"
            )
        # Only the last valid entry should be appended
        assert mock_append.await_count == 1


class TestErrorSwallowing:
    """Exceptions during injection should be caught and logged, not raised."""

    @pytest.mark.asyncio
    async def test_exception_is_swallowed(self):
        component = _make_component()
        component.session_service.get_session = AsyncMock(side_effect=RuntimeError("boom"))
        history = [{"role": "user", "content": "hello"}]
        # Should not raise
        await _inject_scheduler_conversation_history(
            component, "agent", "user", "sess-1", history, "task-1"
        )
