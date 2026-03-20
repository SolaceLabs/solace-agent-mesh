"""
Unit tests for feature-flag-gated configuration helpers in config.py router.
"""
import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.gateway.http_sse.routers.config import (
    _determine_auto_title_generation_enabled,
    _determine_mentions_enabled,
)


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
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = False

        with patch("solace_agent_mesh.gateway.http_sse.routers.config.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            result = _determine_auto_title_generation_enabled(
                mock_component, {"persistence_enabled": True}, "[TEST]"
            )

        assert result is False
        mock_client.get_boolean_value.assert_called_once_with("auto_title_generation", False)

    def test_enabled_when_persistence_and_flag_on(self):
        mock_component = MagicMock()
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = True

        with patch("solace_agent_mesh.gateway.http_sse.routers.config.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            result = _determine_auto_title_generation_enabled(
                mock_component, {"persistence_enabled": True}, "[TEST]"
            )

        assert result is True
        mock_client.get_boolean_value.assert_called_once_with("auto_title_generation", False)


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
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = False

        with patch("solace_agent_mesh.gateway.http_sse.routers.config.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is False
        mock_client.get_boolean_value.assert_called_once_with("mentions", False)

    def test_enabled_when_identity_service_and_flag_on(self):
        mock_component = MagicMock()
        mock_component.identity_service = MagicMock()
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = True

        with patch("solace_agent_mesh.gateway.http_sse.routers.config.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            result = _determine_mentions_enabled(mock_component, "[TEST]")

        assert result is True
        mock_client.get_boolean_value.assert_called_once_with("mentions", False)
