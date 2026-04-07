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


class TestGetComponentNameHelper:
    """Tests for get_component_name() helper function."""

    def test_get_component_name_for_agent(self):
        """Agent components should return the actual agent_name."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            get_component_name,
        )

        mock_component = MagicMock()
        mock_component.agent_name = "my-test-agent"

        result = get_component_name(mock_component)

        assert result == "my-test-agent"

    def test_get_component_name_for_gateway(self):
        """Gateway components should return 'gateway' literal (not gateway_id)."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            get_component_name,
        )

        # Simulate WebUIBackendComponent (has gateway_id, NOT agent_name)
        mock_component = MagicMock()
        mock_component.gateway_id = "test-gateway-123"
        # Explicitly delete agent_name to simulate real gateway component
        del mock_component.agent_name

        result = get_component_name(mock_component)

        assert result == "gateway"

    def test_get_component_name_for_workflow(self):
        """Workflow components should return 'workflow' literal (not workflow_name)."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            get_component_name,
        )

        # Simulate workflow component (has workflow_name, NOT agent_name or gateway_id)
        mock_component = MagicMock()
        mock_component.workflow_name = "test-workflow-456"
        del mock_component.agent_name
        del mock_component.gateway_id

        result = get_component_name(mock_component)

        assert result == "workflow"

    def test_get_component_name_for_unknown(self):
        """Unknown components should return 'unknown'."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            get_component_name,
        )

        # Simulate component with no identifying attributes
        mock_component = MagicMock()
        del mock_component.agent_name
        del mock_component.gateway_id
        del mock_component.workflow_name

        result = get_component_name(mock_component)

        assert result == "unknown"


class TestPromptBuilderChatObservability:
    """Tests for ObservabilityContext integration in prompt_builder_chat."""

    @pytest.mark.asyncio
    async def test_observability_context_with_gateway_component(self):
        """Test that gateway component uses 'gateway' literal for observability."""
        from solace_agent_mesh.gateway.http_sse.routers.prompts import (
            prompt_builder_chat,
        )
        from unittest.mock import patch

        # Create mock that simulates WebUIBackendComponent
        mock_component = MagicMock()
        mock_component.gateway_id = "test-gateway-123"
        del mock_component.agent_name  # Gateway doesn't have agent_name
        mock_component.get_lite_llm_model.return_value = MagicMock()

        request = PromptBuilderChatRequest(
            message="Create a template",
            conversation_history=[],
            current_template={},
        )

        mock_response = PromptBuilderResponse(
            message="OK",
            confidence=0.9,
            ready_to_save=True,
            is_error=False,
        )

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.prompts.PromptBuilderAssistant"
        ) as MockAssistant, patch(
            "solace_agent_mesh.agent.adk.models.lite_llm.ObservabilityContext"
        ) as MockObservabilityContext:
            mock_assistant = MockAssistant.return_value
            mock_assistant.process_message = AsyncMock(return_value=mock_response)

            # Mock the context manager
            mock_context = MagicMock()
            MockObservabilityContext.return_value.__enter__ = MagicMock(
                return_value=mock_context
            )
            MockObservabilityContext.return_value.__exit__ = MagicMock(
                return_value=False
            )

            await prompt_builder_chat(
                request=request,
                db=MagicMock(),
                user_id="test-user",
                component=mock_component,
            )

            # Verify ObservabilityContext was called with "gateway" not component.agent_name
            MockObservabilityContext.assert_called_once_with(
                component_name="gateway", owner_id="test-user"
            )
