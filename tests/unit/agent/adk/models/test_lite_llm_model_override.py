"""Tests for per-request model override via ContextVar."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from google.genai.types import Content, Part, GenerateContentConfig
from google.adk.models.llm_request import LlmRequest

from solace_agent_mesh.agent.adk.models.lite_llm import (
    LiteLlm,
    get_model_override,
    set_model_override,
)


@pytest.fixture
def mock_litellm_completion():
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Test response",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }
    return response


@pytest.fixture
def simple_llm_request():
    return LlmRequest(
        contents=[Content(role="user", parts=[Part(text="Hello")])],
        config=GenerateContentConfig(),
    )


class TestSetModelOverride:
    """Tests for the set_model_override helper and ContextVar."""

    def test_set_and_get(self):
        config = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        set_model_override(config)
        assert get_model_override() == config
        set_model_override(None)

    def test_default_is_none(self):
        set_model_override(None)
        assert get_model_override() is None

    @pytest.mark.asyncio
    async def test_isolation_across_async_tasks(self):
        """Each asyncio.Task should see its own ContextVar value."""
        results = {}

        async def worker(name, model_name):
            set_model_override({"model": model_name})
            await asyncio.sleep(0.01)
            results[name] = get_model_override()
            set_model_override(None)

        await asyncio.gather(
            worker("a", "openai/gpt-4o"),
            worker("b", "anthropic/claude-3-5-sonnet"),
        )

        assert results["a"]["model"] == "openai/gpt-4o"
        assert results["b"]["model"] == "anthropic/claude-3-5-sonnet"


class TestModelOverrideInGenerateContent:
    """Tests that generate_content_async applies the override."""

    @pytest.mark.asyncio
    async def test_override_applied_to_completion_args(
        self, mock_litellm_completion, simple_llm_request
    ):
        captured_args = {}

        async def capture_acompletion(**kwargs):
            captured_args.update(kwargs)
            return mock_litellm_completion

        with patch("solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry"):
            llm = LiteLlm(model="openai/gpt-4o-mini", api_key="default-key")
            llm.llm_client = Mock()
            llm.llm_client.acompletion = AsyncMock(side_effect=capture_acompletion)

            set_model_override({"model": "anthropic/claude-3-5-sonnet", "api_key": "override-key"})

            async for _ in llm.generate_content_async(simple_llm_request):
                pass

            assert captured_args["model"] == "anthropic/claude-3-5-sonnet"
            assert captured_args["api_key"] == "override-key"

    @pytest.mark.asyncio
    async def test_no_override_uses_default(
        self, mock_litellm_completion, simple_llm_request
    ):
        captured_args = {}

        async def capture_acompletion(**kwargs):
            captured_args.update(kwargs)
            return mock_litellm_completion

        set_model_override(None)

        with patch("solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry"):
            llm = LiteLlm(model="openai/gpt-4o-mini", api_key="default-key")
            llm.llm_client = Mock()
            llm.llm_client.acompletion = AsyncMock(side_effect=capture_acompletion)

            async for _ in llm.generate_content_async(simple_llm_request):
                pass

            assert captured_args["model"] == "openai/gpt-4o-mini"
            assert captured_args["api_key"] == "default-key"

    @pytest.mark.asyncio
    async def test_override_persists_across_calls(
        self, mock_litellm_completion, simple_llm_request
    ):
        """Override should apply to every LLM call (multi-turn agent reasoning)."""
        captured_models = []

        async def capture_acompletion(**kwargs):
            captured_models.append(kwargs.get("model"))
            return mock_litellm_completion

        with patch("solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry"):
            llm = LiteLlm(model="openai/gpt-4o-mini", api_key="default-key")
            llm.llm_client = Mock()
            llm.llm_client.acompletion = AsyncMock(side_effect=capture_acompletion)

            set_model_override({"model": "anthropic/claude-3-5-sonnet"})

            async for _ in llm.generate_content_async(simple_llm_request):
                pass
            async for _ in llm.generate_content_async(simple_llm_request):
                pass

            assert captured_models == [
                "anthropic/claude-3-5-sonnet",
                "anthropic/claude-3-5-sonnet",
            ]
            set_model_override(None)

    @pytest.mark.asyncio
    async def test_override_inherits_default_resilience(
        self, mock_litellm_completion, simple_llm_request
    ):
        """Override should inherit num_retries and timeout from default if not specified."""
        captured_args = {}

        async def capture_acompletion(**kwargs):
            captured_args.update(kwargs)
            return mock_litellm_completion

        with patch("solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry"):
            llm = LiteLlm(model="openai/gpt-4o-mini", num_retries=5, timeout=300)
            llm.llm_client = Mock()
            llm.llm_client.acompletion = AsyncMock(side_effect=capture_acompletion)

            set_model_override({"model": "anthropic/claude-3-5-sonnet"})

            async for _ in llm.generate_content_async(simple_llm_request):
                pass

            assert captured_args["num_retries"] == 5
            assert captured_args["timeout"] == 300

    @pytest.mark.asyncio
    async def test_override_can_specify_own_resilience(
        self, mock_litellm_completion, simple_llm_request
    ):
        captured_args = {}

        async def capture_acompletion(**kwargs):
            captured_args.update(kwargs)
            return mock_litellm_completion

        with patch("solace_agent_mesh.agent.adk.models.lite_llm.MetricRegistry"):
            llm = LiteLlm(model="openai/gpt-4o-mini", num_retries=5, timeout=300)
            llm.llm_client = Mock()
            llm.llm_client.acompletion = AsyncMock(side_effect=capture_acompletion)

            set_model_override({"model": "anthropic/claude-3-5-sonnet", "num_retries": 1, "timeout": 60})

            async for _ in llm.generate_content_async(simple_llm_request):
                pass

            assert captured_args["num_retries"] == 1
            assert captured_args["timeout"] == 60
