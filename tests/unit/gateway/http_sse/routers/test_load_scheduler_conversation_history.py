"""Unit tests for _load_scheduler_conversation_history in tasks.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.gateway.http_sse.routers.tasks import (
    _load_scheduler_conversation_history,
    _scheduler_history_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure the TTLCache is empty before and after each test."""
    _scheduler_history_cache.clear()
    yield
    _scheduler_history_cache.clear()


def _make_chat_task(bubbles):
    """Create a mock ChatTask with the given message_bubbles."""
    task = MagicMock()
    task.message_bubbles = json.dumps(bubbles) if isinstance(bubbles, list) else bubbles
    return task


class TestNonScheduledSessionShortCircuit:
    """Sessions that don't start with 'scheduled_' should return None immediately."""

    def test_empty_session_id(self):
        assert _load_scheduler_conversation_history("", MagicMock(), "user-1", "[test] ") is None

    def test_none_session_id(self):
        assert _load_scheduler_conversation_history(None, MagicMock(), "user-1", "[test] ") is None

    def test_non_scheduled_prefix(self):
        assert _load_scheduler_conversation_history("regular_session", MagicMock(), "user-1", "[test] ") is None

    def test_none_factory(self):
        assert _load_scheduler_conversation_history("scheduled_123", None, "user-1", "[test] ") is None


class TestCacheHit:
    """When a session_id is already in the cache, the DB should not be queried."""

    def test_returns_cached_history(self):
        cached = [{"role": "user", "content": "hello"}]
        _scheduler_history_cache["scheduled_abc"] = cached
        factory = MagicMock()
        result = _load_scheduler_conversation_history("scheduled_abc", factory, "user-1", "[test] ")
        assert result is cached
        factory.assert_not_called()

    def test_returns_cached_none(self):
        _scheduler_history_cache["scheduled_abc"] = None
        factory = MagicMock()
        result = _load_scheduler_conversation_history("scheduled_abc", factory, "user-1", "[test] ")
        assert result is None
        factory.assert_not_called()


class TestCacheMissDBLookup:
    """When the cache misses, the function should query the DB and populate the cache."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.tasks.ChatTaskRepository")
    def test_no_tasks_found(self, mock_repo_cls):
        mock_repo = mock_repo_cls.return_value
        mock_repo.find_by_session.return_value = []
        db = MagicMock()
        factory = MagicMock(return_value=db)

        result = _load_scheduler_conversation_history("scheduled_x", factory, "user-1", "[test] ")
        assert result is None
        assert _scheduler_history_cache.get("scheduled_x") is None

    @patch("solace_agent_mesh.gateway.http_sse.routers.tasks.ChatTaskRepository")
    def test_extracts_user_and_agent_bubbles(self, mock_repo_cls):
        bubbles = [
            {"type": "user", "text": "What is 2+2?"},
            {"type": "agent", "text": "4"},
            {"type": "status", "text": "thinking..."},
        ]
        mock_repo = mock_repo_cls.return_value
        mock_repo.find_by_session.return_value = [_make_chat_task(bubbles)]
        db = MagicMock()
        factory = MagicMock(return_value=db)

        result = _load_scheduler_conversation_history("scheduled_y", factory, "user-1", "[test] ")
        assert result == [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        assert _scheduler_history_cache["scheduled_y"] == result


class TestMalformedJSON:
    """Malformed JSON in message_bubbles should be skipped gracefully."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.tasks.ChatTaskRepository")
    def test_invalid_json_skipped(self, mock_repo_cls):
        bad_task = MagicMock()
        bad_task.message_bubbles = "not valid json {{"
        good_task = _make_chat_task([{"type": "user", "text": "hi"}])
        mock_repo = mock_repo_cls.return_value
        mock_repo.find_by_session.return_value = [bad_task, good_task]
        db = MagicMock()
        factory = MagicMock(return_value=db)

        result = _load_scheduler_conversation_history("scheduled_z", factory, "user-1", "[test] ")
        assert result == [{"role": "user", "content": "hi"}]


class TestRoleMapping:
    """Verify that 'user' maps to 'user' and 'agent' maps to 'assistant'."""

    @patch("solace_agent_mesh.gateway.http_sse.routers.tasks.ChatTaskRepository")
    def test_role_mapping(self, mock_repo_cls):
        bubbles = [
            {"type": "user", "text": "a"},
            {"type": "agent", "text": "b"},
        ]
        mock_repo = mock_repo_cls.return_value
        mock_repo.find_by_session.return_value = [_make_chat_task(bubbles)]
        db = MagicMock()
        factory = MagicMock(return_value=db)

        result = _load_scheduler_conversation_history("scheduled_r", factory, "user-1", "[test] ")
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"


class TestDBExceptionHandling:
    """Exceptions during DB access should be caught and return None."""

    def test_factory_raises(self):
        factory = MagicMock(side_effect=RuntimeError("db down"))
        result = _load_scheduler_conversation_history("scheduled_err", factory, "user-1", "[test] ")
        assert result is None
