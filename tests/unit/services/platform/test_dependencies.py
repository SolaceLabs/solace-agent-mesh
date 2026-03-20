"""Unit tests for the get_component_instance dependency."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException


class TestGetComponentInstance:
    """Tests for dependencies.get_component_instance."""

    def test_returns_component_when_initialized(self):
        """Returns the platform component instance when it's set."""
        import solace_agent_mesh.services.platform.api.dependencies as deps

        mock_component = Mock()
        original = deps.platform_component_instance
        try:
            deps.platform_component_instance = mock_component
            result = deps.get_component_instance()
            assert result is mock_component
        finally:
            deps.platform_component_instance = original

    def test_raises_503_when_not_initialized(self):
        """Raises HTTPException 503 when component is None."""
        import solace_agent_mesh.services.platform.api.dependencies as deps

        original = deps.platform_component_instance
        try:
            deps.platform_component_instance = None
            with pytest.raises(HTTPException) as exc_info:
                deps.get_component_instance()
            assert exc_info.value.status_code == 503
            assert "not initialized" in exc_info.value.detail
        finally:
            deps.platform_component_instance = original
