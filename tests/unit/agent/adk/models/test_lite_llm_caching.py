"""Unit tests for LiteLlm prompt caching functionality."""

import pytest
from unittest.mock import Mock, patch
from google.genai.types import Content, Part, GenerateContentConfig
from google.adk.models.llm_request import LlmRequest

from solace_agent_mesh.agent.adk.models.lite_llm import (
    LiteLlm,
    _get_completion_inputs,
)


@pytest.fixture
def sample_llm_config():
    """Sample LLM config with system instruction."""
    return GenerateContentConfig(
        system_instruction="You are a helpful assistant with access to tools.",
    )


@pytest.fixture
def sample_llm_request_with_system():
    """Sample LLM request with system instruction."""
    content = Content(role="user", parts=[Part(text="Hello")])
    config = GenerateContentConfig(
        system_instruction="You are a helpful assistant."
    )
    return LlmRequest(contents=[content], config=config)


class TestLiteLlmCacheStrategyInitialization:
    """Test cache strategy initialization and validation."""

    def test_init_with_default_cache_strategy(self):
        """Test LiteLlm initializes with default 5m cache strategy."""
        llm = LiteLlm(model="test-model")
        assert llm._cache_strategy == "5m"

    def test_init_with_explicit_5m_strategy(self):
        """Test LiteLlm initializes with explicit 5m strategy."""
        llm = LiteLlm(model="test-model", cache_strategy="5m")
        assert llm._cache_strategy == "5m"

    def test_init_with_1h_strategy(self):
        """Test LiteLlm initializes with 1h strategy."""
        llm = LiteLlm(model="test-model", cache_strategy="1h")
        assert llm._cache_strategy == "1h"

    def test_init_with_none_strategy(self):
        """Test LiteLlm initializes with none strategy (caching disabled)."""
        llm = LiteLlm(model="test-model", cache_strategy="none")
        assert llm._cache_strategy == "none"

    def test_init_with_invalid_strategy_defaults_to_5m(self):
        """Test invalid cache strategy falls back to 5m with warning."""
        with patch("solace_agent_mesh.agent.adk.models.lite_llm.logger") as mock_logger:
            llm = LiteLlm(model="test-model", cache_strategy="invalid")

            # Should default to 5m
            assert llm._cache_strategy == "5m"

            # Should log warning
            mock_logger.warning.assert_called_once()
            assert "Invalid cache_strategy" in mock_logger.warning.call_args[0][0]

    def test_init_logs_cache_strategy(self):
        """Test that cache strategy is logged on initialization."""
        with patch("solace_agent_mesh.agent.adk.models.lite_llm.logger") as mock_logger:
            llm = LiteLlm(model="test-model", cache_strategy="1h")

            # Should log the strategy
            mock_logger.info.assert_called()
            # Check if any info log contains cache strategy message
            found = False
            for call in mock_logger.info.call_args_list:
                call_str = str(call).lower()
                if "cache" in call_str and "1h" in call_str:
                    found = True
                    break
            assert found, f"Expected cache strategy log not found. Logs: {mock_logger.info.call_args_list}"


