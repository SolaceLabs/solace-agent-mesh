"""
Unit tests for StarterSuggestionsService.
"""

import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.gateway.http_sse.services.starter_suggestions_service import (
    CACHE_TTL_SECONDS,
    DEFAULT_STARTER_SUGGESTIONS,
    StarterSuggestionsService,
)


VALID_LLM_JSON = json.dumps(
    {
        "categories": [
            {
                "icon": "BarChart3",
                "label": "Analytics",
                "description": "Explore data trends",
                "options": [
                    {"label": "Run a report", "prompt": "Help me run a report."}
                ],
            },
            {
                "icon": "Code",
                "label": "Development",
                "description": "Write and debug code",
                "options": [
                    {"label": "Fix a bug", "prompt": "Help me debug this issue."}
                ],
            },
        ]
    }
)


def _create_service():
    """Create a StarterSuggestionsService with a mocked LLM."""
    mock_llm = MagicMock()
    service = StarterSuggestionsService(model_config={}, llm=mock_llm)
    return service


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLlmResponse:
    def test_valid_json(self):
        service = _create_service()
        result, err = service._parse_llm_response(VALID_LLM_JSON)
        assert result is not None
        assert err == ""
        assert len(result) == 2
        assert result[0]["label"] == "Analytics"

    def test_json_in_markdown_fences(self):
        service = _create_service()
        fenced = "```json\n" + VALID_LLM_JSON + "\n```"
        result, err = service._parse_llm_response(fenced)
        assert result is not None
        assert err == ""
        assert len(result) == 2

    def test_fence_with_no_newline(self):
        service = _create_service()
        result, err = service._parse_llm_response("```")
        assert result is None
        assert "no newline" in err.lower()

    def test_empty_categories(self):
        service = _create_service()
        result, err = service._parse_llm_response('{"categories": []}')
        assert result is None
        assert "empty" in err.lower() or "no" in err.lower()

    def test_missing_label(self):
        service = _create_service()
        data = json.dumps(
            {
                "categories": [
                    {
                        "icon": "Code",
                        "description": "desc",
                        "options": [
                            {"label": "Do thing", "prompt": "Do the thing."}
                        ],
                    }
                ]
            }
        )
        result, err = service._parse_llm_response(data)
        assert result is None
        assert "label" in err.lower()

    def test_invalid_icon_fallback(self):
        service = _create_service()
        data = json.dumps(
            {
                "categories": [
                    {
                        "icon": "NonExistentIcon",
                        "label": "Test",
                        "description": "desc",
                        "options": [
                            {"label": "Do thing", "prompt": "Do the thing."}
                        ],
                    }
                ]
            }
        )
        result, err = service._parse_llm_response(data)
        assert result is not None
        assert result[0]["icon"] == "Lightbulb"

    def test_options_missing_fields(self):
        service = _create_service()
        data = json.dumps(
            {
                "categories": [
                    {
                        "icon": "Code",
                        "label": "Dev",
                        "description": "desc",
                        "options": [
                            {"label": "Has label only"},
                            {"prompt": "Has prompt only"},
                            {"label": "Valid", "prompt": "Valid prompt"},
                        ],
                    }
                ]
            }
        )
        result, err = service._parse_llm_response(data)
        assert result is not None
        assert len(result[0]["options"]) == 1
        assert result[0]["options"][0]["label"] == "Valid"

    def test_all_options_invalid_skips_category(self):
        service = _create_service()
        data = json.dumps(
            {
                "categories": [
                    {
                        "icon": "Code",
                        "label": "Bad",
                        "description": "desc",
                        "options": [{"label": "", "prompt": ""}],
                    }
                ]
            }
        )
        result, err = service._parse_llm_response(data)
        assert result is None
        assert "missing" in err.lower() or "no valid" in err.lower()

    def test_malformed_json(self):
        service = _create_service()
        result, err = service._parse_llm_response("not json at all {{{")
        assert result is None
        assert "json" in err.lower()

    def test_non_dict_category_skipped(self):
        service = _create_service()
        data = json.dumps(
            {
                "categories": [
                    "not a dict",
                    {
                        "icon": "Code",
                        "label": "Valid",
                        "description": "desc",
                        "options": [
                            {"label": "Do thing", "prompt": "Do the thing."}
                        ],
                    },
                ]
            }
        )
        result, err = service._parse_llm_response(data)
        assert result is not None
        assert len(result) == 1
        assert result[0]["label"] == "Valid"


# ---------------------------------------------------------------------------
# Cache logic: _build_cache_key, _get_cached, _set_cached
# ---------------------------------------------------------------------------


