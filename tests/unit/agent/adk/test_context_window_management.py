"""
Unit tests for context window management callback functionality.
Tests cover token counting, compression, summarization, and edge cases.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from google.genai import types as adk_types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from solace_agent_mesh.agent.adk import callbacks


def create_mock_config(system_instruction=None):
    """Create a mock config object that won't trigger Pydantic validation."""
    # Return None for most tests to avoid Pydantic validation issues
    # Only create a minimal mock when system_instruction is needed
    if system_instruction is None:
        return None
    
    config = Mock()
    config.system_instruction = system_instruction
    config.model_dump = Mock(return_value={})
    # Set spec to avoid creating too many mock attributes
    config._spec_class = None
    return config


@pytest.fixture
def mock_host_component():
    """Create a mock host component with default configuration."""
    component = Mock()
    component.model_config = "gpt-4"
    component.log_identifier = "[Test]"
    
    # Default config values
    config_values = {
        "enable_context_window_management": True,
        "context_window_threshold_percent": 80,
        "context_preserve_recent_messages": 3,
    }
    component.get_config = Mock(side_effect=lambda key, default=None: config_values.get(key, default))
    
    return component


@pytest.fixture
def mock_callback_context():
    """Create a mock callback context."""
    context = Mock(spec=CallbackContext)
    context.state = {}
    return context


@pytest.fixture
def sample_llm_request():
    """Create a sample LLM request with conversation history."""
    contents = [
        adk_types.Content(
            role="user",
            parts=[adk_types.Part(text="Hello, how are you?")]
        ),
        adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="I'm doing well, thank you!")]
        ),
        adk_types.Content(
            role="user",
            parts=[adk_types.Part(text="Can you help me with something?")]
        ),
        adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="Of course! What do you need help with?")]
        ),
    ]
    
    # Use None for config to avoid Pydantic validation issues with Mock
    return LlmRequest(contents=contents, config=None)


class TestTokenCounting:
    """Tests for _count_request_tokens function."""
    
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    def test_count_tokens_basic(self, mock_litellm, sample_llm_request):
        """Test basic token counting."""
        mock_litellm.token_counter.return_value = 100
        
        count = callbacks._count_request_tokens(sample_llm_request, "gpt-4")
        
        assert count == 100
        mock_litellm.token_counter.assert_called_once()
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', False)
    def test_count_tokens_litellm_unavailable(self, sample_llm_request):
        """Test token counting when litellm is not available."""
        count = callbacks._count_request_tokens(sample_llm_request, "gpt-4")
        assert count == 0
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    def test_count_tokens_with_system_instruction(self, mock_litellm):
        """Test token counting includes system instruction."""
        mock_litellm.token_counter.return_value = 150
        
        # Create a real ADK Content object for system instruction
        system_instruction = adk_types.Content(
            role="system",
            parts=[adk_types.Part(text="You are a helpful assistant with special instructions.")]
        )
        
        # Create a minimal config-like object with just system_instruction
        config = type('Config', (), {'system_instruction': system_instruction})()
        
        request = LlmRequest(
            contents=[
                adk_types.Content(role="user", parts=[adk_types.Part(text="Hello")])
            ],
            config=config
        )
        
        count = callbacks._count_request_tokens(request, "gpt-4")
        
        assert count == 150
        # Verify system instruction was included in messages
        call_args = mock_litellm.token_counter.call_args
        messages = call_args[1]['messages']
        assert any(msg['role'] == 'system' for msg in messages)
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    def test_count_tokens_with_function_calls(self, mock_litellm):
        """Test token counting includes function calls."""
        mock_litellm.token_counter.return_value = 200
        
        function_call = adk_types.FunctionCall(
            name="search_web",
            args={"query": "test"},
            id="call-123"
        )
        
        request = LlmRequest(
            contents=[
                adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(function_call=function_call)]
                )
            ],
            config=create_mock_config()
        )
        
        count = callbacks._count_request_tokens(request, "gpt-4")
        assert count == 200
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    def test_count_tokens_error_handling(self, mock_litellm, sample_llm_request):
        """Test error handling in token counting."""
        mock_litellm.token_counter.side_effect = Exception("API Error")
        
        count = callbacks._count_request_tokens(sample_llm_request, "gpt-4")
        assert count == 0


