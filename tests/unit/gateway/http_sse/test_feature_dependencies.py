"""
Unit tests for require_feature and get_feature_value dependency factories.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from solace_agent_mesh.common.features.fastapi import (
    require_feature,
    get_feature_value,
)


class TestRequireFeature:
    """Tests for the require_feature dependency factory."""

    def test_raises_404_when_flag_disabled(self):
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = False

        with patch("solace_agent_mesh.common.features.fastapi.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            check = require_feature("my_flag")
            with pytest.raises(HTTPException) as exc_info:
                check()

        assert exc_info.value.status_code == 404
        mock_client.get_boolean_value.assert_called_once_with("my_flag", False)

    def test_passes_when_flag_enabled(self):
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = True

        with patch("solace_agent_mesh.common.features.fastapi.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            check = require_feature("my_flag")
            result = check()

        assert result is None
        mock_client.get_boolean_value.assert_called_once_with("my_flag", False)


class TestGetFeatureValue:
    """Tests for the get_feature_value dependency factory."""

    def test_returns_true_when_enabled(self):
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = True

        with patch("solace_agent_mesh.common.features.fastapi.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            resolve = get_feature_value("my_flag")
            result = resolve()

        assert result is True
        mock_client.get_boolean_value.assert_called_once_with("my_flag", False)

    def test_returns_false_when_disabled(self):
        mock_client = MagicMock()
        mock_client.get_boolean_value.return_value = False

        with patch("solace_agent_mesh.common.features.fastapi.openfeature_api") as mock_api:
            mock_api.get_client.return_value = mock_client
            resolve = get_feature_value("my_flag")
            result = resolve()

        assert result is False
        mock_client.get_boolean_value.assert_called_once_with("my_flag", False)
