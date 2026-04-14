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
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert result is None
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}

    @pytest.mark.asyncio
    async def test_failed_resolution_returns_error_reason(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = None
        metadata = {"model_override": {"model_id": "unknown-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert isinstance(result, str)
        assert "unknown-alias" in result

    @pytest.mark.asyncio
    async def test_no_provider_returns_error_reason(self):
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(metadata, None, "[Test]")

        assert isinstance(result, str)
        assert "not available" in result

    @pytest.mark.asyncio
    async def test_no_override_in_metadata_is_noop(self):
        dmp = AsyncMock()
        metadata = {"some_other_key": "value"}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert result is None
        dmp.resolve.assert_not_awaited()
        assert metadata == {"some_other_key": "value"}

    @pytest.mark.asyncio
    async def test_none_override_is_noop(self):
        dmp = AsyncMock()
        metadata = {"model_override": None}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert result is None
        dmp.resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bare_string_stripped(self):
        metadata = {"model_override": "my-alias"}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_raw_config_dict_stripped(self):
        """Raw config dict without model_id wrapper is not accepted."""
        metadata = {"model_override": {"model": "openai/gpt-4o", "api_key": "sk-123"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_model_id_stripped(self):
        metadata = {"model_override": {"model_id": ""}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_dict_stripped(self):
        metadata = {"model_override": {}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_non_string_model_id_stripped(self):
        metadata = {"model_override": {"model_id": 12345}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert "model_override" not in metadata


class TestModelOverrideFeatureFlag:
    """Test that model_override is gated behind the offline_evals flag."""

    @pytest.mark.asyncio
    async def test_flag_disabled_strips_override(self):
        dmp = AsyncMock()
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=False):
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert result is None
        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_flag_disabled_no_override_is_noop(self):
        metadata = {"some_key": "value"}

        with mock_flags(offline_evals=False):
            result = await _resolve_model_override_metadata(
                metadata, AsyncMock(), "[Test]"
            )

        assert result is None
        assert metadata == {"some_key": "value"}

    @pytest.mark.asyncio
    async def test_flag_enabled_resolves_alias(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        metadata = {"model_override": {"model_id": "my-alias"}}

        with mock_flags(offline_evals=True):
            result = await _resolve_model_override_metadata(metadata, dmp, "[Test]")

        assert result is None
        dmp.resolve.assert_awaited_once_with("my-alias")
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}