class TestMessageSummarization:
    """Tests for _summarize_messages function."""
    
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm')
    async def test_summarize_messages_success(self, mock_model_class):
        """Test successful message summarization."""
        # Mock the model and its response
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        mock_response = Mock()
        mock_response.content = adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="This is a summary of the conversation.")]
        )
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        
        messages = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Hello")]),
            adk_types.Content(role="model", parts=[adk_types.Part(text="Hi there!")]),
        ]
        
        summary = await callbacks._summarize_messages(
            messages, "gpt-4", "[Test]", max_retries=3
        )
        
        assert summary == "This is a summary of the conversation."
        mock_model.generate_content_async.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm')
    async def test_summarize_messages_retry_logic(self, mock_model_class):
        """Test retry logic when summarization fails."""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        # First two attempts fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.content = None
        
        mock_response_success = Mock()
        mock_response_success.content = adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="Summary after retry")]
        )
        
        mock_model.generate_content_async = AsyncMock(
            side_effect=[mock_response_fail, mock_response_fail, mock_response_success]
        )
        
        messages = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Test")]),
        ]
        
        summary = await callbacks._summarize_messages(
            messages, "gpt-4", "[Test]", max_retries=3
        )
        
        assert summary == "Summary after retry"
        assert mock_model.generate_content_async.call_count == 3
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm')
    async def test_summarize_messages_all_retries_fail(self, mock_model_class):
        """Test fallback when all retry attempts fail."""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        mock_model.generate_content_async = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        messages = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Test")]),
        ]
        
        summary = await callbacks._summarize_messages(
            messages, "gpt-4", "[Test]", max_retries=3
        )
        
        assert summary == "[Previous conversation context]"
        assert mock_model.generate_content_async.call_count == 3
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm')
    async def test_summarize_messages_with_function_calls(self, mock_model_class):
        """Test summarization includes function call information."""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        mock_response = Mock()
        mock_response.content = adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="Summary with tool calls")]
        )
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        
        function_call = adk_types.FunctionCall(
            name="search_web",
            args={"query": "test"},
            id="call-123"
        )
        
        messages = [
            adk_types.Content(
                role="model",
                parts=[adk_types.Part(function_call=function_call)]
            ),
        ]
        
        summary = await callbacks._summarize_messages(
            messages, "gpt-4", "[Test]", max_retries=1
        )
        
        assert summary == "Summary with tool calls"


class TestContextCompression:
    """Tests for _compress_context_window function."""
    
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks._summarize_messages')
    async def test_compress_context_basic(self, mock_summarize):
        """Test basic context compression."""
        mock_summarize.return_value = "Summary of old messages"
        
        # Create request with 10 messages (5 pairs)
        contents = []
        for i in range(10):
            role = "user" if i % 2 == 0 else "model"
            contents.append(
                adk_types.Content(
                    role=role,
                    parts=[adk_types.Part(text=f"Message {i}")]
                )
            )
        
        request = LlmRequest(contents=contents, config=create_mock_config())
        
        await callbacks._compress_context_window(
            request,
            max_tokens=100000,
            target_tokens=60000,
            model_name="gpt-4",
            preserve_recent=2,  # Keep last 2 pairs = 4 messages
            log_identifier="[Test]"
        )
        
        # Should have 1 summary + 4 recent messages = 5 total
        assert len(request.contents) == 5
        assert "[Context Summary:" in request.contents[0].parts[0].text
        assert "Message 6" in request.contents[1].parts[0].text  # First preserved message
        
    @pytest.mark.asyncio
    async def test_compress_context_insufficient_messages(self):
        """Test compression skips when not enough messages."""
        # Only 4 messages (2 pairs), but preserve_recent=3 (needs 6)
        contents = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Msg 1")]),
            adk_types.Content(role="model", parts=[adk_types.Part(text="Msg 2")]),
            adk_types.Content(role="user", parts=[adk_types.Part(text="Msg 3")]),
            adk_types.Content(role="model", parts=[adk_types.Part(text="Msg 4")]),
        ]
        
        request = LlmRequest(contents=contents, config=create_mock_config())
        original_count = len(request.contents)
        
        await callbacks._compress_context_window(
            request,
            max_tokens=100000,
            target_tokens=60000,
            model_name="gpt-4",
            preserve_recent=3,
            log_identifier="[Test]"
        )
        
        # Should not compress
        assert len(request.contents) == original_count
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks._summarize_messages')
    async def test_compress_context_empty_contents(self, mock_summarize):
        """Test compression handles empty contents."""
        request = LlmRequest(contents=[], config=create_mock_config())
        
        await callbacks._compress_context_window(
            request,
            max_tokens=100000,
            target_tokens=60000,
            model_name="gpt-4",
            preserve_recent=3,
            log_identifier="[Test]"
        )
        
        assert len(request.contents) == 0
        mock_summarize.assert_not_called()


