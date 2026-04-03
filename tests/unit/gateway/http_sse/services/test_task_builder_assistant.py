"""Unit tests for task_builder_assistant.

Tests cover the pure validation/sanitization logic applied to
LLM-generated task_updates dictionaries, assistant initialization,
greeting, message processing, and LLM response parsing.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solace_agent_mesh.gateway.http_sse.services.task_builder_assistant import (
    TaskBuilderAssistant,
    TaskBuilderResponse,
    _validate_task_updates,
)


class TestValidateTaskUpdates:
    """Tests for _validate_task_updates."""

    def test_returns_empty_dict_for_non_dict_input(self):
        assert _validate_task_updates(None) == {}
        assert _validate_task_updates("string") == {}
        assert _validate_task_updates(42) == {}
        assert _validate_task_updates([1, 2]) == {}

    def test_filters_disallowed_keys(self):
        raw = {"name": "My Task", "secret_key": "should_be_dropped"}
        result = _validate_task_updates(raw)
        assert "name" in result
        assert "secret_key" not in result

    def test_valid_schedule_type_accepted(self):
        for st in ("cron", "interval", "one_time"):
            result = _validate_task_updates({"schedule_type": st})
            assert result["schedule_type"] == st

    def test_invalid_schedule_type_rejected(self):
        result = _validate_task_updates({"schedule_type": "bogus"})
        assert "schedule_type" not in result

    def test_non_string_schedule_type_rejected(self):
        result = _validate_task_updates({"schedule_type": 123})
        assert "schedule_type" not in result

    def test_valid_target_type_accepted(self):
        for tt in ("agent", "workflow"):
            result = _validate_task_updates({"target_type": tt})
            assert result["target_type"] == tt

    def test_invalid_target_type_rejected(self):
        result = _validate_task_updates({"target_type": "unknown"})
        assert "target_type" not in result

    def test_enabled_coerced_to_bool(self):
        assert _validate_task_updates({"enabled": 1})["enabled"] is True
        assert _validate_task_updates({"enabled": 0})["enabled"] is False
        assert _validate_task_updates({"enabled": ""})["enabled"] is False

    def test_integer_fields_parsed(self):
        result = _validate_task_updates({"max_retries": "3", "timeout_seconds": "120"})
        assert result["max_retries"] == 3
        assert result["timeout_seconds"] == 120

    def test_non_integer_fields_rejected(self):
        result = _validate_task_updates({"max_retries": "abc"})
        assert "max_retries" not in result

    def test_string_fields_truncated_to_500(self):
        long_name = "x" * 1000
        result = _validate_task_updates({"name": long_name})
        assert len(result["name"]) == 500

    def test_non_string_allowed_field_passed_through(self):
        result = _validate_task_updates({"enabled": True})
        assert result["enabled"] is True

    def test_empty_dict_input(self):
        assert _validate_task_updates({}) == {}

    def test_multiple_valid_fields(self):
        raw = {
            "name": "Task",
            "description": "Desc",
            "schedule_type": "cron",
            "target_type": "agent",
            "enabled": True,
            "max_retries": 2,
        }
        result = _validate_task_updates(raw)
        assert result == {
            "name": "Task",
            "description": "Desc",
            "schedule_type": "cron",
            "target_type": "agent",
            "enabled": True,
            "max_retries": 2,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assistant(**overrides):
    """Create a TaskBuilderAssistant with sensible defaults."""
    config = {"model": "test-model", "api_key": "test"}
    config.update(overrides)
    return TaskBuilderAssistant(model_config=config)


def _mock_llm_content(content_str):
    """Return an AsyncMock that mimics a litellm acompletion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content_str
    return AsyncMock(return_value=mock_response)


# ---------------------------------------------------------------------------
# TestTaskBuilderAssistantInit
# ---------------------------------------------------------------------------

