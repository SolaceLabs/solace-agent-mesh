"""Unit tests for LiteLlm status management, configure_model, and unconfigure_model."""

import pytest
from unittest.mock import patch, MagicMock

from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm, VALID_CACHE_STRATEGIES


class TestLiteLlmStatusProperty:
    """Test LiteLlm status tracking."""

    def test_initial_status_is_ready_with_model(self):
        """LiteLlm initialized with a valid model should be 'ready'."""
        llm = LiteLlm(model="test-model")
        assert llm.status == "ready"

    def test_initial_status_is_initializing_without_model(self):
        """LiteLlm initialized with model=None should be 'initializing'."""
        llm = LiteLlm(model=None)
        assert llm.status == "initializing"

    def test_status_after_unconfigure(self):
        """unconfigure_model should set status to 'none'."""
        llm = LiteLlm(model="test-model")
        assert llm.status == "ready"
        llm.unconfigure_model()
        assert llm.status == "none"


class TestLiteLlmOnStatusChangeCallback:
    """Test the on_status_change callback mechanism."""

    def test_callback_invoked_on_init_with_model(self):
        """Callback should be invoked during init when model transitions to ready."""
        callback = MagicMock()
        LiteLlm(model="test-model", on_status_change=callback)
        # Should transition from initializing -> ready
        callback.assert_called_once_with("initializing", "ready")

    def test_callback_not_invoked_on_init_without_model(self):
        """Callback should not fire when model stays in 'initializing' (no transition)."""
        callback = MagicMock()
        LiteLlm(model=None, on_status_change=callback)
        callback.assert_not_called()

    def test_callback_invoked_on_unconfigure(self):
        """Callback should fire when unconfigure_model transitions ready -> none."""
        callback = MagicMock()
        llm = LiteLlm(model="test-model", on_status_change=callback)
        callback.reset_mock()

        llm.unconfigure_model()
        callback.assert_called_once_with("ready", "none")

    def test_callback_invoked_on_reconfigure(self):
        """Callback should fire when configure_model transitions status to ready."""
        callback = MagicMock()
        llm = LiteLlm(model=None, on_status_change=callback)
        callback.assert_not_called()

        llm.configure_model({"model": "new-model"})
        callback.assert_called_once_with("initializing", "ready")

    def test_no_callback_on_same_status(self):
        """Callback should not fire when status doesn't change."""
        callback = MagicMock()
        llm = LiteLlm(model="test-model", on_status_change=callback)
        callback.reset_mock()

        # configure_model with a valid model again should stay 'ready' -> no callback
        llm.configure_model({"model": "another-model"})
        callback.assert_not_called()

    def test_callback_exception_does_not_propagate(self):
        """Errors in the callback should be caught and not raise."""
        callback = MagicMock(side_effect=RuntimeError("callback error"))
        # Should not raise even though callback throws
        llm = LiteLlm(model="test-model", on_status_change=callback)
        assert llm.status == "ready"

    def test_no_callback_when_none(self):
        """No error when on_status_change is None."""
        llm = LiteLlm(model="test-model", on_status_change=None)
        assert llm.status == "ready"
        llm.unconfigure_model()
        assert llm.status == "none"


