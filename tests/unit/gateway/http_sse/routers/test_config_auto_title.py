"""
Unit tests for feature-flag-gated configuration helpers in config.py router.
"""
import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.routers.config import (
    _determine_auto_title_generation_enabled,
    _determine_mentions_enabled,
)


class TestDetermineAutoTitleGenerationEnabled:
    """Tests for _determine_auto_title_generation_enabled function."""

    def test_disabled_when_persistence_not_enabled(self):
        """Test disabled when persistence is not enabled."""
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = True

        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": False}, "[TEST]"
        )

        assert result is False

    def test_disabled_when_flag_is_off(self):
        """Test disabled when feature flag is off, even with persistence."""
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = False

        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": True}, "[TEST]"
        )

        assert result is False

    def test_enabled_when_persistence_and_flag_on(self):
        """Test enabled when persistence is on and feature flag is on."""
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = True

        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": True}, "[TEST]"
        )

        assert result is True
        mock_component.feature_checker.is_enabled.assert_called_once_with("auto_title_generation")


class TestDetermineMentionsEnabled:
    """Tests for _determine_mentions_enabled function."""

    def test_disabled_when_no_identity_service(self):
        mock_component = MagicMock()
        mock_component.identity_service = None
        mock_component.feature_checker.is_enabled.return_value = True

        result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is False
        mock_component.feature_checker.is_enabled.assert_not_called()

    def test_disabled_when_flag_is_off(self):
        mock_component = MagicMock()
        mock_component.identity_service = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = False

        result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is False
        mock_component.feature_checker.is_enabled.assert_called_once_with("mentions")

    def test_enabled_when_identity_service_and_flag_on(self):
        mock_component = MagicMock()
        mock_component.identity_service = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = True

        result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is True
        mock_component.feature_checker.is_enabled.assert_called_once_with("mentions")
