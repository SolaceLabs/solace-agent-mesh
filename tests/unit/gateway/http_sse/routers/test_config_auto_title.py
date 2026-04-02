"""
Unit tests for feature-flag-gated configuration helpers in config.py router.
"""
import pytest
from unittest.mock import MagicMock

from sam_test_infrastructure.feature_flags import mock_flags
from solace_agent_mesh.common.features import core as feature_flags
from solace_agent_mesh.gateway.http_sse.routers.config import (
    _determine_auto_title_generation_enabled,
    _determine_mentions_enabled,
)


@pytest.fixture(autouse=True)
def _reset_feature_flags():
    feature_flags._reset_for_testing()
    feature_flags.initialize()
    yield
    feature_flags._reset_for_testing()


class TestDetermineAutoTitleGenerationEnabled:
    """Tests for _determine_auto_title_generation_enabled function."""

    def test_disabled_when_persistence_not_enabled(self):
        mock_component = MagicMock()

        result = _determine_auto_title_generation_enabled(
            mock_component, {"persistence_enabled": False}, "[TEST]"
        )

        assert result is False

    def test_disabled_when_flag_is_off(self):
        mock_component = MagicMock()

        with mock_flags(auto_title_generation=False):
            result = _determine_auto_title_generation_enabled(
                mock_component, {"persistence_enabled": True}, "[TEST]"
            )

        assert result is False

    def test_enabled_when_persistence_and_flag_on(self):
        mock_component = MagicMock()

        with mock_flags(auto_title_generation=True):
            result = _determine_auto_title_generation_enabled(
                mock_component, {"persistence_enabled": True}, "[TEST]"
            )

        assert result is True


class TestDetermineMentionsEnabled:
    """Tests for _determine_mentions_enabled function."""

    def test_disabled_when_no_identity_service(self):
        mock_component = MagicMock()
        mock_component.identity_service = None

        result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is False

    def test_disabled_when_flag_is_off(self):
        mock_component = MagicMock()
        mock_component.identity_service = MagicMock()

        with mock_flags(mentions=False):
            result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is False

    def test_enabled_when_identity_service_and_flag_on(self):
        mock_component = MagicMock()
        mock_component.identity_service = MagicMock()

        with mock_flags(mentions=True):
            result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is True
