"""Base App class for all SAM applications with broker and database health checks."""

import logging

from solace_ai_connector.common.messaging.solace_messaging import ConnectionStatus
from solace_ai_connector.common.monitoring import Monitoring
from solace_ai_connector.flow.app import App
from sqlalchemy import text

log = logging.getLogger(__name__)


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

    def _is_database_connected(self) -> bool:
        """
        Check if all configured databases are connected.

        Collects database engines from components and tests each connection
        by executing a simple query. Returns True only if ALL databases
        are reachable.

        If no databases are configured, returns True.

        Returns:
            True if all databases are connected (or none configured), False otherwise.
        """
        engines = self._get_db_engines_from_components()

        if not engines:
            log.debug("Database health check: no databases configured, returning True")
            return True

        for engine in engines:
            try:
                # Test the connection with a simple query
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                log.debug("Database health check: connection successful")
            except Exception as e:
                log.debug(
                    "Database health check: connection failed - %s",
                    str(e),
                )
                return False

        return True

    def is_startup_complete(self) -> bool:
        """
        Check if the app has completed its startup/initialization phase.

        Returns True if:
        - Broker is connected (or using dev_mode)
        - All configured databases are connected

        Returns False if:
        - Broker is DISCONNECTED or RECONNECTING
        - Any configured database is unreachable

        Returns:
            bool: True if startup is complete, False if still initializing
        """
        return self._is_broker_connected() and self._is_database_connected()

    def is_ready(self) -> bool:
        """
        Check if the app is ready to process messages.

        Returns True if:
        - Broker is connected (or using dev_mode)
        - All configured databases are connected

        Returns False if:
        - Broker is DISCONNECTED or RECONNECTING
        - Any configured database is unreachable

        Returns:
            bool: True if the app is ready, False otherwise
        """
        return self._is_broker_connected() and self._is_database_connected()
