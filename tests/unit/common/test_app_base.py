"""Tests for SamAppBase health check methods."""

from unittest.mock import MagicMock, patch

import pytest


class TestSamAppBaseHealthChecks:
    """Tests for is_startup_complete and is_ready methods."""

    @pytest.fixture
    def mock_app_info_dev_mode(self):
        """Create app_info with dev_mode enabled."""
        return {
            "name": "test_app",
            "broker": {
                "dev_mode": True,
            },
        }

    @pytest.fixture
    def mock_app_info_real_broker(self):
        """Create app_info with real broker (dev_mode disabled)."""
        return {
            "name": "test_app",
            "broker": {
                "dev_mode": False,
            },
        }

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_startup_complete_dev_mode_true_returns_true(
        self, mock_app_init, mock_app_info_dev_mode
    ):
        """When dev_mode is True, is_startup_complete should return True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_dev_mode

        result = app.is_startup_complete()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_startup_complete_dev_mode_string_true_returns_true(self, mock_app_init):
        """When dev_mode is string 'true', is_startup_complete should return True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"name": "test", "broker": {"dev_mode": "true"}}

        result = app.is_startup_complete()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_dev_mode_returns_true(
        self, mock_app_init, mock_app_info_dev_mode
    ):
        """When dev_mode is True, is_ready should return True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_dev_mode

        result = app.is_ready()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_startup_complete_real_broker_connected_returns_true(
        self, mock_app_init, mock_monitoring_class, mock_app_info_real_broker
    ):
        """With real broker connected, is_startup_complete should return True."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = ConnectionStatus.CONNECTED
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_real_broker

        result = app.is_startup_complete()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_startup_complete_real_broker_disconnected_returns_false(
        self, mock_app_init, mock_monitoring_class, mock_app_info_real_broker
    ):
        """With real broker disconnected, is_startup_complete should return False."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = (
            ConnectionStatus.DISCONNECTED
        )
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_real_broker

        result = app.is_startup_complete()
        assert result is False

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_real_broker_reconnecting_returns_false(
        self, mock_app_init, mock_monitoring_class, mock_app_info_real_broker
    ):
        """With real broker reconnecting, is_ready should return False."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = (
            ConnectionStatus.RECONNECTING
        )
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_real_broker

        result = app.is_ready()
        assert result is False

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_real_broker_connected_returns_true(
        self, mock_app_init, mock_monitoring_class, mock_app_info_real_broker
    ):
        """With real broker connected, is_ready should return True."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = ConnectionStatus.CONNECTED
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = mock_app_info_real_broker

        result = app.is_ready()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_no_broker_config_returns_true(self, mock_app_init):
        """When broker config is missing, should return True (assume dev mode)."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"name": "test"}  # No broker key

        result = app.is_startup_complete()
        assert result is True

        result = app.is_ready()
        assert result is True
