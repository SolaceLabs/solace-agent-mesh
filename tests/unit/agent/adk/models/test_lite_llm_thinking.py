"""Unit tests for thinking/reasoning content handling in LiteLlm."""

import pytest

from solace_agent_mesh.agent.adk.models.lite_llm import (
    ThinkingChunk,
    TextChunk,
    _model_response_to_chunk,
    _model_response_to_generate_content_response,
)


class TestModelResponseToChunkThinking:
    """Tests for ThinkingChunk yielding from _model_response_to_chunk."""

    def test_yields_thinking_chunk_from_reasoning_content(self):
        """reasoning_content in message yields a ThinkingChunk."""
        response = {
            "choices": [
                {
                    "delta": {
                        "reasoning_content": "Let me think step by step...",
                        "content": None,
                    },
                    "finish_reason": None,
                }
            ]
        }

        chunks = list(_model_response_to_chunk(response))
        thinking_chunks = [c for c, _ in chunks if isinstance(c, ThinkingChunk)]
        assert len(thinking_chunks) == 1
        assert thinking_chunks[0].text == "Let me think step by step..."

    def test_yields_thinking_chunk_from_provider_specific_fields(self):
        """reasoning_content in provider_specific_fields yields a ThinkingChunk."""
        response = {
            "choices": [
                {
                    "delta": {
                        "provider_specific_fields": {
                            "reasoning_content": "Deep reasoning here"
                        },
                        "content": None,
                    },
                    "finish_reason": None,
                }
            ]
        }

        chunks = list(_model_response_to_chunk(response))
        thinking_chunks = [c for c, _ in chunks if isinstance(c, ThinkingChunk)]
        assert len(thinking_chunks) == 1
        assert thinking_chunks[0].text == "Deep reasoning here"

    def test_yields_both_thinking_and_text_chunks(self):
        """Message with both reasoning and content yields both chunk types."""
        response = {
            "choices": [
                {
                    "message": {
                        "reasoning_content": "thinking...",
                        "content": "the answer is 42",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        chunks = list(_model_response_to_chunk(response))
        types_found = [type(c) for c, _ in chunks if c is not None]
        assert ThinkingChunk in types_found
        assert TextChunk in types_found

    def test_no_thinking_chunk_when_no_reasoning(self):
        """No ThinkingChunk when reasoning_content is absent."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": "plain response",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        chunks = list(_model_response_to_chunk(response))
        thinking_chunks = [c for c, _ in chunks if isinstance(c, ThinkingChunk)]
        assert len(thinking_chunks) == 0


class TestModelResponseToGenerateContentResponseThinking:
    """Tests for reasoning extraction in _model_response_to_generate_content_response."""

    def test_extracts_reasoning_content_to_custom_metadata(self):
        """reasoning_content is placed into custom_metadata['thinking_content']."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": "final answer",
                        "reasoning_content": "step by step reasoning",
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        llm_response = _model_response_to_generate_content_response(response)
        assert llm_response.custom_metadata is not None
        assert llm_response.custom_metadata["thinking_content"] == "step by step reasoning"

    def test_extracts_reasoning_from_provider_specific_fields(self):
        """reasoning_content from provider_specific_fields goes to custom_metadata."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": "answer",
                        "provider_specific_fields": {
                            "reasoning_content": "provider reasoning"
                        },
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        llm_response = _model_response_to_generate_content_response(response)
        assert llm_response.custom_metadata is not None
        assert llm_response.custom_metadata["thinking_content"] == "provider reasoning"

    def test_no_custom_metadata_when_no_reasoning(self):
        """No thinking_content in custom_metadata when reasoning is absent."""
        response = {
            "choices": [
                {
                    "message": {
                        "content": "plain response",
                        "role": "assistant",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

        llm_response = _model_response_to_generate_content_response(response)
        if llm_response.custom_metadata:
            assert "thinking_content" not in llm_response.custom_metadata