class TestManageContextWindowCallback:
    """Tests for manage_context_window_callback function."""
    
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_disabled(
        self, mock_count, mock_litellm, mock_host_component, 
        mock_callback_context, sample_llm_request
    ):
        """Test callback does nothing when disabled."""
        mock_host_component.get_config = Mock(
            side_effect=lambda key, default=None: False if key == "enable_context_window_management" else default
        )
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        mock_count.assert_not_called()
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', False)
    def test_callback_litellm_unavailable(
        self, mock_host_component, mock_callback_context, sample_llm_request
    ):
        """Test callback handles litellm unavailability."""
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_within_threshold(
        self, mock_count, mock_litellm, mock_host_component,
        mock_callback_context, sample_llm_request
    ):
        """Test callback does nothing when within threshold."""
        mock_litellm.get_max_tokens.return_value = 128000
        mock_count.return_value = 50000  # 39% of max, below 80% threshold
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    @patch('solace_agent_mesh.agent.adk.callbacks._compress_context_window')
    @patch('asyncio.get_event_loop')
    def test_callback_exceeds_threshold(
        self, mock_get_loop, mock_compress, mock_count, mock_litellm,
        mock_host_component, mock_callback_context, sample_llm_request
    ):
        """Test callback triggers compression when threshold exceeded."""
        mock_litellm.get_max_tokens.return_value = 128000
        mock_count.side_effect = [110000, 60000]  # Before and after compression
        
        # Mock event loop
        mock_loop = Mock()
        mock_loop.is_running.return_value = True
        mock_loop.run_until_complete = Mock()
        mock_get_loop.return_value = mock_loop
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        mock_loop.run_until_complete.assert_called_once()
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    def test_callback_model_config_dict(
        self, mock_litellm, mock_callback_context, sample_llm_request
    ):
        """Test callback handles model config as dictionary."""
        component = Mock()
        component.model_config = {"model": "gpt-4-turbo", "temperature": 0.7}
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value=True)
        
        mock_litellm.get_max_tokens.return_value = 128000
        
        with patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens', return_value=50000):
            result = callbacks.manage_context_window_callback(
                mock_callback_context,
                sample_llm_request,
                component
            )
        
        assert result is None
        mock_litellm.get_max_tokens.assert_called_with("gpt-4-turbo")
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_max_tokens_unavailable(
        self, mock_count, mock_litellm, mock_host_component,
        mock_callback_context, sample_llm_request
    ):
        """Test callback handles when max tokens cannot be determined."""
        mock_litellm.get_max_tokens.return_value = None
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        mock_count.assert_not_called()
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_token_counting_returns_zero(
        self, mock_count, mock_litellm, mock_host_component,
        mock_callback_context, sample_llm_request
    ):
        """Test callback handles when token counting returns 0."""
        mock_litellm.get_max_tokens.return_value = 128000
        mock_count.return_value = 0
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_custom_threshold(
        self, mock_count, mock_litellm, mock_callback_context, sample_llm_request
    ):
        """Test callback respects custom threshold percentage."""
        component = Mock()
        component.model_config = "gpt-4"
        component.log_identifier = "[Test]"
        
        config_values = {
            "enable_context_window_management": True,
            "context_window_threshold_percent": 90,  # Custom 90% threshold
            "context_preserve_recent_messages": 3,
        }
        component.get_config = Mock(side_effect=lambda key, default=None: config_values.get(key, default))
        
        mock_litellm.get_max_tokens.return_value = 100000
        mock_count.return_value = 85000  # 85% - would trigger at 80% but not at 90%
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            component
        )
        
        assert result is None  # Should not compress
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_error_handling(
        self, mock_count, mock_litellm, mock_host_component,
        mock_callback_context, sample_llm_request
    ):
        """Test callback handles errors gracefully."""
        mock_litellm.get_max_tokens.side_effect = Exception("Unexpected error")
        
        # Should not raise, just return None
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            sample_llm_request,
            mock_host_component
        )
        
        assert result is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks._summarize_messages')
    async def test_compression_with_single_message(self, mock_summarize):
        """Test compression with minimal message count."""
        mock_summarize.return_value = "Summary"
        
        contents = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Only message")]),
        ]
        
        request = LlmRequest(contents=contents, config=create_mock_config())
        
        await callbacks._compress_context_window(
            request,
            max_tokens=100000,
            target_tokens=60000,
            model_name="gpt-4",
            preserve_recent=1,
            log_identifier="[Test]"
        )
        
        # Should not compress (not enough messages)
        assert len(request.contents) == 1
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks._summarize_messages')
    async def test_compression_preserves_exact_count(self, mock_summarize):
        """Test compression preserves exact number of recent messages."""
        mock_summarize.return_value = "Summary"
        
        # 8 messages, preserve 2 pairs (4 messages)
        contents = []
        for i in range(8):
            role = "user" if i % 2 == 0 else "model"
            contents.append(
                adk_types.Content(role=role, parts=[adk_types.Part(text=f"Msg {i}")])
            )
        
        request = LlmRequest(contents=contents, config=create_mock_config())
        
        await callbacks._compress_context_window(
            request,
            max_tokens=100000,
            target_tokens=60000,
            model_name="gpt-4",
            preserve_recent=2,
            log_identifier="[Test]"
        )
        
        # 1 summary + 4 preserved = 5 total
        assert len(request.contents) == 5
        # Check that the right messages were preserved (last 4)
        assert "Msg 4" in request.contents[1].parts[0].text
        assert "Msg 7" in request.contents[4].parts[0].text
        
    @patch('solace_agent_mesh.agent.adk.callbacks.LITELLM_AVAILABLE', True)
    @patch('solace_agent_mesh.agent.adk.callbacks.litellm')
    @patch('solace_agent_mesh.agent.adk.callbacks._count_request_tokens')
    def test_callback_with_empty_request(
        self, mock_count, mock_litellm, mock_host_component, mock_callback_context
    ):
        """Test callback handles empty request."""
        empty_request = LlmRequest(contents=[], config=create_mock_config())
        
        mock_litellm.get_max_tokens.return_value = 128000
        mock_count.return_value = 0
        
        result = callbacks.manage_context_window_callback(
            mock_callback_context,
            empty_request,
            mock_host_component
        )
        
        assert result is None
        
    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.models.lite_llm.LiteLlm')
    async def test_summarize_empty_summary_text(self, mock_model_class):
        """Test summarization handles empty summary text."""
        mock_model = Mock()
        mock_model_class.return_value = mock_model
        
        # Return empty text
        mock_response = Mock()
        mock_response.content = adk_types.Content(
            role="model",
            parts=[adk_types.Part(text="   ")]  # Whitespace only
        )
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        
        messages = [
            adk_types.Content(role="user", parts=[adk_types.Part(text="Test")]),
        ]
        
        summary = await callbacks._summarize_messages(
            messages, "gpt-4", "[Test]", max_retries=1
        )
        
        # Should use fallback
        assert summary == "[Previous conversation context]"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=solace_agent_mesh.agent.adk.callbacks", 
                 "--cov-report=term-missing", "--cov-report=html"])