"""Tests for LiteLlm.get_max_input_tokens resolution chain.

Resolution order under test:
  1. Admin-configured value (self._max_input_tokens).
  2. LiteLLM registry lookup of the full model name.
  3. LiteLLM registry lookup of the bare name after stripping the provider
     prefix (``openai/foo`` → ``foo``).
  4. None.
"""

from unittest.mock import patch

import pytest

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


def _make_instance(model: str, max_input_tokens=None) -> LiteLlm:
    """Construct a minimally-wired LiteLlm without running its init."""
    instance = LiteLlm.__new__(LiteLlm)
    instance.model = model
    instance._max_input_tokens = max_input_tokens
    return instance


def test_admin_value_wins_over_registry():
    instance = _make_instance("gpt-4o", max_input_tokens=99_999)
    with patch("litellm.get_model_info", return_value={"max_input_tokens": 128_000}):
        assert instance.get_max_input_tokens() == 99_999


def test_registry_used_when_admin_unset():
    instance = _make_instance("gpt-4o")
    with patch("litellm.get_model_info", return_value={"max_input_tokens": 128_000}):
        assert instance.get_max_input_tokens() == 128_000


def test_bare_name_fallback_when_prefixed_lookup_fails():
    instance = _make_instance("openai/foo")

    def fake(name):
        if name == "openai/foo":
            raise Exception("unknown model")
        if name == "foo":
            return {"max_input_tokens": 42_000}
        raise Exception("unknown model")

    with patch("litellm.get_model_info", side_effect=fake):
        assert instance.get_max_input_tokens() == 42_000


def test_returns_none_when_all_lookups_fail():
    instance = _make_instance("openai/unknown")

    with patch("litellm.get_model_info", side_effect=Exception("unknown model")):
        assert instance.get_max_input_tokens() is None


def test_returns_none_when_no_slash_and_registry_fails():
    instance = _make_instance("weird-model")

    with patch("litellm.get_model_info", side_effect=Exception("unknown model")):
        assert instance.get_max_input_tokens() is None


def test_registry_result_without_max_input_tokens_key_falls_through():
    """Registry returns a dict missing ``max_input_tokens`` → treat as miss
    and fall through to the bare-name lookup."""
    instance = _make_instance("openai/gpt-4o")

    def fake(name):
        if name == "openai/gpt-4o":
            return {"model_name": "gpt-4o"}  # no max_input_tokens
        if name == "gpt-4o":
            return {"max_input_tokens": 128_000}
        raise Exception("unknown")

    with patch("litellm.get_model_info", side_effect=fake):
        assert instance.get_max_input_tokens() == 128_000


def test_admin_zero_is_treated_as_unset():
    """Falsy admin value must not block registry fallback."""
    instance = _make_instance("gpt-4o", max_input_tokens=0)
    with patch("litellm.get_model_info", return_value={"max_input_tokens": 128_000}):
        assert instance.get_max_input_tokens() == 128_000


@pytest.mark.parametrize("value", [None, ""])
def test_admin_falsy_values_fallthrough(value):
    instance = _make_instance("gpt-4o", max_input_tokens=value)
    with patch("litellm.get_model_info", return_value={"max_input_tokens": 64_000}):
        assert instance.get_max_input_tokens() == 64_000
