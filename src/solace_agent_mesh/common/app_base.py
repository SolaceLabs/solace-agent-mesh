"""Base App class for all SAM applications with broker and database health checks."""

import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from solace_ai_connector.common.messaging.solace_messaging import ConnectionStatus
from solace_ai_connector.common.monitoring import Monitoring
from solace_ai_connector.flow.app import App
from sqlalchemy import text

log = logging.getLogger(__name__)

# Default timeout for database health checks (in seconds)
DB_HEALTH_CHECK_TIMEOUT_SECONDS = 5.0

# Config keys for custom health checks
CUSTOM_STARTUP_CHECK_KEY = "custom_startup_check"
CUSTOM_READY_CHECK_KEY = "custom_ready_check"


class SamAppBase(App):
    """
    Base class for all SAM applications.

    Extends solace-ai-connector's App class with broker connection and database
    health checks for the is_startup_complete() and is_ready() methods.

    When using dev_mode (DevBroker), broker health checks always return True since
    the DevBroker doesn't have real connection issues to monitor.

    When using a real Solace broker, health checks return True only when
    the broker connection status is CONNECTED.

    When using SQL-based session services, health checks also verify database
    connectivity by testing the connection to each configured database.
    """

    def _is_dev_mode(self) -> bool:
        """
        Check if the broker is configured in dev mode.

        Returns:
            True if dev_mode is enabled or no broker config exists, False otherwise.
        """
        broker_config = self.app_info.get("broker")
        if broker_config is None or broker_config == {}:
            return True  # No config means assume dev mode for safety

        dev_mode = broker_config.get("dev_mode", False)

        # Handle boolean
        if isinstance(dev_mode, bool):
            return dev_mode

        # Handle string "true" (case insensitive)
        if isinstance(dev_mode, str):
            return dev_mode.lower() == "true"

        return False

    def _get_db_health_check_timeout(self) -> float:
        """
        Get the database health check timeout from configuration.

        Reads from app_info['health_check']['database_timeout_seconds'].
        Falls back to DB_HEALTH_CHECK_TIMEOUT_SECONDS if not configured.

        Returns:
            Timeout in seconds for database health checks.
        """
        health_check_config = self.app_info.get("health_check", {})
        timeout = health_check_config.get(
            "database_timeout_seconds", DB_HEALTH_CHECK_TIMEOUT_SECONDS
        )

        # Ensure we have a valid positive number
        if timeout is None:
            return DB_HEALTH_CHECK_TIMEOUT_SECONDS

        try:
            timeout = float(timeout)
            if timeout <= 0:
                log.warning(
                    "Invalid database_timeout_seconds value: %s, using default: %s",
                    timeout,
                    DB_HEALTH_CHECK_TIMEOUT_SECONDS,
                )
                return DB_HEALTH_CHECK_TIMEOUT_SECONDS
            return timeout
        except (TypeError, ValueError):
            log.warning(
                "Invalid database_timeout_seconds value: %s, using default: %s",
                timeout,
                DB_HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            return DB_HEALTH_CHECK_TIMEOUT_SECONDS

    def _is_broker_connected(self) -> bool:
        """
        Check if the broker connection is healthy.

        When using dev_mode, this always returns True since the DevBroker
        doesn't have real connection state to check.

        When using a real Solace broker, this checks the Monitoring singleton's
        connection status and returns True only if CONNECTED.

        Returns:
            True if broker is connected (or in dev_mode), False otherwise.
        """
        # Dev mode always returns True
        if self._is_dev_mode():
            log.debug("Broker health check: dev_mode enabled, returning True")
            return True

        # For real broker, check the Monitoring singleton's connection status
        monitoring = Monitoring()
        status = monitoring.get_connection_status()

        is_connected = status == ConnectionStatus.CONNECTED

        if not is_connected:
            log.debug(
                "Broker health check: connection status is %s, returning False",
                status,
            )

        return is_connected

    def _get_db_engines_from_components(self) -> list:
        """
        Collect database engines from all components.

        Traverses flows and component groups to find components with:
        - get_db_engine() method (Gateway/Platform pattern)
        - session_service.db_engine attribute (Agent pattern)

        Returns:
            List of SQLAlchemy Engine objects.
        """
        engines = []

        if not hasattr(self, "flows") or not self.flows:
            return engines

        for flow in self.flows:
            if not hasattr(flow, "component_groups") or not flow.component_groups:
                continue

            for group in flow.component_groups:
                for wrapper in group:
                    # Get the actual component from wrapper if needed
                    component = getattr(wrapper, "component", wrapper)

                    # Check for get_db_engine() method (Gateway/Platform pattern)
                    if hasattr(component, "get_db_engine") and callable(
                        component.get_db_engine
                    ):
                        engine = component.get_db_engine()
                        if engine is not None:
                            engines.append(engine)
                    # Check for session_service.db_engine (Agent pattern)
                    elif hasattr(component, "session_service"):
                        session_svc = component.session_service
                        if hasattr(session_svc, "db_engine") and session_svc.db_engine:
                            engines.append(session_svc.db_engine)

        return engines

    def _test_single_db_connection(self, engine) -> bool:
        """
        Test a single database connection.

        Args:
            engine: SQLAlchemy engine to test

        Returns:
            True if connection successful, False otherwise.
        """
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def _is_database_connected(
        self, timeout: float = DB_HEALTH_CHECK_TIMEOUT_SECONDS
    ) -> bool:
        """
        Check if all configured databases are connected.

        Collects database engines from components and tests each connection
        by executing a simple query with a timeout. Returns True only if ALL
        databases are reachable within the timeout period.

        If no databases are configured, returns True.

        Args:
            timeout: Maximum time in seconds to wait for each database connection
                     test. Defaults to DB_HEALTH_CHECK_TIMEOUT_SECONDS (5 seconds).

        Returns:
            True if all databases are connected (or none configured), False otherwise.
        """
        engines = self._get_db_engines_from_components()

        if not engines:
            return True

        for engine in engines:
            try:
                # Use ThreadPoolExecutor to enforce timeout on the connection test
                # Note: We use shutdown(wait=False) to avoid blocking if timeout occurs
                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(self._test_single_db_connection, engine)
                    future.result(timeout=timeout)
                finally:
                    # Don't wait for thread to finish - just release resources
                    executor.shutdown(wait=False)
            except FuturesTimeoutError:
                log.warning(
                    "Database health check failed: timed out after %.1f seconds",
                    timeout,
                )
                return False
            except Exception as e:
                log.warning(
                    "Database health check failed: %s",
                    str(e),
                )
                return False

        return True

    def _load_custom_check(self, check_path: str):
        """
        Load a custom health check callable from a module path.

        Args:
            check_path: Path in format "module.path:function_name"

        Returns:
            The callable function, or None if loading fails.
        """
        # Use cached callable if available
        if not hasattr(self, "_custom_check_cache"):
            self._custom_check_cache = {}

        if check_path in self._custom_check_cache:
            return self._custom_check_cache[check_path]

        try:
            if ":" not in check_path:
                log.error(
                    "Invalid custom health check path '%s': "
                    "expected format 'module.path:function_name'",
                    check_path,
                )
                return None

            module_path, function_name = check_path.rsplit(":", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, function_name)

            if not callable(func):
                log.error(
                    "Custom health check '%s' is not callable",
                    check_path,
                )
                return None

            # Cache the callable
            self._custom_check_cache[check_path] = func
            log.info("Loaded custom health check: %s", check_path)
            return func

        except ImportError as e:
            log.error(
                "Failed to import custom health check module '%s': %s",
                check_path,
                e,
            )
            return None
        except AttributeError as e:
            log.error(
                "Custom health check function not found '%s': %s",
                check_path,
                e,
            )
            return None

    def _run_custom_check(self, check_key: str) -> bool:
        """
        Run a custom health check if configured.

        The custom health check function receives the application instance,
        allowing it to access app_info, flows, and other application state.

        Args:
            check_key: The config key for the custom check
                       (CUSTOM_STARTUP_CHECK_KEY or CUSTOM_READY_CHECK_KEY)

        Returns:
            True if check passes or no custom check configured, False if check fails.
        """
        health_check_config = self.app_info.get("health_check", {})
        check_path = health_check_config.get(check_key)

        if not check_path:
            return True  # No custom check configured

        func = self._load_custom_check(check_path)
        if func is None:
            # Loading failed - treat as unhealthy
            return False

        try:
            result = func(self)

            if not isinstance(result, bool):
                log.warning(
                    "Custom health check '%s' returned non-boolean value: %s, "
                    "treating as unhealthy",
                    check_path,
                    result,
                )
                return False

            if not result:
                log.warning("Custom health check '%s' returned False", check_path)

            return result

        except Exception as e:
            log.error(
                "Custom health check '%s' raised exception: %s",
                check_path,
                e,
            )
            return False

    def is_startup_complete(self) -> bool:
        """
        Check if the app has completed its startup/initialization phase.

        Returns True if:
        - Broker is connected (or using dev_mode)
        - All configured databases are connected
        - Custom startup check passes (if configured)

        Returns False if:
        - Broker is DISCONNECTED or RECONNECTING
        - Any configured database is unreachable
        - Custom startup check returns False or raises an exception

        Returns:
            bool: True if startup is complete, False if still initializing
        """
        timeout = self._get_db_health_check_timeout()
        return (
            self._is_broker_connected()
            and self._is_database_connected(timeout)
            and self._run_custom_check(CUSTOM_STARTUP_CHECK_KEY)
        )

    def is_ready(self) -> bool:
        """
        Check if the app is ready to process messages.

        Returns True if:
        - Broker is connected (or using dev_mode)
        - All configured databases are connected
        - Custom ready check passes (if configured)

        Returns False if:
        - Broker is DISCONNECTED or RECONNECTING
        - Any configured database is unreachable
        - Custom ready check returns False or raises an exception

        Returns:
            bool: True if the app is ready, False otherwise
        """
        timeout = self._get_db_health_check_timeout()
        return (
            self._is_broker_connected()
            and self._is_database_connected(timeout)
            and self._run_custom_check(CUSTOM_READY_CHECK_KEY)
        )
