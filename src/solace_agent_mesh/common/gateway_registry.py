"""
Manages discovered A2A gateways.
Extends BaseRegistry with gateway-specific extension extraction methods.
"""

from typing import List, Optional, Tuple

from a2a.types import AgentCard

from solace_agent_mesh.common.base_registry import BaseRegistry


class GatewayRegistry(BaseRegistry):
    """Stores and manages discovered Gateway cards with health tracking."""

    def __init__(self, on_gateway_added=None, on_gateway_removed=None):
        """
        Initialize the gateway registry.

        Args:
            on_gateway_added: Optional callback(agent_card) when a new gateway is discovered
            on_gateway_removed: Optional callback(gateway_id) when a gateway is removed
        """
        super().__init__("gateway", on_gateway_added, on_gateway_removed)

    def set_on_gateway_added_callback(self, callback):
        """Sets the callback function to be called when a new gateway is added."""
        self.set_on_added_callback(callback)

    def set_on_gateway_removed_callback(self, callback):
        """Sets the callback function to be called when a gateway is removed."""
        self.set_on_removed_callback(callback)

    def add_or_update_gateway(self, agent_card: AgentCard) -> bool:
        """
        Adds a new gateway or updates an existing one.

        Args:
            agent_card: AgentCard representing a gateway (should have gateway-role extension)

        Returns:
            True if this is a new gateway, False if updating existing gateway
        """
        return self.add_or_update(agent_card)

    def get_gateway(self, gateway_id: str) -> Optional[AgentCard]:
        """
        Retrieves a gateway card by ID.

        Args:
            gateway_id: The gateway ID (matches AgentCard.name)

        Returns:
            The gateway's AgentCard or None if not found
        """
        return self.get(gateway_id)

    def get_gateway_ids(self) -> List[str]:
        """
        Returns a sorted list of discovered gateway IDs.

        Returns:
            Sorted list of gateway IDs
        """
        return self.get_ids()

    def get_last_seen(self, gateway_id: str) -> Optional[float]:
        """
        Returns the timestamp when the gateway was last seen.

        Args:
            gateway_id: The gateway ID

        Returns:
            Unix timestamp of last heartbeat, or None if not found
        """
        return super().get_last_seen(gateway_id)

    def check_ttl_expired(
        self, gateway_id: str, ttl_seconds: int = 90
    ) -> Tuple[bool, int]:
        """
        Checks if a gateway's TTL has expired (heartbeat timeout).

        Args:
            gateway_id: The gateway ID to check
            ttl_seconds: The TTL in seconds (default: 90)

        Returns:
            A tuple of (is_expired, seconds_since_last_seen)
        """
        return super().check_ttl_expired(gateway_id, ttl_seconds)

    def remove_gateway(self, gateway_id: str) -> bool:
        """
        Removes a gateway from the registry.

        Args:
            gateway_id: The gateway ID to remove

        Returns:
            True if gateway was removed, False if it didn't exist
        """
        return self.remove(gateway_id)

    def get_gateway_type(self, gateway_id: str) -> Optional[str]:
        """
        Extract gateway type from the gateway's AgentCard extensions.

        Args:
            gateway_id: The gateway ID

        Returns:
            Gateway type (e.g., 'http_sse', 'slack', 'rest') or None if not found
        """
        card = self.get(gateway_id)
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
        card = self.get(gateway_id)
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
        card = self.get(gateway_id)
        if not card or not card.capabilities or not card.capabilities.extensions:
            return None

        for ext in card.capabilities.extensions:
            if ext.uri == "https://solace.com/a2a/extensions/sam/deployment":
                return ext.params.get("deployment_id")

        return None
