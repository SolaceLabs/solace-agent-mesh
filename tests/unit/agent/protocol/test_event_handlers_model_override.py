"""Tests for model_override alias resolution in _handle_send_message_request.

These tests verify the alias resolution logic that runs in the event handler,
specifically the block that transforms structured model_override dicts into
resolved raw config dicts before ADK processing.

Expected input format: {"model_override": {"model_id": "<alias-or-uuid>"}}
Feature-gated behind the offline_evals flag.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


_REQUEST_FAILED = object()


async def _resolve_model_override_in_metadata(
    component, task_metadata, flag_enabled=True
):
    """Mirror the model_override resolution logic from event_handlers.py.

    Returns _REQUEST_FAILED if resolution fails (request should be rejected).
    Returns None on success or no-op.
    """
    model_override = task_metadata.get("model_override")
    if model_override is not None:
        if not flag_enabled:
            task_metadata.pop("model_override", None)
            return None
        if (
            isinstance(model_override, dict)
            and isinstance(model_override.get("model_id"), str)
            and model_override["model_id"]
        ):
            model_id = model_override["model_id"]
            resolved = None
            if component._dynamic_model_provider:
                resolved = await component._dynamic_model_provider.resolve(model_id)
            if resolved:
                task_metadata["model_override"] = resolved
            else:
                return _REQUEST_FAILED
        else:
            task_metadata.pop("model_override", None)
    return None


def _make_component(dmp=None):
    component = MagicMock()
    component._dynamic_model_provider = dmp
    component.log_identifier = "[TestComponent]"
    return component


class TestModelOverrideAliasResolution:
    """Test the alias resolution behavior in the event handler."""

    @pytest.mark.asyncio
    async def test_alias_resolved_to_dict(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": "my-gpt4-alias"}}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_awaited_once_with("my-gpt4-alias")
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}

    @pytest.mark.asyncio
    async def test_failed_resolution_rejects_request(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = None
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": "unknown-alias"}}

        result = await _resolve_model_override_in_metadata(component, metadata)

        assert result is _REQUEST_FAILED

    @pytest.mark.asyncio
    async def test_no_provider_rejects_request(self):
        component = _make_component(dmp=None)
        metadata = {"model_override": {"model_id": "my-alias"}}

        result = await _resolve_model_override_in_metadata(component, metadata)

        assert result is _REQUEST_FAILED

    @pytest.mark.asyncio
    async def test_no_override_in_metadata_is_noop(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"some_other_key": "value"}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert metadata == {"some_other_key": "value"}

    @pytest.mark.asyncio
    async def test_none_override_is_noop(self):
        """None value is harmless — callback treats it as no override."""
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": None}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bare_string_stripped(self):
        """Bare string is not the expected format — should be stripped."""
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": "my-alias"}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_raw_dict_stripped(self):
        """Raw config dict without model_id wrapper is not accepted."""
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": {"model": "openai/gpt-4o", "api_key": "sk-123"}}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_model_id_stripped(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": ""}}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_dict_stripped(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": {}}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_non_string_model_id_stripped(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": 12345}}

        await _resolve_model_override_in_metadata(component, metadata)

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata


class TestModelOverrideFeatureFlag:
    """Test that model_override is gated behind the offline_evals flag."""

    @pytest.mark.asyncio
    async def test_flag_disabled_strips_override(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": "my-alias"}}

        await _resolve_model_override_in_metadata(
            component, metadata, flag_enabled=False
        )

        dmp.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_flag_disabled_no_override_is_noop(self):
        dmp = AsyncMock()
        component = _make_component(dmp)
        metadata = {"some_key": "value"}

        await _resolve_model_override_in_metadata(
            component, metadata, flag_enabled=False
        )

        assert metadata == {"some_key": "value"}

    @pytest.mark.asyncio
    async def test_flag_enabled_resolves_alias(self):
        dmp = AsyncMock()
        dmp.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        component = _make_component(dmp)
        metadata = {"model_override": {"model_id": "my-alias"}}

        await _resolve_model_override_in_metadata(
            component, metadata, flag_enabled=True
        )

        dmp.resolve.assert_awaited_once_with("my-alias")
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}
