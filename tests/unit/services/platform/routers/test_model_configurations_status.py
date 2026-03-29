"""Unit tests for GET /models/status endpoint.

Tests:
- Returns configured=False when no models exist
- Returns configured=False when only general exists
- Returns configured=False when only planning exists
- Returns configured=False when general has empty model_name
- Returns configured=False when planning has empty model_name
- Returns configured=True when both general and planning have valid model_name
- Returns configured=False when general has whitespace-only model_name
"""

from unittest.mock import Mock

import pytest

from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
    get_models_status,
)


def _make_config(alias: str, model_name: str | None = None) -> Mock:
    """Create a mock model config with the given alias and model_name."""
    config = Mock()
    config.alias = alias
    config.model_name = model_name
    return config


class TestGetModelsStatus:
    """Tests for GET /models/status endpoint."""

    @pytest.mark.asyncio
    async def test_configured_false_when_no_models(self):
        """Returns configured=False when no models exist."""
        mock_service = Mock()
        mock_service.list_all.return_value = []

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_only_general_exists(self):
        """Returns configured=False when only 'general' alias exists."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", "gpt-4"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_only_planning_exists(self):
        """Returns configured=False when only 'planning' alias exists."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("planning", "gpt-4"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_general_has_empty_model_name(self):
        """Returns configured=False when general has empty model_name."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", ""),
            _make_config("planning", "gpt-4"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_planning_has_empty_model_name(self):
        """Returns configured=False when planning has empty model_name."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", "gpt-4"),
            _make_config("planning", ""),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_general_has_whitespace_model_name(self):
        """Returns configured=False when general has whitespace-only model_name."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", "   "),
            _make_config("planning", "gpt-4"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_general_has_none_model_name(self):
        """Returns configured=False when general has None model_name."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", None),
            _make_config("planning", "gpt-4"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_true_when_both_have_valid_model_names(self):
        """Returns configured=True when both general and planning have valid model_name."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", "gpt-4"),
            _make_config("planning", "claude-3"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is True

    @pytest.mark.asyncio
    async def test_ignores_other_aliases(self):
        """Extra non-general/planning models don't affect the result."""
        mock_service = Mock()
        mock_service.list_all.return_value = [
            _make_config("general", "gpt-4"),
            _make_config("planning", "claude-3"),
            _make_config("custom-model", "llama-3"),
        ]

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is True