class TestLiteLlmConfigureModel:
    """Test configure_model method."""

    def test_configure_sets_model_and_status(self):
        """configure_model with valid config sets model and status to ready."""
        llm = LiteLlm(model=None)
        assert llm.status == "initializing"

        llm.configure_model({"model": "gpt-4"})
        assert llm.status == "ready"
        assert llm._model_config["model"] == "gpt-4"

    def test_configure_applies_default_resilience_settings(self):
        """configure_model should set default num_retries and timeout when type is None."""
        llm = LiteLlm(model=None)
        llm.configure_model({"model": "gpt-4"})
        assert llm._model_config["num_retries"] == 3
        assert llm._model_config["timeout"] == 120

    def test_configure_preserves_custom_resilience_settings(self):
        """configure_model should not override user-specified retries/timeout."""
        llm = LiteLlm(model=None)
        llm.configure_model({"model": "gpt-4", "num_retries": 5, "timeout": 300})
        assert llm._model_config["num_retries"] == 5
        assert llm._model_config["timeout"] == 300

    def test_configure_skips_defaults_when_type_set(self):
        """configure_model should not add defaults when 'type' key is present."""
        llm = LiteLlm(model=None)
        llm.configure_model({"model": "gpt-4", "type": "custom"})
        assert "num_retries" not in llm._model_config
        assert "timeout" not in llm._model_config

    def test_configure_with_invalid_type_raises(self):
        """configure_model with non-dict raises ValueError."""
        llm = LiteLlm(model=None)
        with pytest.raises(ValueError, match="Invalid model config type"):
            llm.configure_model("not-a-dict")

    def test_configure_without_model_name_stays_initializing(self):
        """configure_model without 'model' key stays in 'initializing'."""
        llm = LiteLlm(model=None)
        llm.configure_model({"timeout": 60})
        assert llm.status == "initializing"

    def test_configure_cache_strategy_valid(self):
        """configure_model should accept valid cache strategies."""
        for strategy in VALID_CACHE_STRATEGIES:
            llm = LiteLlm(model=None)
            llm.configure_model({"model": "test-model", "cache_strategy": strategy})
            assert llm._cache_strategy == strategy

    def test_configure_cache_strategy_invalid_defaults_to_5m(self):
        """configure_model with invalid cache_strategy defaults to 5m."""
        llm = LiteLlm(model=None)
        with patch("solace_agent_mesh.agent.adk.models.lite_llm.logger") as mock_logger:
            llm.configure_model({"model": "test-model", "cache_strategy": "bad"})
            assert llm._cache_strategy == "5m"
            mock_logger.warning.assert_called()

    def test_configure_strips_cache_strategy_from_model_config(self):
        """cache_strategy should not remain in _model_config after configure_model."""
        llm = LiteLlm(model=None)
        llm.configure_model({"model": "test-model", "cache_strategy": "1h"})
        assert "cache_strategy" not in llm._model_config

    def test_configure_does_not_mutate_input(self):
        """configure_model should not mutate the input dict."""
        config = {"model": "gpt-4", "cache_strategy": "1h"}
        original = config.copy()
        llm = LiteLlm(model=None)
        llm.configure_model(config)
        assert config == original

    def test_configure_with_oauth_sets_token_manager(self):
        """configure_model with OAuth params should initialize token manager."""
        llm = LiteLlm(model=None)
        llm.configure_model({
            "model": "test-model",
            "oauth_client_id": "client-id",
            "oauth_client_secret": "client-secret",
            "oauth_token_url": "https://auth.example.com/token",
        })
        assert llm._oauth_token_manager is not None
        assert llm.status == "ready"

    def test_configure_without_oauth_clears_token_manager(self):
        """configure_model without OAuth params should not set token manager."""
        llm = LiteLlm(model=None)
        llm.configure_model({"model": "test-model"})
        assert llm._oauth_token_manager is None


class TestLiteLlmUnconfigureModel:
    """Test unconfigure_model method."""

    def test_unconfigure_sets_status_to_none(self):
        """unconfigure_model transitions to 'none'."""
        llm = LiteLlm(model="test-model")
        llm.unconfigure_model()
        assert llm.status == "none"

    def test_unconfigure_idempotent(self):
        """Calling unconfigure_model twice should not error."""
        callback = MagicMock()
        llm = LiteLlm(model="test-model", on_status_change=callback)
        callback.reset_mock()

        llm.unconfigure_model()
        assert callback.call_count == 1  # ready -> none

        llm.unconfigure_model()
        assert callback.call_count == 1  # no transition


class TestLiteLlmGenerateContentRejectsWhenNotReady:
    """Test that generate_content_async rejects calls when model is not ready."""

    @pytest.mark.asyncio
    async def test_rejects_when_initializing(self):
        """generate_content_async should raise BadRequestError when status is 'initializing'."""
        from litellm.exceptions import BadRequestError
        from google.adk.models.llm_request import LlmRequest
        from google.genai.types import Content, Part

        llm = LiteLlm(model=None)
        assert llm.status == "initializing"

        content = Content(role="user", parts=[Part(text="Hello")])
        request = LlmRequest(contents=[content])

        with pytest.raises(BadRequestError, match="not been configured"):
            async for _ in llm.generate_content_async(request):
                pass

    @pytest.mark.asyncio
    async def test_rejects_when_unconfigured(self):
        """generate_content_async should raise BadRequestError when status is 'none'."""
        from litellm.exceptions import BadRequestError
        from google.adk.models.llm_request import LlmRequest
        from google.genai.types import Content, Part

        llm = LiteLlm(model="test-model")
        llm.unconfigure_model()
        assert llm.status == "none"

        content = Content(role="user", parts=[Part(text="Hello")])
        request = LlmRequest(contents=[content])

        with pytest.raises(BadRequestError, match="not been configured"):
            async for _ in llm.generate_content_async(request):
                pass


class TestValidCacheStrategiesConstant:
    """Test the VALID_CACHE_STRATEGIES module-level constant."""

    def test_contains_expected_values(self):
        assert "none" in VALID_CACHE_STRATEGIES
        assert "5m" in VALID_CACHE_STRATEGIES
        assert "1h" in VALID_CACHE_STRATEGIES
        assert len(VALID_CACHE_STRATEGIES) == 3
