"""
Unit tests for the prompt_builder_chat endpoint in prompts router.

Tests verify:
1. is_error field is passed through from PromptBuilderResponse to PromptBuilderChatResponse
2. Outer exception handler returns is_error=True with sanitized message
3. Template updates and ready_to_save are forwarded correctly
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.http_sse.services.prompt_builder_assistant import (
    PromptBuilderResponse,
)
from solace_agent_mesh.gateway.http_sse.routers.dto.prompt_dto import (
    PromptBuilderChatRequest,
    PromptBuilderChatResponse,
)


class TestPromptBuilderChatResponseDTO:
    """Tests for the PromptBuilderChatResponse DTO."""

    def test_is_error_defaults_to_false(self):
        """is_error should default to False."""
        response = PromptBuilderChatResponse(message="Hello")
        assert response.is_error is False

    def test_is_error_can_be_set_true(self):
        """is_error should be settable to True."""
        response = PromptBuilderChatResponse(message="Error occurred", is_error=True)
        assert response.is_error is True

    def test_serialization_includes_is_error(self):
        """is_error should be included in JSON serialization."""
        response = PromptBuilderChatResponse(message="Error", is_error=True)
        data = response.model_dump()
        assert "is_error" in data
        assert data["is_error"] is True

    def test_serialization_includes_is_error_when_false(self):
        """is_error=False should also be included in serialization."""
        response = PromptBuilderChatResponse(message="OK")
        data = response.model_dump()
        assert "is_error" in data
        assert data["is_error"] is False

    def test_all_fields_present(self):
        """All response fields should be present."""
        response = PromptBuilderChatResponse(
            message="test",
            template_updates={"name": "Test"},
            confidence=0.9,
            ready_to_save=True,
            is_error=False,
        )
        data = response.model_dump()
        assert data["message"] == "test"
        assert data["template_updates"] == {"name": "Test"}
        assert data["confidence"] == 0.9
        assert data["ready_to_save"] is True
        assert data["is_error"] is False


class TestPromptBuilderChatEndpoint:
    """Tests for the prompt_builder_chat endpoint function."""

    @pytest.mark.asyncio
    async def test_success_response_passes_is_error_false(self):
        """Successful response should have is_error=False."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            prompt_builder_chat,
        )

        mock_response = PromptBuilderResponse(
            message="Here's your template!",
            template_updates={"name": "Test"},
            confidence=0.9,
            ready_to_save=True,
            is_error=False,
        )

        mock_component = MagicMock()
        mock_component.get_lite_llm_model.return_value = MagicMock()

        request = PromptBuilderChatRequest(
            message="Create a code review template",
            conversation_history=[],
            current_template={},
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.prompts.PromptBuilderAssistant"
        ) as MockAssistant:
            mock_assistant = MockAssistant.return_value
            mock_assistant.process_message = AsyncMock(return_value=mock_response)

            result = await prompt_builder_chat(
                request=request,
                db=MagicMock(),
                user_id="test-user",
                component=mock_component,
            )

        assert isinstance(result, PromptBuilderChatResponse)
        assert result.is_error is False
        assert result.message == "Here's your template!"
        assert result.template_updates == {"name": "Test"}
        assert result.confidence == 0.9
        assert result.ready_to_save is True

    @pytest.mark.asyncio
    async def test_error_response_passes_is_error_true(self):
        """Error response from assistant should have is_error=True."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            prompt_builder_chat,
        )

        mock_response = PromptBuilderResponse(
            message="The LLM service rejected the authentication credentials.",
            confidence=0.0,
            ready_to_save=False,
            is_error=True,
        )

        mock_component = MagicMock()
        mock_component.get_lite_llm_model.return_value = MagicMock()

        request = PromptBuilderChatRequest(
            message="Create something",
            conversation_history=[],
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.prompts.PromptBuilderAssistant"
        ) as MockAssistant:
            mock_assistant = MockAssistant.return_value
            mock_assistant.process_message = AsyncMock(return_value=mock_response)

            result = await prompt_builder_chat(
                request=request,
                db=MagicMock(),
                user_id="test-user",
                component=mock_component,
            )

        assert result.is_error is True
        assert result.confidence == 0.0
        assert result.template_updates == {}

    @pytest.mark.asyncio
    async def test_outer_exception_returns_error_response(self):
        """Outer exception handler should return is_error=True, not raise HTTPException."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            prompt_builder_chat,
        )

        mock_component = MagicMock()
        mock_component.get_lite_llm_model.side_effect = RuntimeError("LLM not configured")

        request = PromptBuilderChatRequest(
            message="Create something",
            conversation_history=[],
        )

        result = await prompt_builder_chat(
            request=request,
            db=MagicMock(),
            user_id="test-user",
            component=mock_component,
        )

        # Should return a response, not raise an exception
        assert isinstance(result, PromptBuilderChatResponse)
        assert result.is_error is True
        assert "administrator" in result.message
        assert result.template_updates == {}
        assert result.ready_to_save is False

    @pytest.mark.asyncio
    async def test_outer_exception_does_not_leak_details(self):
        """Outer exception handler should not leak raw error details."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            prompt_builder_chat,
        )

        mock_component = MagicMock()
        mock_component.get_lite_llm_model.side_effect = RuntimeError(
            "SECRET_CONNECTION_STRING=postgres://user:pass@host"
        )

        request = PromptBuilderChatRequest(
            message="Create something",
            conversation_history=[],
        )

        result = await prompt_builder_chat(
            request=request,
            db=MagicMock(),
            user_id="test-user",
            component=mock_component,
        )

        assert "SECRET_CONNECTION_STRING" not in result.message
        assert "postgres" not in result.message