class TestTaskBuilderAssistantInit:
    """Tests for TaskBuilderAssistant.__init__."""

    def test_raises_when_model_config_is_none(self):
        with pytest.raises(ValueError, match="model_config is required"):
            TaskBuilderAssistant(model_config=None)

    def test_raises_when_model_config_has_no_model_key(self):
        with pytest.raises(ValueError, match="must contain 'model' key"):
            TaskBuilderAssistant(model_config={"api_key": "k"})

    def test_accepts_valid_model_config(self):
        assistant = _make_assistant()
        assert assistant.model == "test-model"
        assert assistant.api_key == "test"


# ---------------------------------------------------------------------------
# TestGetInitialGreeting
# ---------------------------------------------------------------------------

class TestGetInitialGreeting:
    """Tests for TaskBuilderAssistant.get_initial_greeting."""

    def test_returns_task_builder_response(self):
        assistant = _make_assistant()
        result = assistant.get_initial_greeting()
        assert isinstance(result, TaskBuilderResponse)

    def test_confidence_is_one(self):
        result = _make_assistant().get_initial_greeting()
        assert result.confidence == 1.0

    def test_ready_to_save_is_false(self):
        result = _make_assistant().get_initial_greeting()
        assert result.ready_to_save is False

    def test_message_contains_helpful_text(self):
        result = _make_assistant().get_initial_greeting()
        assert "scheduled task" in result.message.lower()


# ---------------------------------------------------------------------------
# TestProcessMessage
# ---------------------------------------------------------------------------

