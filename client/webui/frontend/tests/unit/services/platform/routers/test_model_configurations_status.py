"""Unit tests for GET /models/status endpoint."""

from unittest.mock import Mock

import pytest

from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
    get_models_status,
)


def _make_config(alias, model_name=None):
    config = Mock()
    config.alias = alias
    config.model_name = model_name
    return config


class TestGetModelsStatus:

    @pytest.mark.asyncio
    async def test_configured_false_when_no_models(self):
        svc = Mock()
        svc.list_all.return_value = []
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_only_general(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", "gpt-4")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_only_planning(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("planning", "gpt-4")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_general_empty(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", ""), _make_config("planning", "gpt-4")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_planning_empty(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", "gpt-4"), _make_config("planning", "")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_whitespace(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", "   "), _make_config("planning", "gpt-4")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_false_when_none(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", None), _make_config("planning", "gpt-4")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is False

    @pytest.mark.asyncio
    async def test_configured_true_when_both_valid(self):
        svc = Mock()
        svc.list_all.return_value = [_make_config("general", "gpt-4"), _make_config("planning", "claude-3")]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is True

    @pytest.mark.asyncio
    async def test_ignores_other_aliases(self):
        svc = Mock()
        svc.list_all.return_value = [
            _make_config("general", "gpt-4"),
            _make_config("planning", "claude-3"),
            _make_config("custom", "llama-3"),
        ]
        result = await get_models_status(db=Mock(), service=svc)
        assert result.data.configured is True
