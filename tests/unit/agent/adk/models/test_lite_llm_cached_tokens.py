#!/usr/bin/env python3
"""
Unit tests for cached token extraction in lite_llm.py

These tests verify that cached tokens are correctly extracted from LiteLLM
responses and passed through to GenerateContentResponseUsageMetadata.
"""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

# Import the functions and classes we're testing
from solace_agent_mesh.agent.adk.models.lite_llm import (
    UsageMetadataChunk,
    _model_response_to_generate_content_response,
    _model_response_to_chunk,
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])