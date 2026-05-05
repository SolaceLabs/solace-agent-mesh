"""Tests for model_override alias resolution in _resolve_model_override_metadata.

These tests exercise the real resolution function from event_handlers.py,
which validates the metadata schema, checks the offline_evals feature flag,
and resolves aliases via the DynamicModelProvider.

Expected input format: {"model_override": {"model_id": "<alias-or-uuid>"}}
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from sam_test_infrastructure.feature_flags import mock_flags
from solace_agent_mesh.common.features import core as feature_flags
from solace_agent_mesh.agent.protocol.event_handlers import (
    _resolve_model_override_metadata,
)


def _component(dmp=None, litellm=None):
    """Build a stand-in component for the resolver.

    The resolver reads ``_dynamic_model_provider`` and may call
    ``get_lite_llm_model()`` for lazy-init. Tests that don't exercise lazy-init
    can leave ``litellm`` unset.
    """
    component = MagicMock()
    component._dynamic_model_provider = dmp
    component._dynamic_model_provider_init_lock = None
    component.get_lite_llm_model = MagicMock(return_value=litellm)
    component.log_identifier = "[TestComponent]"
    return component


@pytest.fixture(autouse=True)
def _reset_feature_flags():
    feature_flags._reset_for_testing()
    feature_flags.initialize()
    yield
    feature_flags._reset_for_testing()


class TestModelOverrideAliasResolution:
    """Test the alias resolution behavior."""

    @pytest.mark.asyncio
    async def test_alias_resolved_to_config(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        metadata = {"model_override": {"model_id": "my-gpt4-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert result is None
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}

    @pytest.mark.asyncio
    async def test_failed_resolution_returns_error_reason(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = None
        metadata = {"model_override": {"model_id": "unknown-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert isinstance(result, str)
        assert "unknown-alias" in result

    @pytest.mark.asyncio
    async def test_no_provider_no_litellm_returns_error_reason(self):
        """Component with neither a provider nor a litellm can't resolve."""
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=None, litellm=None), "[Test]"
            )

        assert isinstance(result, str)
        assert "not available" in result

    @pytest.mark.asyncio
    async def test_no_override_in_metadata_is_noop(self):
        dmp = AsyncMock()
        metadata = {"some_other_key": "value"}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert result is None
        dmp.resolve.assert_not_awaited()
        assert metadata == {"some_other_key": "value"}

    @pytest.mark.asyncio
    async def test_none_override_is_noop(self):
        dmp = AsyncMock()
        metadata = {"model_override": None}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert result is None
        dmp.resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bare_string_stripped(self):
        metadata = {"model_override": "my-alias"}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_raw_config_dict_stripped(self):
        """Raw config dict without model_id wrapper is not accepted."""
        metadata = {"model_override": {"model": "openai/gpt-4o", "api_key": "sk-123"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_model_id_stripped(self):
        metadata = {"model_override": {"model_id": ""}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_dict_stripped(self):
        metadata = {"model_override": {}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_non_string_model_id_stripped(self):
        metadata = {"model_override": {"model_id": 12345}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata


class TestLazyOverrideProviderInit:
    """Lazy-init path: components without a model_provider configured can still
    accept model_override by spinning up an override-only DynamicModelProvider
    on demand. Without this, the orchestrator agent (which has model: but no
    model_provider:) would reject every eval task with "model config not
    available".
    """

    @pytest.mark.asyncio
    async def test_lazy_init_when_provider_missing(self, monkeypatch):
        from solace_agent_mesh.agent.protocol import event_handlers

        litellm = MagicMock()
        component = _component(dmp=None, litellm=litellm)

        provider = AsyncMock()
        provider.resolve.return_value = {"model": "openai/gpt-4o"}

        # Patch the inline import target inside _ensure_override_provider so the
        # constructor returns our pre-baked AsyncMock instead of creating a real
        # provider (which would try to start an SAC flow).
        provider_factory = MagicMock(return_value=provider)
        import solace_agent_mesh.agent.adk.models.dynamic_model_provider as dmp_mod
        monkeypatch.setattr(dmp_mod, "DynamicModelProvider", provider_factory)

        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await event_handlers._resolve_model_override_metadata(
                metadata, component, "[Test]"
            )

        assert result is None
        # Constructed with skip_bootstrap=True so the agent's static litellm is
        # never replaced via the auto-update flow.
        assert provider_factory.called
        assert provider_factory.call_args.kwargs.get("skip_bootstrap") is True
        assert component._dynamic_model_provider is provider

    @pytest.mark.asyncio
    async def test_lazy_init_skipped_when_litellm_unavailable(self):
        """Without a litellm instance there's nothing to back resolve(); the
        request must be rejected with the same "not available" error rather
        than constructing a dead provider."""
        component = _component(dmp=None, litellm=None)
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, component, "[Test]"
            )

        assert isinstance(result, str)
        assert "not available" in result
        assert component._dynamic_model_provider is None


class TestModelOverrideFeatureFlag:
    """Test that model_override is gated behind the offline_evals flag."""

    @pytest.mark.asyncio
    async def test_flag_disabled_strips_override(self):
        dmp = AsyncMock()
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=False):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert result is None
        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_flag_disabled_no_override_is_noop(self):
        metadata = {"some_key": "value"}

        with mock_flags(offline_evals=False):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=AsyncMock()), "[Test]"
            )

        assert result is None
        assert metadata == {"some_key": "value"}

    @pytest.mark.asyncio
    async def test_flag_enabled_resolves_alias(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, _component(dmp=dmp), "[Test]"
            )

        assert result is None
        dmp.resolve.assert_awaited_once_with("my-alias")
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}
