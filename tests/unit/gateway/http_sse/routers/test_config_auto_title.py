"""
Unit tests for auto_title_generation configuration in config.py router.
"""
import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.routers.config import (
    _determine_auto_title_generation_enabled,
)


class TestDetermineAutoTitleGenerationEnabled:
    """Tests for _determine_auto_title_generation_enabled function."""

    def test_disabled_when_persistence_not_enabled(self):
        """Test disabled when persistence is not enabled."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = {}
        
        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": False}, "[TEST]"
        )
        
        assert result is False

    def test_disabled_when_not_explicitly_enabled(self):
        """Test disabled by default even with persistence."""
        mock_component = MagicMock()
        mock_component.get_config.return_value = {}
        
        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": True}, "[TEST]"
        )
        
        assert result is False

    def test_enabled_via_auto_title_generation_config(self):
        """Test enabling via auto_title_generation config block."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"enabled": True} if k == "auto_title_generation" else {}
        )
        
        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": True}, "[TEST]"
        )
        
        assert result is True

    def test_enabled_via_frontend_feature_enablement(self):
        """Test enabling via frontend_feature_enablement override."""
        mock_component = MagicMock()
        mock_component.get_config.side_effect = lambda k, d=None: (
            {"auto_title_generation": True} if k == "frontend_feature_enablement" else {}
        )
        
        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": True}, "[TEST]"
        )
        
        assert result is True
