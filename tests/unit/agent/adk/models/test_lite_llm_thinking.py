"""Unit tests for thinking/reasoning content handling in LiteLlm."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from solace_agent_mesh.agent.adk.models.lite_llm import (
    LiteLlm,
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


def _make_lite_llm(model="anthropic/claude-sonnet-4-20250514", **kwargs):
    """Create a LiteLlm instance with minimal config, suppressing litellm logging."""
    with patch("solace_agent_mesh.agent.adk.models.lite_llm.logging"):
        return LiteLlm(model=model, **kwargs)


class TestLiteLlmInit:
    """Tests for __init__ non-pydantic key extraction (issue #8)."""

    def test_thinking_key_extracted_without_validation_error(self):
        """'thinking' in kwargs should not cause a Pydantic validation error."""
        llm = _make_lite_llm(thinking={"budget_tokens": 5000})
        assert llm._thinking_config == {"budget_tokens": 5000}

    def test_cache_strategy_key_extracted_without_validation_error(self):
        """'cache_strategy' in kwargs should not cause a Pydantic validation error."""
        llm = _make_lite_llm(cache_strategy="none")
        assert llm._cache_strategy == "none"

    def test_oauth_keys_extracted_without_validation_error(self):
        """OAuth keys in kwargs should not cause a Pydantic validation error."""
        llm = _make_lite_llm(
            oauth_client_id="id",
            oauth_client_secret="secret",
            oauth_token_url="https://example.com/token",
        )
        # Should not raise; oauth manager should be initialized
        assert llm._oauth_token_manager is not None


class TestConfigureModelThinking:
    """Tests for configure_model thinking config extraction (issue #7)."""

    def test_stores_thinking_config(self):
        """thinking dict is stored on _thinking_config."""
        llm = _make_lite_llm()
        llm.configure_model({"model": "anthropic/claude-sonnet-4-20250514", "thinking": {"budget_tokens": 8000}})
        assert llm._thinking_config == {"budget_tokens": 8000}

    def test_clears_thinking_config_when_absent(self):
        """_thinking_config is None when thinking is not in config."""
        llm = _make_lite_llm(thinking={"budget_tokens": 5000})
        assert llm._thinking_config is not None
        llm.configure_model({"model": "anthropic/claude-sonnet-4-20250514"})
        assert llm._thinking_config is None

    def test_clears_thinking_config_when_not_dict(self):
        """_thinking_config is None when thinking is not a dict."""
        llm = _make_lite_llm()
        llm.configure_model({"model": "anthropic/claude-sonnet-4-20250514", "thinking": "invalid"})
        assert llm._thinking_config is None


async def _async_iter(items):
    """Helper to create an async iterator from a list."""
    for item in items:
        yield item


class TestThinkingConfigInjection:
    """Tests for thinking config injection into completion_args (issue #5)."""

    def _make_llm_with_thinking(self, model="anthropic/claude-sonnet-4-20250514", budget=10000):
        llm = _make_lite_llm(model=model, thinking={"budget_tokens": budget})
        return llm

    @pytest.mark.asyncio
    async def test_native_anthropic_gets_top_level_thinking(self):
        """Native Anthropic model gets thinking as top-level completion arg."""
        llm = self._make_llm_with_thinking(model="anthropic/claude-sonnet-4-20250514")

        captured_args = {}
        async def fake_acompletion(**kwargs):
            captured_args.update(kwargs)
            return _async_iter([{
                "choices": [{"delta": {"content": "response"}, "finish_reason": "stop"}]
            }])

        llm.llm_client.acompletion = fake_acompletion

        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="hello")])],
        )
        async for _ in llm.generate_content_async(llm_request, stream=True):
            pass

        assert "thinking" in captured_args
        assert captured_args["thinking"]["budget_tokens"] == 10000
        assert captured_args["temperature"] == 1

    @pytest.mark.asyncio
    async def test_proxy_model_gets_extra_body_thinking(self):
        """Non-Anthropic model gets thinking in extra_body, no temperature override."""
        llm = self._make_llm_with_thinking(model="openai/gpt-4")

        captured_args = {}
        async def fake_acompletion(**kwargs):
            captured_args.update(kwargs)
            return _async_iter([{
                "choices": [{"delta": {"content": "response"}, "finish_reason": "stop"}]
            }])

        llm.llm_client.acompletion = fake_acompletion

        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="hello")])],
        )
        async for _ in llm.generate_content_async(llm_request, stream=True):
            pass

        assert "thinking" not in captured_args
        assert "extra_body" in captured_args
        assert captured_args["extra_body"]["thinking"]["budget_tokens"] == 10000
        # Temperature should NOT be forced for non-Anthropic models
        assert captured_args.get("temperature") != 1

    @pytest.mark.asyncio
    async def test_zero_budget_skips_thinking_injection(self):
        """budget_tokens=0 means thinking is not injected."""
        llm = self._make_llm_with_thinking(budget=0)

        captured_args = {}
        async def fake_acompletion(**kwargs):
            captured_args.update(kwargs)
            return _async_iter([{
                "choices": [{"delta": {"content": "response"}, "finish_reason": "stop"}]
            }])

        llm.llm_client.acompletion = fake_acompletion

        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="hello")])],
        )
        async for _ in llm.generate_content_async(llm_request, stream=True):
            pass

        assert "thinking" not in captured_args
        assert "extra_body" not in captured_args


class TestStreamingThinkingChunkYield:
    """Tests for streaming ThinkingChunk -> LlmResponse yield path (issue #6)."""

    @pytest.mark.asyncio
    async def test_thinking_chunk_yields_llm_response_with_metadata(self):
        """ThinkingChunk from stream is yielded as LlmResponse with is_thinking_content metadata."""
        llm = _make_lite_llm(model="anthropic/claude-sonnet-4-20250514", thinking={"budget_tokens": 5000})

        async def fake_acompletion(**kwargs):
            return _async_iter([
                {"choices": [{"delta": {"reasoning_content": "Let me think..."}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "The answer."}, "finish_reason": "stop"}]},
            ])

        llm.llm_client.acompletion = fake_acompletion

        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="test")])],
        )

        responses = []
        async for resp in llm.generate_content_async(llm_request, stream=True):
            responses.append(resp)

        thinking_responses = [r for r in responses if r.custom_metadata and r.custom_metadata.get("is_thinking_content")]
        assert len(thinking_responses) == 1
        assert thinking_responses[0].partial is True
        assert thinking_responses[0].content.parts[0].text == "Let me think..."

    @pytest.mark.asyncio
    async def test_thinking_and_text_chunks_both_yielded(self):
        """Both thinking and text chunks are yielded in order."""
        llm = _make_lite_llm(model="anthropic/claude-sonnet-4-20250514", thinking={"budget_tokens": 5000})

        async def fake_acompletion(**kwargs):
            return _async_iter([
                {"choices": [{"delta": {"reasoning_content": "thinking..."}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "answer"}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
            ])

        llm.llm_client.acompletion = fake_acompletion

        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="test")])],
        )

        responses = []
        async for resp in llm.generate_content_async(llm_request, stream=True):
            responses.append(resp)

        thinking = [r for r in responses if r.custom_metadata and r.custom_metadata.get("is_thinking_content")]
        text = [r for r in responses if not (r.custom_metadata and r.custom_metadata.get("is_thinking_content"))]
        assert len(thinking) >= 1
        assert len(text) >= 1
