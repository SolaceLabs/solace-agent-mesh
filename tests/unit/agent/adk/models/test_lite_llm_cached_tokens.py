#!/usr/bin/env python3
"""
Unit tests for token usage tracking in lite_llm.py

These tests verify that token usage (including cached tokens) is correctly
extracted from LiteLLM responses and passed through to GenerateContentResponseUsageMetadata.
Also tests the track_token_usage feature flag functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pydantic import BaseModel

# Import the functions and classes we're testing
from solace_agent_mesh.agent.adk.models.lite_llm import (
    UsageMetadataChunk,
    _model_response_to_generate_content_response,
    _model_response_to_chunk,
    LiteLlm,
)


class TestUsageMetadataChunk:
    """Tests for UsageMetadataChunk class."""

    def test_cached_tokens_field_exists(self):
        """Test that cached_tokens field exists with default value 0."""
        chunk = UsageMetadataChunk(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert hasattr(chunk, "cached_tokens")
        assert chunk.cached_tokens == 0

    def test_cached_tokens_can_be_set(self):
        """Test that cached_tokens can be set to a non-zero value."""
        chunk = UsageMetadataChunk(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cached_tokens=75,
        )
        assert chunk.cached_tokens == 75


class TestModelResponseToChunk:
    """Tests for _model_response_to_chunk function."""

    def test_extracts_cached_tokens_from_dict(self):
        """Test extraction of cached tokens when prompt_tokens_details is a dict."""
        response = {
            "choices": [
                {
                    "message": {"content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {
                    "cached_tokens": 75,
                    "audio_tokens": 0,
                },
            },
        }

        chunks = list(_model_response_to_chunk(response))
        
        # Find the UsageMetadataChunk
        usage_chunk = None
        for chunk, _ in chunks:
            if isinstance(chunk, UsageMetadataChunk):
                usage_chunk = chunk
                break

        assert usage_chunk is not None
        assert usage_chunk.cached_tokens == 75
        assert usage_chunk.prompt_tokens == 100
        assert usage_chunk.completion_tokens == 50

    def test_extracts_cached_tokens_from_object(self):
        """Test extraction of cached tokens when prompt_tokens_details is an object."""
        
        # Create a mock object with cached_tokens attribute
        class MockPromptTokensDetails:
            cached_tokens = 80
            audio_tokens = 0

        response = {
            "choices": [
                {
                    "message": {"content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": MockPromptTokensDetails(),
            },
        }

        chunks = list(_model_response_to_chunk(response))
        
        # Find the UsageMetadataChunk
        usage_chunk = None
        for chunk, _ in chunks:
            if isinstance(chunk, UsageMetadataChunk):
                usage_chunk = chunk
                break

        assert usage_chunk is not None
        assert usage_chunk.cached_tokens == 80

    def test_handles_missing_prompt_tokens_details(self):
        """Test that missing prompt_tokens_details results in cached_tokens=0."""
        response = {
            "choices": [
                {
                    "message": {"content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }

        chunks = list(_model_response_to_chunk(response))
        
        # Find the UsageMetadataChunk
        usage_chunk = None
        for chunk, _ in chunks:
            if isinstance(chunk, UsageMetadataChunk):
                usage_chunk = chunk
                break

        assert usage_chunk is not None
        assert usage_chunk.cached_tokens == 0

    def test_handles_none_cached_tokens(self):
        """Test that None cached_tokens is treated as 0."""
        response = {
            "choices": [
                {
                    "message": {"content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {
                    "cached_tokens": None,
                },
            },
        }

        chunks = list(_model_response_to_chunk(response))
        
        # Find the UsageMetadataChunk
        usage_chunk = None
        for chunk, _ in chunks:
            if isinstance(chunk, UsageMetadataChunk):
                usage_chunk = chunk
                break

        assert usage_chunk is not None
        assert usage_chunk.cached_tokens == 0


class TestModelResponseToGenerateContentResponse:
    """Tests for _model_response_to_generate_content_response function."""

    def test_extracts_cached_tokens_from_dict(self):
        """Test extraction of cached tokens in non-streaming response."""
        response = {
            "choices": [
                {
                    "message": {"content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {
                    "cached_tokens": 75,
                },
            },
        }

        llm_response = _model_response_to_generate_content_response(response)

        assert llm_response.usage_metadata is not None
        assert llm_response.usage_metadata.prompt_token_count == 100
        assert llm_response.usage_metadata.candidates_token_count == 50
        assert llm_response.usage_metadata.cached_content_token_count == 75

    def test_cached_content_token_count_is_none_when_zero(self):
        """Test that cached_content_token_count is None when cached_tokens is 0."""
        response = {
            "choices": [
                {
                    "message": {"content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                },
            },
        }

        llm_response = _model_response_to_generate_content_response(response)

        assert llm_response.usage_metadata is not None
        assert llm_response.usage_metadata.cached_content_token_count is None

    def test_handles_litellm_wrapper_object(self):
        """Test extraction when prompt_tokens_details is a LiteLLM wrapper object."""
        
        # Simulate LiteLLM's PromptTokensDetailsWrapper
        class PromptTokensDetailsWrapper:
            def __init__(self):
                self.cached_tokens = 60
                self.audio_tokens = 0
                self.text_tokens = None
                self.image_tokens = None

        response = {
            "choices": [
                {
                    "message": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": PromptTokensDetailsWrapper(),
            },
        }

        llm_response = _model_response_to_generate_content_response(response)

        assert llm_response.usage_metadata is not None
        assert llm_response.usage_metadata.cached_content_token_count == 60


class TestTrackTokenUsageFeatureFlag:
    """Tests for the track_token_usage feature flag.
    
    The global setting is injected by setup.py when creating the model.
    """

    def test_default_track_token_usage_is_false(self):
        """Test that track_token_usage defaults to False when not specified."""
        llm = LiteLlm(model="test-model")
        assert llm._track_token_usage is False

    def test_track_token_usage_can_be_enabled(self):
        """Test that track_token_usage can be set to True."""
        llm = LiteLlm(model="test-model", track_token_usage=True)
        assert llm._track_token_usage is True

    def test_track_token_usage_can_be_explicitly_disabled(self):
        """Test that track_token_usage can be explicitly set to False."""
        llm = LiteLlm(model="test-model", track_token_usage=False)
        assert llm._track_token_usage is False

    def test_init_logs_track_token_usage_setting(self):
        """Test that track_token_usage setting is logged on initialization."""
        with patch("solace_agent_mesh.agent.adk.models.lite_llm.logger") as mock_logger:
            llm = LiteLlm(model="test-model", track_token_usage=True)
            
            # Check that info was called with the track_token_usage value
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args_list[-1]
            assert "track_token_usage" in call_args[0][0]
            assert call_args[0][2] is True  # The track_token_usage value

    @pytest.mark.asyncio
    async def test_streaming_no_usage_metadata_when_flag_disabled(self):
        """Test that streaming mode doesn't include ANY usage metadata when flag is disabled."""
        llm = LiteLlm(model="test-model", track_token_usage=False)
        
        # Create an async iterator wrapper with proper streaming response format
        async def async_iter():
            for item in [
                {
                    "choices": [{"message": {"content": "Hello"}, "delta": {"content": "Hello"}, "finish_reason": None}],
                },
                {
                    "choices": [{"message": {"content": ""}, "delta": {}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                        "prompt_tokens_details": {"cached_tokens": 75},
                    },
                },
            ]:
                yield item
        
        llm.llm_client.acompletion = AsyncMock(return_value=async_iter())
        
        # Create a minimal LlmRequest
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types
        
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text="Hello")])]
        )
        
        # Collect responses
        responses = []
        async for response in llm.generate_content_async(llm_request, stream=True):
            responses.append(response)
        
        # Check that the final response has NO usage_metadata when flag is disabled
        final_response = responses[-1]
        assert final_response.usage_metadata is None

    @pytest.mark.asyncio
    async def test_streaming_includes_all_usage_when_flag_enabled(self):
        """Test that streaming mode includes all usage metadata when flag is enabled."""
        llm = LiteLlm(model="test-model", track_token_usage=True)
        
        # Create an async iterator wrapper with proper streaming response format
        async def async_iter():
            for item in [
                {
                    "choices": [{"message": {"content": "Hello"}, "delta": {"content": "Hello"}, "finish_reason": None}],
                },
                {
                    "choices": [{"message": {"content": ""}, "delta": {}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                        "prompt_tokens_details": {"cached_tokens": 75},
                    },
                },
            ]:
                yield item
        
        llm.llm_client.acompletion = AsyncMock(return_value=async_iter())
        
        # Create a minimal LlmRequest
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types
        
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text="Hello")])]
        )
        
        # Collect responses
        responses = []
        async for response in llm.generate_content_async(llm_request, stream=True):
            responses.append(response)
        
        # Check that the final response has full usage_metadata when flag is enabled
        final_response = responses[-1]
        assert final_response.usage_metadata is not None
        assert final_response.usage_metadata.prompt_token_count == 100
        assert final_response.usage_metadata.candidates_token_count == 50
        assert final_response.usage_metadata.total_token_count == 150
        assert final_response.usage_metadata.cached_content_token_count == 75

    @pytest.mark.asyncio
    async def test_non_streaming_no_usage_metadata_when_flag_disabled(self):
        """Test that non-streaming mode doesn't include ANY usage metadata when flag is disabled."""
        llm = LiteLlm(model="test-model", track_token_usage=False)
        
        # Mock the llm_client.acompletion to return a non-streaming response
        mock_response = {
            "choices": [
                {
                    "message": {"content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {"cached_tokens": 75},
            },
        }
        
        llm.llm_client.acompletion = AsyncMock(return_value=mock_response)
        
        # Create a minimal LlmRequest
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types
        
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text="Hello")])]
        )
        
        # Collect responses
        responses = []
        async for response in llm.generate_content_async(llm_request, stream=False):
            responses.append(response)
        
        # Check that the response has NO usage_metadata when flag is disabled
        assert len(responses) == 1
        assert responses[0].usage_metadata is None

    @pytest.mark.asyncio
    async def test_non_streaming_includes_all_usage_when_flag_enabled(self):
        """Test that non-streaming mode includes all usage metadata when flag is enabled."""
        llm = LiteLlm(model="test-model", track_token_usage=True)
        
        # Mock the llm_client.acompletion to return a non-streaming response
        mock_response = {
            "choices": [
                {
                    "message": {"content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "prompt_tokens_details": {"cached_tokens": 75},
            },
        }
        
        llm.llm_client.acompletion = AsyncMock(return_value=mock_response)
        
        # Create a minimal LlmRequest
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types
        
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text="Hello")])]
        )
        
        # Collect responses
        responses = []
        async for response in llm.generate_content_async(llm_request, stream=False):
            responses.append(response)
        
        # Check that the response has full usage_metadata when flag is enabled
        assert len(responses) == 1
        assert responses[0].usage_metadata is not None
        assert responses[0].usage_metadata.prompt_token_count == 100
        assert responses[0].usage_metadata.candidates_token_count == 50
        assert responses[0].usage_metadata.total_token_count == 150
        assert responses[0].usage_metadata.cached_content_token_count == 75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])