class TestCacheLogic:
    def test_same_names_different_order_same_key(self):
        service = _create_service()
        key1 = service._build_cache_key(["b", "a", "c"])
        key2 = service._build_cache_key(["c", "a", "b"])
        assert key1 == key2

    def test_different_agent_sets_different_keys(self):
        service = _create_service()
        key1 = service._build_cache_key(["agent-a"])
        key2 = service._build_cache_key(["agent-b"])
        assert key1 != key2

    def test_cache_hit_returns_stored_data(self):
        service = _create_service()
        suggestions = [{"label": "test"}]
        service._set_cached("key1", suggestions)
        assert service._get_cached("key1") == suggestions

    def test_cache_miss_returns_none(self):
        service = _create_service()
        assert service._get_cached("nonexistent") is None

    def test_cache_expiry(self):
        service = _create_service()
        suggestions = [{"label": "test"}]
        # Insert with a timestamp in the past
        expired_time = time.time() - CACHE_TTL_SECONDS - 1
        service._cache["key1"] = (expired_time, suggestions)
        assert service._get_cached("key1") is None
        # Entry should be removed
        assert "key1" not in service._cache

    def test_duplicate_names_deduplicated(self):
        service = _create_service()
        key1 = service._build_cache_key(["a", "a", "b"])
        key2 = service._build_cache_key(["a", "b"])
        assert key1 == key2


# ---------------------------------------------------------------------------
# generate_suggestions branching
# ---------------------------------------------------------------------------


class TestGenerateSuggestions:
    @pytest.mark.asyncio
    async def test_empty_agents_returns_defaults(self):
        service = _create_service()
        result = await service.generate_suggestions([])
        assert result == DEFAULT_STARTER_SUGGESTIONS

    @pytest.mark.asyncio
    async def test_llm_success_caches_result(self):
        service = _create_service()
        parsed = [{"icon": "Code", "label": "Dev", "description": "d", "options": [{"label": "x", "prompt": "y"}]}]
        service._send_llm_request = AsyncMock(return_value=VALID_LLM_JSON)

        agents = [{"name": "test-agent", "description": "A test agent", "tools": []}]
        result = await service.generate_suggestions(agents)

        assert result is not None
        assert len(result) == 2
        # Second call should use cache (no additional LLM call)
        service._send_llm_request.reset_mock()
        result2 = await service.generate_suggestions(agents)
        assert result2 == result
        service._send_llm_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_defaults(self):
        service = _create_service()
        service._send_llm_request = AsyncMock(side_effect=Exception("LLM down"))

        agents = [{"name": "agent1", "description": "desc", "tools": []}]
        result = await service.generate_suggestions(agents)
        assert result == DEFAULT_STARTER_SUGGESTIONS

    @pytest.mark.asyncio
    async def test_llm_returns_none_falls_back_to_defaults(self):
        service = _create_service()
        service._send_llm_request = AsyncMock(return_value=None)

        agents = [{"name": "agent1", "description": "desc", "tools": []}]
        result = await service.generate_suggestions(agents)
        assert result == DEFAULT_STARTER_SUGGESTIONS


# ---------------------------------------------------------------------------
# _call_litellm retry/correction logic
# ---------------------------------------------------------------------------


class TestCallLitellmRetry:
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_invalid_json(self):
        """First LLM call returns invalid JSON, correction call succeeds."""
        service = _create_service()
        service._send_llm_request = AsyncMock(
            side_effect=["not valid json {{{", VALID_LLM_JSON]
        )

        result = await service._call_litellm("agent descriptions")

        assert result is not None
        assert len(result) == 2
        assert result[0]["label"] == "Analytics"
        assert service._send_llm_request.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_none(self):
        """Both initial and retry calls return invalid JSON → returns None."""
        service = _create_service()
        service._send_llm_request = AsyncMock(
            side_effect=["bad json 1", "bad json 2"]
        )

        result = await service._call_litellm("agent descriptions")

        assert result is None
        assert service._send_llm_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_returns_none_content(self):
        """First call returns invalid JSON, retry returns None → returns None."""
        service = _create_service()
        service._send_llm_request = AsyncMock(
            side_effect=["not valid json", None]
        )

        result = await service._call_litellm("agent descriptions")

        assert result is None
        assert service._send_llm_request.call_count == 2

    @pytest.mark.asyncio
    async def test_first_attempt_valid_no_retry(self):
        """First call returns valid JSON → no retry attempted."""
        service = _create_service()
        service._send_llm_request = AsyncMock(return_value=VALID_LLM_JSON)

        result = await service._call_litellm("agent descriptions")

        assert result is not None
        assert len(result) == 2
        service._send_llm_request.assert_called_once()
