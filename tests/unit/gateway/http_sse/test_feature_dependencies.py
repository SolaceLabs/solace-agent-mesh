"""
Unit tests for require_feature and get_feature_value dependency factories.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.dependencies import (
    require_feature,
    get_feature_value,
)


class TestRequireFeature:
    """Tests for the require_feature dependency factory."""

    def test_raises_404_when_flag_disabled(self):
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = False

        check = require_feature("my_flag")
        with pytest.raises(HTTPException) as exc_info:
            check(component=mock_component)

        assert exc_info.value.status_code == 404
        mock_component.feature_checker.is_enabled.assert_called_once_with("my_flag")

    def test_passes_when_flag_enabled(self):
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = True

        check = require_feature("my_flag")
        result = check(component=mock_component)

        assert result is None
        mock_component.feature_checker.is_enabled.assert_called_once_with("my_flag")


class TestGetFeatureValue:
    """Tests for the get_feature_value dependency factory."""

    def test_returns_true_when_enabled(self):
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = True

        resolve = get_feature_value("my_flag")
        result = resolve(component=mock_component)

        assert result is True
        mock_component.feature_checker.is_enabled.assert_called_once_with("my_flag")

    def test_returns_false_when_disabled(self):
        mock_component = MagicMock()
        mock_component.feature_checker.is_enabled.return_value = False

        resolve = get_feature_value("my_flag")
        result = resolve(component=mock_component)

        assert result is False
        mock_component.feature_checker.is_enabled.assert_called_once_with("my_flag")
