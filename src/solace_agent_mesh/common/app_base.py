"""Base App class for all SAM applications with broker health checks."""

import logging

from solace_ai_connector.common.messaging.solace_messaging import ConnectionStatus
from solace_ai_connector.common.monitoring import Monitoring
from solace_ai_connector.flow.app import App

log = logging.getLogger(__name__)


class SamAppBase(App):
    """
    Base class for all SAM applications.

    Extends solace-ai-connector's App class with broker connection health checks
    for the is_startup_complete() and is_ready() methods.

    When using dev_mode (DevBroker), health checks always return True since
    the DevBroker doesn't have real connection issues to monitor.

    When using a real Solace broker, health checks return True only when
    the broker connection status is CONNECTED.
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

    def is_startup_complete(self) -> bool:
        """
        Check if the app has completed its startup/initialization phase.

        Returns True if:
        - Using dev_mode (DevBroker is always "connected")
        - Using real Solace broker and connection status is CONNECTED

        Returns False if:
        - Using real Solace broker and connection status is DISCONNECTED or RECONNECTING

        Returns:
            bool: True if startup is complete, False if still initializing
        """
        return self._is_broker_connected()

    def is_ready(self) -> bool:
        """
        Check if the app is ready to process messages.

        Returns True if:
        - Using dev_mode (DevBroker is always "connected")
        - Using real Solace broker and connection status is CONNECTED

        Returns False if:
        - Using real Solace broker and connection status is DISCONNECTED or RECONNECTING

        Returns:
            bool: True if the app is ready, False otherwise
        """
        return self._is_broker_connected()
