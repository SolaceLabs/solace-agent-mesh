"""
Unit tests for PromptBuilderAssistant.
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from solace_agent_mesh.gateway.http_sse.services.prompt_builder_assistant import (
    PromptBuilderAssistant,
    PromptBuilderResponse,
)


def _mock_llm_response(text):
    """Create a mock LlmResponse with the given text content."""
    mock_part = MagicMock()
    mock_part.text = text
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.content = mock_content
    return mock_response


async def _async_gen(*responses):
    """Create an async generator yielding the given responses."""
    for r in responses:
        yield r


def _create_assistant(llm_return=None, db=None):
    """Create a PromptBuilderAssistant with a mocked LLM."""
    mock_llm = MagicMock()
    if llm_return is not None:
        mock_llm.generate_content_async = MagicMock(
            return_value=_async_gen(llm_return)
        )
    return PromptBuilderAssistant(llm=mock_llm, db=db)


class TestPromptBuilderAssistantInit:
    """Tests for PromptBuilderAssistant initialization."""

    def test_init_stores_llm(self):
        """Test that the llm is stored on the assistant."""
        mock_llm = MagicMock()
        assistant = PromptBuilderAssistant(llm=mock_llm)
        assert assistant.llm is mock_llm

    def test_init_stores_db(self):
        """Test that the db session is stored on the assistant."""
        mock_llm = MagicMock()
        mock_db = MagicMock()
        assistant = PromptBuilderAssistant(llm=mock_llm, db=mock_db)
        assert assistant.db is mock_db

    def test_init_db_defaults_to_none(self):
        """Test that db defaults to None."""
        mock_llm = MagicMock()
        assistant = PromptBuilderAssistant(llm=mock_llm)
        assert assistant.db is None


class TestPromptBuilderAssistantGreeting:
    """Tests for the initial greeting."""

    def test_get_initial_greeting(self):
        """Test that initial greeting returns a valid PromptBuilderResponse."""
        assistant = _create_assistant()
        greeting = assistant.get_initial_greeting()

        assert isinstance(greeting, PromptBuilderResponse)
        assert greeting.confidence == 1.0
        assert greeting.ready_to_save is False
        assert "template" in greeting.message.lower()


class TestPromptBuilderAssistantProcessMessage:
    """Tests for process_message using the BaseLlm interface."""

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test successful message processing with valid JSON response."""
        llm_response_json = json.dumps({
            "message": "I'll create a code review template for you.",
            "template_updates": {
                "name": "Code Review",
                "category": "Development",
            },
            "confidence": 0.8,
            "ready_to_save": False,
        })
        mock_resp = _mock_llm_response(llm_response_json)
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a code review template",
            conversation_history=[],
            current_template={},
        )

        assert isinstance(result, PromptBuilderResponse)
        assert "code review" in result.message.lower()
        assert result.template_updates["name"] == "Code Review"
        assert result.confidence == 0.8
        assert result.ready_to_save is False

    @pytest.mark.asyncio
    async def test_process_message_calls_generate_content_async(self):
        """Test that process_message invokes llm.generate_content_async."""
        llm_response_json = json.dumps({
            "message": "Hello!",
            "template_updates": {},
            "confidence": 0.5,
            "ready_to_save": False,
        })
        mock_resp = _mock_llm_response(llm_response_json)
        mock_llm = MagicMock()
        mock_llm.generate_content_async = MagicMock(
            return_value=_async_gen(mock_resp)
        )
        assistant = PromptBuilderAssistant(llm=mock_llm)

        await assistant.process_message(
            user_message="Help me",
            conversation_history=[],
            current_template={},
        )

        mock_llm.generate_content_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_builds_system_and_user_contents(self):
        """Test that system prompt and user messages are correctly split into LlmRequest."""
        llm_response_json = json.dumps({
            "message": "Got it.",
            "template_updates": {},
            "confidence": 0.5,
            "ready_to_save": False,
        })
        mock_resp = _mock_llm_response(llm_response_json)
        mock_llm = MagicMock()
        mock_llm.generate_content_async = MagicMock(
            return_value=_async_gen(mock_resp)
        )
        assistant = PromptBuilderAssistant(llm=mock_llm)

        await assistant.process_message(
            user_message="Create a template",
            conversation_history=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            current_template={"name": "Test"},
        )

        llm_request = mock_llm.generate_content_async.call_args[0][0]
        # System instruction should contain the system prompt
        assert llm_request.config.system_instruction is not None
        assert "CRITICAL RULES" in llm_request.config.system_instruction
        # Contents should have conversation history + current message
        assert len(llm_request.contents) == 3  # Hi, Hello!, Create a template

    @pytest.mark.asyncio
    async def test_process_message_fallback_on_llm_error(self):
        """Test that an LLM error returns a fallback response."""
        mock_llm = MagicMock()

        async def _raise_error(*args, **kwargs):
            raise Exception("LLM failure")
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_error)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert isinstance(result, PromptBuilderResponse)
        assert result.confidence <= 0.3
        assert result.ready_to_save is False

    @pytest.mark.asyncio
    async def test_process_message_handles_invalid_json(self):
        """Test that invalid JSON from LLM triggers fallback."""
        mock_resp = _mock_llm_response("not valid json at all")
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a template",
            conversation_history=[],
            current_template={},
        )

        assert isinstance(result, PromptBuilderResponse)
        assert result.confidence <= 0.3

    @pytest.mark.asyncio
    async def test_process_message_handles_generic_message(self):
        """Test that generic 'I understand' message is replaced with helpful one."""
        llm_response_json = json.dumps({
            "message": "I understand",
            "template_updates": {},
            "confidence": 0.5,
            "ready_to_save": False,
        })
        mock_resp = _mock_llm_response(llm_response_json)
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a template",
            conversation_history=[],
            current_template={},
        )

        assert "I understand" not in result.message
        assert "details" in result.message.lower() or "template" in result.message.lower()

    @pytest.mark.asyncio
    async def test_process_message_unwraps_nested_response(self):
        """Test that nested 'response' key is properly unwrapped."""
        llm_response_json = json.dumps({
            "response": {
                "message": "Here is your template.",
                "template_updates": {"name": "Test"},
                "confidence": 0.9,
                "ready_to_save": True,
            }
        })
        mock_resp = _mock_llm_response(llm_response_json)
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a template",
            conversation_history=[],
            current_template={},
        )

        assert result.message == "Here is your template."
        assert result.template_updates["name"] == "Test"
        assert result.ready_to_save is True
