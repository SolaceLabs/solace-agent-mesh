"""
Unit tests for PromptBuilderAssistant.
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    NotFoundError,
    APIConnectionError,
    ContextWindowExceededError,
    ContentPolicyViolationError,
)

from solace_agent_mesh.common.error_handlers import (
    AUTHENTICATION_ERROR_MESSAGE,
    RATE_LIMIT_ERROR_MESSAGE,
    TIMEOUT_ERROR_MESSAGE,
    NOT_FOUND_ERROR_MESSAGE,
    API_CONNECTION_ERROR_MESSAGE,
    CONTEXT_LIMIT_ERROR_MESSAGE,
    CONTENT_POLICY_VIOLATION_MESSAGE,
)
from solace_agent_mesh.gateway.http_sse.services.prompt_builder_assistant import (
    PromptBuilderAssistant,
    PromptBuilderResponse,
)


def _make_litellm_exception(cls, message="test error"):
    """Helper to create litellm exception instances."""
    try:
        return cls(message=message, model="test-model", llm_provider="test")
    except TypeError:
        try:
            return cls(message=message)
        except TypeError:
            return cls(message)


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
        """Test that an LLM error returns a fallback response with is_error=True."""
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
        assert result.confidence == 0.0
        assert result.ready_to_save is False
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_process_message_handles_invalid_json(self):
        """Test that invalid JSON from LLM triggers fallback with is_error=True."""
        mock_resp = _mock_llm_response("not valid json at all")
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a template",
            conversation_history=[],
            current_template={},
        )

        assert isinstance(result, PromptBuilderResponse)
        assert result.confidence == 0.0
        assert result.is_error is True

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


class TestPromptBuilderResponseIsError:
    """Tests for the is_error field on PromptBuilderResponse."""

    def test_is_error_defaults_to_false(self):
        """is_error should default to False for normal responses."""
        resp = PromptBuilderResponse(message="Hello", confidence=1.0)
        assert resp.is_error is False

    def test_is_error_can_be_set_true(self):
        """is_error should be settable to True."""
        resp = PromptBuilderResponse(message="Error", confidence=0.0, is_error=True)
        assert resp.is_error is True

    @pytest.mark.asyncio
    async def test_successful_response_is_not_error(self):
        """A successful LLM response should have is_error=False."""
        llm_response_json = json.dumps({
            "message": "Great template!",
            "template_updates": {"name": "Test"},
            "confidence": 0.9,
            "ready_to_save": True,
        })
        mock_resp = _mock_llm_response(llm_response_json)
        assistant = _create_assistant(llm_return=mock_resp)

        result = await assistant.process_message(
            user_message="Create a template",
            conversation_history=[],
            current_template={},
        )

        assert result.is_error is False

    def test_initial_greeting_is_not_error(self):
        """The initial greeting should have is_error=False."""
        assistant = _create_assistant()
        greeting = assistant.get_initial_greeting()
        assert greeting.is_error is False


class TestPromptBuilderLlmExceptionHandling:
    """Tests for LLM exception-specific error handling in _llm_response()."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc_class, expected_message",
        [
            (AuthenticationError, AUTHENTICATION_ERROR_MESSAGE),
            (RateLimitError, RATE_LIMIT_ERROR_MESSAGE),
            (Timeout, TIMEOUT_ERROR_MESSAGE),
            (NotFoundError, NOT_FOUND_ERROR_MESSAGE),
            (APIConnectionError, API_CONNECTION_ERROR_MESSAGE),
            (ContextWindowExceededError, CONTEXT_LIMIT_ERROR_MESSAGE),
            (ContentPolicyViolationError, CONTENT_POLICY_VIOLATION_MESSAGE),
        ],
    )
    async def test_llm_exception_returns_descriptive_message(
        self, exc_class, expected_message
    ):
        """Each litellm exception should produce its specific error message."""
        exc = _make_litellm_exception(exc_class)
        mock_llm = MagicMock()

        async def _raise_exc(*args, **kwargs):
            raise exc
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_exc)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert result.message == expected_message
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_llm_exception_sets_is_error_true(self):
        """LLM exceptions should set is_error=True."""
        exc = _make_litellm_exception(AuthenticationError)
        mock_llm = MagicMock()

        async def _raise_exc(*args, **kwargs):
            raise exc
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_exc)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert result.is_error is True
        assert result.confidence == 0.0
        assert result.ready_to_save is False

    @pytest.mark.asyncio
    async def test_non_llm_exception_returns_generic_message(self):
        """Non-litellm exceptions should return a generic fallback message."""
        mock_llm = MagicMock()

        async def _raise_error(*args, **kwargs):
            raise RuntimeError("something broke")
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_error)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert result.is_error is True
        assert "trouble processing" in result.message.lower()

    @pytest.mark.asyncio
    async def test_non_llm_exception_does_not_leak_details(self):
        """Non-litellm exceptions should not expose raw error details."""
        mock_llm = MagicMock()

        async def _raise_error(*args, **kwargs):
            raise RuntimeError("SECRET_KEY=abc123")
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_error)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert "SECRET_KEY" not in result.message

    @pytest.mark.asyncio
    async def test_llm_exception_does_not_include_template_updates(self):
        """Error responses should not include template updates."""
        exc = _make_litellm_exception(RateLimitError)
        mock_llm = MagicMock()

        async def _raise_exc(*args, **kwargs):
            raise exc
            yield  # noqa: unreachable

        mock_llm.generate_content_async = MagicMock(side_effect=_raise_exc)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="Create something",
            conversation_history=[],
            current_template={},
        )

        assert result.template_updates == {}


class TestProcessMessageOuterCatch:
    """Tests for the outer exception handler in process_message()."""

    @pytest.mark.asyncio
    async def test_outer_catch_with_llm_exception(self):
        """If _llm_response itself raises a litellm exception, it should be handled."""
        exc = _make_litellm_exception(ServiceUnavailableError)
        mock_llm = MagicMock()

        # Make _llm_response raise before even calling the LLM
        # by making generate_content_async raise synchronously
        mock_llm.generate_content_async = MagicMock(side_effect=exc)
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="test",
            conversation_history=[],
            current_template={},
        )

        assert result.is_error is True
        assert "administrator" in result.message or "rephrase" in result.message

    @pytest.mark.asyncio
    async def test_outer_catch_with_generic_exception(self):
        """If _llm_response raises a non-litellm exception, generic message is returned."""
        mock_llm = MagicMock()
        mock_llm.generate_content_async = MagicMock(
            side_effect=TypeError("bad argument")
        )
        assistant = PromptBuilderAssistant(llm=mock_llm)

        result = await assistant.process_message(
            user_message="test",
            conversation_history=[],
            current_template={},
        )

        assert result.is_error is True
        assert "bad argument" not in result.message
