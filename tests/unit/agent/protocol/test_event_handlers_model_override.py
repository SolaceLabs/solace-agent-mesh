"""Tests for model_override alias resolution in _handle_send_message_request.

These tests verify the alias resolution logic that runs in the event handler,
specifically the block that transforms structured model_override dicts into
resolved raw config dicts before ADK processing.

Expected input format: {"model_override": {"model_id": "<alias-or-uuid>"}}
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


async def _resolve_model_override_in_metadata(component, task_metadata):
    """Mirror the model_override resolution logic from event_handlers.py."""
    model_override = task_metadata.get("model_override")
    if (
        isinstance(model_override, dict)
        and isinstance(model_override.get("model_id"), str)
        and model_override["model_id"]
    ):
        model_id = model_override["model_id"]
        if component.model_override_resolver:
            resolved = await component.model_override_resolver.resolve(model_id)
            if resolved:
                task_metadata["model_override"] = resolved
            else:
                task_metadata.pop("model_override", None)
        else:
            task_metadata.pop("model_override", None)
    elif model_override is not None:
        task_metadata.pop("model_override", None)


def _make_component(resolver=None):
    component = MagicMock()
    component.model_override_resolver = resolver
    component.log_identifier = "[TestComponent]"
    return component


class TestModelOverrideAliasResolution:
    """Test the alias resolution behavior in the event handler."""

    @pytest.mark.asyncio
    async def test_alias_resolved_to_dict(self):
        resolver = AsyncMock()
        resolver.resolve.return_value = {"model": "openai/gpt-4o", "api_key": "sk-test"}
        component = _make_component(resolver)
        metadata = {"model_override": {"model_id": "my-gpt4-alias"}}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_awaited_once_with("my-gpt4-alias")
        assert metadata["model_override"] == {"model": "openai/gpt-4o", "api_key": "sk-test"}

    @pytest.mark.asyncio
    async def test_failed_resolution_removes_override(self):
        resolver = AsyncMock()
        resolver.resolve.return_value = None
        component = _make_component(resolver)
        metadata = {"model_override": {"model_id": "unknown-alias"}}

        await _resolve_model_override_in_metadata(component, metadata)

        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_no_resolver_removes_override(self):
        component = _make_component(resolver=None)
        metadata = {"model_override": {"model_id": "my-alias"}}

        await _resolve_model_override_in_metadata(component, metadata)

        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_no_override_in_metadata_is_noop(self):
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"some_other_key": "value"}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert metadata == {"some_other_key": "value"}

    @pytest.mark.asyncio
    async def test_none_override_is_noop(self):
        """None value is harmless — callback treats it as no override."""
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": None}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bare_string_stripped(self):
        """Bare string is not the expected format — should be stripped."""
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": "my-alias"}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_raw_dict_stripped(self):
        """Raw config dict without model_id wrapper is not accepted."""
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": {"model": "openai/gpt-4o", "api_key": "sk-123"}}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_model_id_stripped(self):
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": {"model_id": ""}}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_empty_dict_stripped(self):
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": {}}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert "model_override" not in metadata

    @pytest.mark.asyncio
    async def test_non_string_model_id_stripped(self):
        resolver = AsyncMock()
        component = _make_component(resolver)
        metadata = {"model_override": {"model_id": 12345}}

        await _resolve_model_override_in_metadata(component, metadata)

        resolver.resolve.assert_not_awaited()
        assert "model_override" not in metadata
