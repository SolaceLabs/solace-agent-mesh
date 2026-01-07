"""
Manages discovered A2A gateways.
Parallel implementation to agent_registry.py for tracking gateway health and status.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple
import logging

from a2a.types import AgentCard

log = logging.getLogger(__name__)


class GatewayRegistry:
    """Stores and manages discovered Gateway cards with health tracking."""

    def __init__(self, on_gateway_added=None, on_gateway_removed=None):
        """
        Initialize the gateway registry.

        Args:
            on_gateway_added: Optional callback(agent_card) when a new gateway is discovered
            on_gateway_removed: Optional callback(gateway_id) when a gateway is removed
        """
        self._gateways: Dict[str, AgentCard] = {}
        self._last_seen: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._on_gateway_added = on_gateway_added
        self._on_gateway_removed = on_gateway_removed

    def set_on_gateway_added_callback(self, callback):
        """Sets the callback function to be called when a new gateway is added."""
        self._on_gateway_added = callback

    def set_on_gateway_removed_callback(self, callback):
        """Sets the callback function to be called when a gateway is removed."""
        self._on_gateway_removed = callback

    def add_or_update_gateway(self, agent_card: AgentCard) -> bool:
        """
        Adds a new gateway or updates an existing one.

        Args:
            agent_card: AgentCard representing a gateway (should have gateway-role extension)

        Returns:
            True if this is a new gateway, False if updating existing gateway
        """
        if not agent_card or not agent_card.name:
            log.warning("Attempted to register gateway with invalid card or missing name")
            return False

        with self._lock:
            is_new = agent_card.name not in self._gateways
            current_time = time.time()

            self._gateways[agent_card.name] = agent_card
            self._last_seen[agent_card.name] = current_time

        # Call callback OUTSIDE the lock to avoid deadlock
        if is_new and self._on_gateway_added:
            try:
                self._on_gateway_added(agent_card)
            except Exception as e:
                log.error(f"Error in gateway added callback for {agent_card.name}: {e}", exc_info=True)

        return is_new

    def get_gateway(self, gateway_id: str) -> Optional[AgentCard]:
        """
        Retrieves a gateway card by ID.

        Args:
            gateway_id: The gateway ID (matches AgentCard.name)

        Returns:
            The gateway's AgentCard or None if not found
        """
        with self._lock:
            return self._gateways.get(gateway_id)

    def get_gateway_ids(self) -> List[str]:
        """
        Returns a sorted list of discovered gateway IDs.

        Returns:
            Sorted list of gateway IDs
        """
        with self._lock:
            return sorted(list(self._gateways.keys()))

    def get_last_seen(self, gateway_id: str) -> Optional[float]:
        """
        Returns the timestamp when the gateway was last seen.

        Args:
            gateway_id: The gateway ID

        Returns:
            Unix timestamp of last heartbeat, or None if not found
        """
        with self._lock:
            return self._last_seen.get(gateway_id)

    def check_ttl_expired(self, gateway_id: str, ttl_seconds: int = 90) -> Tuple[bool, int]:
        """
        Checks if a gateway's TTL has expired (heartbeat timeout).

        Args:
            gateway_id: The gateway ID to check
            ttl_seconds: The TTL in seconds (default: 90)

        Returns:
            A tuple of (is_expired, seconds_since_last_seen)
        """
        with self._lock:
            if gateway_id not in self._last_seen:
                log.debug("Attempted to check TTL for non-existent gateway '%s'", gateway_id)
                return False, 0

            last_seen_time = self._last_seen.get(gateway_id)
            current_time = time.time()
            time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else 0

            is_expired = time_since_last_seen > ttl_seconds

            if is_expired:
                log.warning(
                    "GATEWAY HEALTH CRITICAL: Gateway '%s' TTL expired. "
                    "Last seen: %s seconds ago, TTL: %d seconds",
                    gateway_id,
                    time_since_last_seen,
                    ttl_seconds
                )

            return is_expired, time_since_last_seen

    def remove_gateway(self, gateway_id: str) -> bool:
        """
        Removes a gateway from the registry.

        Args:
            gateway_id: The gateway ID to remove

        Returns:
            True if gateway was removed, False if it didn't exist
        """
        with self._lock:
            if gateway_id in self._gateways:
                last_seen_time = self._last_seen.get(gateway_id)
                current_time = time.time()
                time_since_last_seen = int(current_time - last_seen_time) if last_seen_time else "unknown"

                log.warning(
                    "GATEWAY DE-REGISTRATION: Removing gateway '%s' from registry. "
                    "Last seen: %s seconds ago",
                    gateway_id,
                    time_since_last_seen
                )

                del self._gateways[gateway_id]
                if gateway_id in self._last_seen:
                    del self._last_seen[gateway_id]

                log.info("Gateway '%s' successfully removed from registry", gateway_id)
                removed = True
            else:
                log.debug("Attempted to remove non-existent gateway '%s' from registry", gateway_id)
                removed = False

        # Call callback OUTSIDE the lock to avoid deadlock
        if removed and self._on_gateway_removed:
            try:
                self._on_gateway_removed(gateway_id)
            except Exception as e:
                log.error(f"Error in gateway removed callback for {gateway_id}: {e}", exc_info=True)

        return removed

    def clear(self):
        """Clears all registered gateways."""
        with self._lock:
            self._gateways.clear()
            self._last_seen.clear()

    def get_gateway_type(self, gateway_id: str) -> Optional[str]:
        """
        Extract gateway type from the gateway's AgentCard extensions.

        Args:
            gateway_id: The gateway ID

        Returns:
            Gateway type (e.g., 'http_sse', 'slack', 'rest') or None if not found
        """
        card = self.get_gateway(gateway_id)
        if not card or not card.capabilities or not card.capabilities.extensions:
            return None

        for ext in card.capabilities.extensions:
            if ext.uri == "https://solace.com/a2a/extensions/sam/gateway-role":
                return ext.params.get("gateway_type")

        return None

    def get_gateway_namespace(self, gateway_id: str) -> Optional[str]:
        """
        Extract namespace from the gateway's AgentCard extensions.

        Args:
            gateway_id: The gateway ID

        Returns:
            Namespace (e.g., 'mycompany/production') or None if not found
        """
        card = self.get_gateway(gateway_id)
        if not card or not card.capabilities or not card.capabilities.extensions:
            return None

        for ext in card.capabilities.extensions:
            if ext.uri == "https://solace.com/a2a/extensions/sam/gateway-role":
                return ext.params.get("namespace")

        return None

    def get_deployment_id(self, gateway_id: str) -> Optional[str]:
        """
        Extract deployment ID from the gateway's AgentCard extensions.

        Args:
            gateway_id: The gateway ID

        Returns:
            Deployment ID (e.g., 'k8s-pod-abc123') or None if not found
        """
        card = self.get_gateway(gateway_id)
        if not card or not card.capabilities or not card.capabilities.extensions:
            return None

        for ext in card.capabilities.extensions:
            if ext.uri == "https://solace.com/a2a/extensions/sam/deployment":
                return ext.params.get("deployment_id")

        return None

    def get_healthy_gateways(self, ttl_seconds: int = 90) -> List[str]:
        """
        Get list of gateway IDs with heartbeats within the TTL.

        Args:
            ttl_seconds: The TTL threshold in seconds (default: 90)

        Returns:
            List of healthy gateway IDs
        """
        healthy = []
        for gateway_id in self.get_gateway_ids():
            is_expired, _ = self.check_ttl_expired(gateway_id, ttl_seconds)
            if not is_expired:
                healthy.append(gateway_id)
        return healthy

    def get_unhealthy_gateways(self, ttl_seconds: int = 90) -> List[str]:
        """
        Get list of gateway IDs with expired heartbeats (stale).

        Args:
            ttl_seconds: The TTL threshold in seconds (default: 90)

        Returns:
            List of unhealthy gateway IDs
        """
        unhealthy = []
        for gateway_id in self.get_gateway_ids():
            is_expired, _ = self.check_ttl_expired(gateway_id, ttl_seconds)
            if is_expired:
                unhealthy.append(gateway_id)
        return unhealthy
