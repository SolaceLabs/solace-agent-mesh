"""
Unit tests for TitleGenerationService.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.http_sse.services.title_generation_service import (
    TitleGenerationService,
)
from solace_agent_mesh.gateway.http_sse.services.title_generation_constants import (
    TITLE_CHAR_LIMIT,
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


def _create_service_with_mock_llm(llm_return=None):
    """Create a TitleGenerationService with a mocked LiteLlm."""
    mock_llm = MagicMock()
    if llm_return is not None:
        mock_llm.generate_content_async = MagicMock(
            return_value=_async_gen(llm_return)
        )
    service = TitleGenerationService(mock_llm)
    return service


class TestTitleGenerationService:
    """Tests for TitleGenerationService."""

    def test_truncate_text(self):
        """Test text truncation."""
        service =  _create_service_with_mock_llm()

        assert service._truncate_text("Hello", 50) == "Hello"
        assert service._truncate_text("A" * 100, 50) == "A" * 50 + "..."
        assert service._truncate_text("", 50) == ""
        assert service._truncate_text(None, 50) == ""

    def test_fallback_title(self):
        """Test fallback title generation."""
        service = _create_service_with_mock_llm()

        assert service._fallback_title("Hello") == "Hello"
        assert service._fallback_title("A" * 100) == "A" * TITLE_CHAR_LIMIT + "..."
        assert service._fallback_title("") == "New Chat"
        assert service._fallback_title(None) == "New Chat"

    @pytest.mark.asyncio
    async def test_call_litellm_success(self):
        """Test successful LiteLLM call."""
        mock_resp = _mock_llm_response("Test Title")
        service = _create_service_with_mock_llm(
            model_config={"model": "gpt-4", "api_key": "test-key"},
            llm_return=mock_resp,
        )

        result = await service._call_litellm("Hello", "Hi there!")

        assert result == "Test Title"

    @pytest.mark.asyncio
    async def test_call_litellm_strips_quotes(self):
        """Test LiteLLM strips quotes from title."""
        mock_resp = _mock_llm_response('"Test Title"')
        service = _create_service_with_mock_llm(llm_return=mock_resp)

        result = await service._call_litellm("Hello", "Hi")

        assert result == "Test Title"

    @pytest.mark.asyncio
    async def test_call_litellm_fallback_on_error(self):
        """Test LiteLLM uses fallback on error."""
        service = _create_service_with_mock_llm()

        async def _raise_error(*args, **kwargs):
            raise Exception("API Error")
            yield  # noqa: unreachable - makes this an async generator

        service.llm.generate_content_async = MagicMock(side_effect=_raise_error)

        result = await service._call_litellm("Hello world", "Hi")

        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_and_update_title_success(self):
        """Test successful title generation and update."""
        mock_resp = _mock_llm_response("Generated Title")
        service = _create_service_with_mock_llm(llm_return=mock_resp)
        mock_callback = AsyncMock()

        await service._generate_and_update_title(
            session_id="test-session",
            user_message="Hello",
            agent_response="Hi there!",
            update_callback=mock_callback,
        )

        mock_callback.assert_called_once_with("Generated Title")

    @pytest.mark.asyncio
    async def test_generate_title_async(self):
        """Test async title generation creates background task."""
        mock_resp = _mock_llm_response("Generated Title")
        service = _create_service_with_mock_llm(llm_return=mock_resp)
        mock_callback = AsyncMock()

        await service.generate_title_async(
            session_id="test-session",
            user_message="Hello",
            agent_response="Hi there!",
            user_id="test-user",
            update_callback=mock_callback,
        )
        await asyncio.sleep(0.1)

        mock_callback.assert_called_once_with("Generated Title")