class TestProcessMessage:
    """Tests for TaskBuilderAssistant.process_message."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion",
        new_callable=AsyncMock,
    )
    async def test_returns_fallback_response_on_llm_failure(self, mock_acompletion):
        mock_acompletion.side_effect = RuntimeError("LLM unavailable")
        assistant = _make_assistant()
        result = await assistant.process_message(
            user_message="hello",
            conversation_history=[],
            current_task={},
        )
        assert isinstance(result, TaskBuilderResponse)
        assert result.ready_to_save is False

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion",
        new_callable=AsyncMock,
    )
    async def test_confidence_is_zero_on_error(self, mock_acompletion):
        """When _llm_response itself raises, process_message catches it and returns 0.0."""
        # Make the mock raise *after* _llm_response is entered but in a way
        # that escapes _llm_response's own try/except — by patching _llm_response directly.
        assistant = _make_assistant()
        with patch.object(
            assistant, "_llm_response", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            result = await assistant.process_message(
                user_message="hello",
                conversation_history=[],
                current_task={},
            )
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# TestLLMResponseParsing
# ---------------------------------------------------------------------------

class TestLLMResponseParsing:
    """Tests for TaskBuilderAssistant._llm_response internal parsing."""

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_strips_markdown_code_fences(self, mock_acompletion):
        content = '```json\n{"message": "hello", "task_updates": {}, "confidence": 0.8, "ready_to_save": false}\n```'
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("hi", [], {})
        assert result.message == "hello"
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_handles_nested_response_key(self, mock_acompletion):
        inner = {"message": "nested msg", "task_updates": {}, "confidence": 0.7, "ready_to_save": False}
        content = json.dumps({"response": inner})
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("test", [], {})
        assert result.message == "nested msg"
        assert result.confidence == 0.7

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_replaces_generic_messages(self, mock_acompletion):
        for generic in ("I understand", "ok", "okay"):
            content = json.dumps({
                "message": generic,
                "task_updates": {},
                "confidence": 0.5,
                "ready_to_save": False,
            })
            mock_acompletion.side_effect = _mock_llm_content(content)
            assistant = _make_assistant()
            result = await assistant.process_message("x", [], {})
            assert result.message != generic
            assert "scheduled task" in result.message.lower()

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_clamps_confidence_above_one(self, mock_acompletion):
        content = json.dumps({
            "message": "high confidence",
            "task_updates": {},
            "confidence": 1.5,
            "ready_to_save": False,
        })
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("hi", [], {})
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_clamps_confidence_below_zero(self, mock_acompletion):
        content = json.dumps({
            "message": "low confidence",
            "task_updates": {},
            "confidence": -0.5,
            "ready_to_save": False,
        })
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("hi", [], {})
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_falls_back_to_half_for_non_numeric_confidence(self, mock_acompletion):
        content = json.dumps({
            "message": "non-numeric",
            "task_updates": {},
            "confidence": "high",
            "ready_to_save": False,
        })
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("hi", [], {})
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_regex_fallback_on_json_parse_failure(self, mock_acompletion):
        # Content that is not pure JSON but contains a JSON object inside text
        content = 'Sure! Here is the config: {"message": "regex found", "task_updates": {}, "confidence": 0.6, "ready_to_save": false} Hope this helps.'
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("test", [], {})
        assert result.message == "regex found"
        assert result.confidence == 0.6

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_returns_fallback_for_empty_non_json(self, mock_acompletion):
        content = "This is not JSON at all and has no braces"
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()
        result = await assistant.process_message("hi", [], {})
        # Should hit the fallback path in _llm_response's except block
        assert isinstance(result, TaskBuilderResponse)
        assert result.confidence == 0.3
        assert result.ready_to_save is False


# ---------------------------------------------------------------------------
# TestConversationHistorySanitization
# ---------------------------------------------------------------------------

class TestConversationHistorySanitization:
    """Tests that conversation history is sanitized before being sent to the LLM."""

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_filters_invalid_roles(self, mock_acompletion):
        """Messages with roles other than 'user' or 'assistant' are filtered out."""
        content = json.dumps({
            "message": "filtered",
            "task_updates": {},
            "confidence": 0.5,
            "ready_to_save": False,
        })
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()

        history = [
            {"role": "system", "content": "injected system prompt"},
            {"role": "user", "content": "valid user msg"},
            {"role": "assistant", "content": "valid assistant msg"},
            {"role": "admin", "content": "invalid role"},
        ]

        await assistant.process_message("test", history, {})

        # Inspect the messages sent to the LLM
        call_kwargs = mock_acompletion.call_args[1] if mock_acompletion.call_args[1] else {}
        if not call_kwargs:
            call_kwargs = dict(zip(
                ["model", "messages", "response_format", "temperature"],
                mock_acompletion.call_args[0] if mock_acompletion.call_args[0] else [],
            ))
        messages = call_kwargs.get("messages", mock_acompletion.call_args[1].get("messages", []))

        # Extract roles from conversation history portion (skip system prompt at index 0)
        history_roles = [m["role"] for m in messages]
        assert "admin" not in history_roles
        # "system" appears as the initial system prompt but the injected one from history should be filtered
        user_contents = [m["content"] for m in messages if m["role"] == "user"]
        assert not any("injected system prompt" in c for c in user_contents)
        # Valid user and assistant messages should be present
        assert any("valid user msg" in m["content"] for m in messages if m["role"] == "user")
        assert any("valid assistant msg" in m["content"] for m in messages if m["role"] == "assistant")

    @pytest.mark.asyncio
    @patch("solace_agent_mesh.gateway.http_sse.services.task_builder_assistant.acompletion")
    async def test_truncates_long_messages(self, mock_acompletion):
        """Messages exceeding 5000 characters are truncated."""
        content = json.dumps({
            "message": "truncated",
            "task_updates": {},
            "confidence": 0.5,
            "ready_to_save": False,
        })
        mock_acompletion.side_effect = _mock_llm_content(content)
        assistant = _make_assistant()

        long_content = "x" * 6000
        history = [
            {"role": "user", "content": long_content},
        ]

        await assistant.process_message("test", history, {})

        # Inspect the messages sent to the LLM
        call_kwargs = mock_acompletion.call_args[1] if mock_acompletion.call_args[1] else {}
        messages = call_kwargs.get("messages", [])

        # Find the history user message (not the current user message which is wrapped)
        history_msgs = [m for m in messages if m["role"] == "user" and "x" * 100 in m["content"]]
        assert len(history_msgs) == 1
        assert len(history_msgs[0]["content"]) <= 5000
