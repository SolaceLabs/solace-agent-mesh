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

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_database_connected_timeout_returns_false(self, mock_app_init):
        """When database connection times out, returns False."""
        import time

        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)

        # Mock an engine that takes longer than the timeout to connect
        def slow_connect(*args, **kwargs):
            time.sleep(2)  # Sleep longer than our short timeout
            return MagicMock()

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = slow_connect

        mock_component = MagicMock()
        mock_component.get_db_engine.return_value = mock_engine

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        # Use a very short timeout (0.1 seconds)
        result = app._is_database_connected(timeout=0.1)
        assert result is False


class TestSamAppBaseDatabaseTimeoutConfig:
    """Tests for configurable database health check timeout."""

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_default(self, mock_app_init):
        """When no config, returns default timeout."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            DB_HEALTH_CHECK_TIMEOUT_SECONDS,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {}

        result = app._get_db_health_check_timeout()
        assert result == DB_HEALTH_CHECK_TIMEOUT_SECONDS

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_custom_value(self, mock_app_init):
        """When config specifies timeout, returns that value."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"health_check": {"database_timeout_seconds": 10.0}}

        result = app._get_db_health_check_timeout()
        assert result == 10.0

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_string_value(self, mock_app_init):
        """When config specifies timeout as string, converts to float."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {"health_check": {"database_timeout_seconds": "3.5"}}

        result = app._get_db_health_check_timeout()
        assert result == 3.5

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_invalid_string(self, mock_app_init):
        """When config has invalid string, returns default."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            DB_HEALTH_CHECK_TIMEOUT_SECONDS,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {"health_check": {"database_timeout_seconds": "invalid"}}

        result = app._get_db_health_check_timeout()
        assert result == DB_HEALTH_CHECK_TIMEOUT_SECONDS

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_negative_value(self, mock_app_init):
        """When config has negative value, returns default."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            DB_HEALTH_CHECK_TIMEOUT_SECONDS,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {"health_check": {"database_timeout_seconds": -5}}

        result = app._get_db_health_check_timeout()
        assert result == DB_HEALTH_CHECK_TIMEOUT_SECONDS

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_get_db_health_check_timeout_zero_value(self, mock_app_init):
        """When config has zero value, returns default."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            DB_HEALTH_CHECK_TIMEOUT_SECONDS,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {"health_check": {"database_timeout_seconds": 0}}

        result = app._get_db_health_check_timeout()
        assert result == DB_HEALTH_CHECK_TIMEOUT_SECONDS

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_uses_configured_timeout(self, mock_app_init):
        """is_ready uses timeout from configuration."""
        import time

        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        # Configure a very short timeout (0.1 seconds)
        app.app_info = {
            "broker": {"dev_mode": True},
            "health_check": {"database_timeout_seconds": 0.1},
        }

        # Mock an engine that takes longer than the configured timeout
        def slow_connect(*args, **kwargs):
            time.sleep(2)
            return MagicMock()

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = slow_connect

        mock_component = MagicMock()
        mock_component.get_db_engine.return_value = mock_engine

        mock_wrapper = MagicMock()
        mock_wrapper.component = mock_component

        mock_flow = MagicMock()
        mock_flow.component_groups = [[mock_wrapper]]
        app.flows = [mock_flow]

        # Should fail due to configured timeout
        result = app.is_ready()
        assert result is False


class TestSamAppBaseCustomHealthChecks:
    """Tests for custom health check functionality."""

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_no_custom_check_configured_returns_true(self, mock_app_init):
        """When no custom check is configured, _run_custom_check returns True."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {}

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is True

    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_invalid_path_format_returns_false(self, mock_app_init):
        """When custom check path is missing colon, returns False."""
        mock_app_init.return_value = None

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "invalid_path_without_colon"
            }
        }

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is False

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_module_not_found_returns_false(
        self, mock_app_init, mock_import
    ):
        """When custom check module cannot be imported, returns False."""
        mock_app_init.return_value = None
        mock_import.side_effect = ImportError("Module not found")

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "nonexistent.module:check_func"
            }
        }

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is False

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_function_not_found_returns_false(
        self, mock_app_init, mock_import
    ):
        """When custom check function doesn't exist in module, returns False."""
        mock_app_init.return_value = None
        mock_module = MagicMock(spec=[])  # Module without the function
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:nonexistent_func"
            }
        }

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is False

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_returns_true_when_function_returns_true(
        self, mock_app_init, mock_import
    ):
        """When custom check function returns True, _run_custom_check returns True."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=True)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is True
        mock_func.assert_called_once()

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_returns_false_when_function_returns_false(
        self, mock_app_init, mock_import
    ):
        """When custom check function returns False, _run_custom_check returns False."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=False)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is False

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_returns_false_when_function_raises_exception(
        self, mock_app_init, mock_import
    ):
        """When custom check function raises exception, returns False."""
        mock_app_init.return_value = None

        mock_func = MagicMock(side_effect=Exception("Check failed"))
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        result = app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        assert result is False

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_passes_app_to_function(
        self, mock_app_init, mock_import
    ):
        """Custom check function receives the application instance."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=True)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        app._run_custom_check(CUSTOM_READY_CHECK_KEY)

        # Verify the application was passed to the function
        mock_func.assert_called_once_with(app)

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_custom_check_caches_callable(self, mock_app_init, mock_import):
        """Custom check callable is cached and not reimported."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=True)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import (
            CUSTOM_READY_CHECK_KEY,
            SamAppBase,
        )

        app = object.__new__(SamAppBase)
        app.app_info = {
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        # Call twice
        app._run_custom_check(CUSTOM_READY_CHECK_KEY)
        app._run_custom_check(CUSTOM_READY_CHECK_KEY)

        # import_module should only be called once (cached)
        mock_import.assert_called_once()

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_calls_custom_ready_check(self, mock_app_init, mock_import):
        """is_ready calls custom_ready_check when configured."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=True)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {
            "broker": {"dev_mode": True},
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        result = app.is_ready()
        assert result is True
        mock_func.assert_called_once()

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_startup_complete_calls_custom_startup_check(
        self, mock_app_init, mock_import
    ):
        """is_startup_complete calls custom_startup_check when configured."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=True)
        mock_module = MagicMock()
        mock_module.check_startup = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {
            "broker": {"dev_mode": True},
            "health_check": {
                "custom_startup_check": "mymodule:check_startup"
            }
        }
        app.flows = []

        result = app.is_startup_complete()
        assert result is True
        mock_func.assert_called_once()

    @patch("solace_agent_mesh.common.app_base.importlib.import_module")
    @patch("solace_agent_mesh.common.app_base.App.__init__")
    def test_is_ready_fails_when_custom_check_returns_false(
        self, mock_app_init, mock_import
    ):
        """is_ready returns False when custom check returns False."""
        mock_app_init.return_value = None

        mock_func = MagicMock(return_value=False)
        mock_module = MagicMock()
        mock_module.check_ready = mock_func
        mock_import.return_value = mock_module

        from solace_agent_mesh.common.app_base import SamAppBase

        app = object.__new__(SamAppBase)
        app.app_info = {
            "broker": {"dev_mode": True},
            "health_check": {
                "custom_ready_check": "mymodule:check_ready"
            }
        }
        app.flows = []

        result = app.is_ready()
        assert result is False