class TestGetCompletionInputsSystemInstructionCaching:
    """Test _get_completion_inputs system instruction caching."""

    def test_system_instruction_with_5m_cache(self, sample_llm_request_with_system):
        """Test system instruction formatted with 5m cache control."""
        messages, _, _, _ = _get_completion_inputs(
            sample_llm_request_with_system,
            cache_strategy="5m"
        )

        # First message should be system instruction with cache control
        assert len(messages) > 0
        system_msg = messages[0]
        assert system_msg["role"] == "developer"
        assert isinstance(system_msg["content"], list)
        assert len(system_msg["content"]) == 1

        content_block = system_msg["content"][0]
        assert content_block["type"] == "text"
        assert content_block["text"] == "You are a helpful assistant."
        assert "cache_control" in content_block
        assert content_block["cache_control"] == {"type": "ephemeral"}

    def test_system_instruction_with_1h_cache(self, sample_llm_request_with_system):
        """Test system instruction formatted with 1h cache control."""
        messages, _, _, _ = _get_completion_inputs(
            sample_llm_request_with_system,
            cache_strategy="1h"
        )

        system_msg = messages[0]
        content_block = system_msg["content"][0]
        assert "cache_control" in content_block
        assert content_block["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_system_instruction_with_none_cache(self, sample_llm_request_with_system):
        """Test system instruction without cache control when caching disabled."""
        messages, _, _, _ = _get_completion_inputs(
            sample_llm_request_with_system,
            cache_strategy="none"
        )

        system_msg = messages[0]
        content_block = system_msg["content"][0]
        assert "cache_control" not in content_block

    @pytest.mark.skip(reason="ADK 1.18 requires config to be non-None")
    def test_no_system_instruction_no_error(self):
        """Test that no system instruction doesn't cause errors."""
        content = Content(role="user", parts=[Part(text="Hello")])
        request = LlmRequest(contents=[content], config=None)

        messages, _, _, _ = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        # Should only have user message, no system message
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


class TestGetCompletionInputsToolCaching:
    """Test _get_completion_inputs tool definition caching."""

    def test_tools_with_5m_cache(self):
        """Test tools formatted with 5m cache control on last tool."""
        from google.genai.types import FunctionDeclaration, Tool

        tools = [
            FunctionDeclaration(name="tool1", description="First tool"),
            FunctionDeclaration(name="tool2", description="Second tool"),
            FunctionDeclaration(name="tool3", description="Third tool"),
        ]

        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig(tools=[Tool(function_declarations=tools)])
        request = LlmRequest(contents=[content], config=config)

        _, converted_tools, _, _ = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        assert len(converted_tools) == 3

        # First two tools should NOT have cache_control
        assert "cache_control" not in converted_tools[0]
        assert "cache_control" not in converted_tools[1]

        # Last tool SHOULD have cache_control
        assert "cache_control" in converted_tools[2]
        assert converted_tools[2]["cache_control"] == {"type": "ephemeral"}

    def test_tools_with_1h_cache(self):
        """Test tools formatted with 1h cache control on last tool."""
        from google.genai.types import FunctionDeclaration, Tool

        tools = [FunctionDeclaration(name="tool1", description="First tool")]

        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig(tools=[Tool(function_declarations=tools)])
        request = LlmRequest(contents=[content], config=config)

        _, converted_tools, _, _ = _get_completion_inputs(
            request,
            cache_strategy="1h"
        )

        assert converted_tools[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_tools_with_none_cache(self):
        """Test tools without cache control when caching disabled."""
        from google.genai.types import FunctionDeclaration, Tool

        tools = [FunctionDeclaration(name="tool1", description="First tool")]

        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig(tools=[Tool(function_declarations=tools)])
        request = LlmRequest(contents=[content], config=config)

        _, converted_tools, _, _ = _get_completion_inputs(
            request,
            cache_strategy="none"
        )

        # No cache_control should be present
        assert "cache_control" not in converted_tools[0]

    def test_no_tools_no_error(self):
        """Test that no tools doesn't cause errors."""
        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig()
        request = LlmRequest(contents=[content], config=config)

        _, converted_tools, _, _ = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        assert converted_tools is None


class TestGetCompletionInputsIntegration:
    """Test complete _get_completion_inputs flow with caching."""

    def test_both_system_and_tools_cached(self):
        """Test that both system instruction and tools get cache control."""
        from google.genai.types import FunctionDeclaration, Tool

        tools = [
            FunctionDeclaration(name="tool1", description="First tool"),
            FunctionDeclaration(name="tool2", description="Second tool"),
        ]

        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig(
            system_instruction="You are a helpful assistant.",
            tools=[Tool(function_declarations=tools)]
        )
        request = LlmRequest(contents=[content], config=config)

        messages, converted_tools, _, _ = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        # System instruction should have cache control
        system_msg = messages[0]
        assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}

        # Last tool should have cache control
        assert converted_tools[1]["cache_control"] == {"type": "ephemeral"}

        # First tool should NOT have cache control
        assert "cache_control" not in converted_tools[0]

    def test_user_message_content_preserved(self):
        """Test that user message content is preserved correctly."""
        from google.genai.types import FunctionDeclaration, Tool

        tools = [FunctionDeclaration(name="tool1", description="First tool")]

        content = Content(role="user", parts=[Part(text="What is the weather?")])
        config = GenerateContentConfig(
            system_instruction="You are a weather assistant.",
            tools=[Tool(function_declarations=tools)]
        )
        request = LlmRequest(contents=[content], config=config)

        messages, _, _, _ = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        # Should have system message and user message
        assert len(messages) == 2
        assert messages[0]["role"] == "developer"  # system
        assert messages[1]["role"] == "user"

        # User message content should be preserved
        user_msg = messages[1]
        assert "What is the weather?" in str(user_msg["content"])

    def test_generation_params_preserved(self):
        """Test that generation parameters are preserved with caching."""
        content = Content(role="user", parts=[Part(text="Hello")])
        config = GenerateContentConfig(
            system_instruction="You are a helpful assistant.",
            temperature=0.7,
            max_output_tokens=1000,
            top_p=0.9,
        )
        request = LlmRequest(contents=[content], config=config)

        _, _, _, generation_params = _get_completion_inputs(
            request,
            cache_strategy="5m"
        )

        # Generation params should be preserved
        assert generation_params is not None
        assert generation_params["temperature"] == 0.7
        assert generation_params["max_completion_tokens"] == 1000
        assert generation_params["top_p"] == 0.9
