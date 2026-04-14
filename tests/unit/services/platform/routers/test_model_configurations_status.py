"""Unit tests for GET /models/status endpoint.

Tests that the router delegates to service.are_default_models_configured()
and returns the result in the expected response shape.
"""

from unittest.mock import Mock

import pytest

from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
    get_models_status,
)


class TestGetModelsStatus:
    """Tests for GET /models/status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_configured_false(self):
        """Returns configured=False when service reports not configured."""
        mock_service = Mock()
        mock_service.are_default_models_configured.return_value = False

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is False
        mock_service.are_default_models_configured.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_configured_true(self):
        """Returns configured=True when service reports configured."""
        mock_service = Mock()
        mock_service.are_default_models_configured.return_value = True

        result = await get_models_status(db=Mock(), service=mock_service)

        assert result.data.configured is True
        mock_service.are_default_models_configured.assert_called_once()
