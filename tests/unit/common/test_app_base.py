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


class TestSamAppBaseDatabaseHealthChecks:
    """Tests for database connectivity health checks."""

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_database_connected_no_components_returns_true(self, mock_app_init):
        """When there are no components with databases, returns True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.flows = []

        result = app._is_database_connected()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_database_connected_with_healthy_engine(self, mock_app_init):
        """When database engine is healthy, returns True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)

        # Mock a component with get_db_engine()
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(
            return_value=mock_connection
        )
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_component = MagicMock()
        mock_component.get_db_engine.return_value = mock_engine

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        result = app._is_database_connected()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_database_connected_with_unhealthy_engine(self, mock_app_init):
        """When database connection fails, returns False."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)

        # Mock a component with get_db_engine() that fails to connect
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection failed")

        mock_component = MagicMock()
        mock_component.get_db_engine.return_value = mock_engine

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        result = app._is_database_connected()
        assert result is False

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_database_connected_with_session_service_db_engine(self, mock_app_init):
        """When component has session_service.db_engine, uses that engine."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)

        # Mock a component with session_service.db_engine (Agent pattern)
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(
            return_value=mock_connection
        )
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_session_service = MagicMock()
        mock_session_service.db_engine = mock_engine

        mock_component = MagicMock(spec=[])  # No get_db_engine method
        mock_component.session_service = mock_session_service

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        result = app._is_database_connected()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_combines_broker_and_database_checks(
        self, mock_app_init, mock_monitoring_class
    ):
        """is_ready returns True only when both broker and database are connected."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = ConnectionStatus.CONNECTED
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"broker": {"dev_mode": False}}
        app.flows = []  # No database components

        result = app.is_ready()
        assert result is True

    @patch("solace_agent_mesh.common.app_base.Monitoring")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_false_when_database_disconnected(
        self, mock_app_init, mock_monitoring_class
    ):
        """is_ready returns False when database is disconnected even if broker is connected."""
        from solace_ai_connector.common.messaging.solace_messaging import (
            ConnectionStatus,
        )

        mock_app_init.return_value = None
        mock_monitoring = MagicMock()
        mock_monitoring.get_connection_status.return_value = ConnectionStatus.CONNECTED
        mock_monitoring_class.return_value = mock_monitoring

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"broker": {"dev_mode": False}}

        # Mock a component with failing database
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection failed")

        mock_component = MagicMock()
        mock_component.get_db_engine.return_value = mock_engine

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        result = app.is_ready()
        assert result is False
