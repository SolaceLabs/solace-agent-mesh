"""Tests for LiteLlm._sanitize_for_completion and the override path."""

import copy
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


class TestSanitizeForCompletion:
    def test_removes_non_completion_keys(self):
        config = {
            "model": "openai/gpt-4o",
            "api_key": "sk-test",
            "api_base": "https://api.example.com",
            "num_retries": 3,
            "cache_strategy": "5m",
            "thinking": {"budget_tokens": 10000},
            "type": "custom",
        }
        result = LiteLlm._sanitize_for_completion(config)

        assert "cache_strategy" not in result
        assert "thinking" not in result
        assert "type" not in result

        assert result["model"] == "openai/gpt-4o"
        assert result["api_key"] == "sk-test"
        assert result["api_base"] == "https://api.example.com"
        assert result["num_retries"] == 3

    def test_removes_all_oauth_prefixed_keys(self):
        config = {
            "model": "openai/gpt-4o",
            "oauth_client_id": "id",
            "oauth_client_secret": "secret",
            "oauth_token_url": "https://auth.example.com/token",
            "oauth_scope": "read",
            "oauth_audience": "https://api.example.com",
            "oauth_custom_field": "value",
        }
        original_oauth_keys = [k for k in config if k.startswith("oauth_")]
        result = LiteLlm._sanitize_for_completion(config)

        for key in original_oauth_keys:
            assert key not in result

        assert result["model"] == "openai/gpt-4o"

    def test_preserves_valid_keys_only(self):
        config = {
            "model": "anthropic/claude-3-5-sonnet",
            "api_key": "sk-ant-test",
            "api_base": "https://api.anthropic.com",
            "num_retries": 5,
            "timeout": 60,
            "extra_headers": {"X-Custom": "value"},
        }
        original = copy.deepcopy(config)
        LiteLlm._sanitize_for_completion(config)

        assert config == original

    def test_returns_mutated_dict(self):
        config = {"model": "gpt-4o", "cache_strategy": "1h"}
        result = LiteLlm._sanitize_for_completion(config)
        assert result is config

    def test_handles_empty_config(self):
        config = {}
        result = LiteLlm._sanitize_for_completion(config)
        assert result == {}


class TestOverrideSanitization:
    @pytest.mark.asyncio
    async def test_override_keys_stripped_before_acompletion(self):
        """Per-request override config must not leak non-completion keys to acompletion."""
        mock_client = MagicMock()
        mock_response = {
            "choices": [
                {
                    "message": {"content": "hello", "tool_calls": None},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        mock_client.acompletion = AsyncMock(return_value=mock_response)

        with patch(
            "solace_agent_mesh.agent.adk.models.lite_llm.get_model_override"
        ) as mock_get_override:
            mock_get_override.return_value = {
                "model": "openai/gpt-4o-override",
                "api_key": "sk-override",
                "cache_strategy": "1h",
                "thinking": {"budget_tokens": 5000},
                "type": "custom",
                "oauth_client_id": "id",
                "oauth_audience": "https://api.example.com",
            }

            llm = LiteLlm(model="openai/gpt-4o")
            llm.llm_client = mock_client
            llm._thinking_config = None

            request = LlmRequest(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="hi")],
                    )
                ],
                config=types.GenerateContentConfig(),
            )

            responses = []
            async for resp in llm.generate_content_async(request, stream=False):
                responses.append(resp)

            assert mock_client.acompletion.call_count == 1
            call_kwargs = mock_client.acompletion.call_args
            completion_args = {
                **dict(zip(["model", "messages", "tools"], call_kwargs.args)),
                **call_kwargs.kwargs,
            }

            assert "cache_strategy" not in completion_args
            assert "thinking" not in completion_args
            assert "type" not in completion_args
            assert "oauth_client_id" not in completion_args
            assert "oauth_audience" not in completion_args

            assert completion_args["model"] == "openai/gpt-4o-override"
            assert completion_args["api_key"] == "sk-override"
