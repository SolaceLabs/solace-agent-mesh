"""
Base registry for tracking A2A cards with health monitoring.
Provides common functionality for AgentRegistry and GatewayRegistry.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple, Callable
import logging

from a2a.types import AgentCard

log = logging.getLogger(__name__)


class BaseRegistry:
    """
    Base class for storing and managing discovered A2A cards with health tracking.

    Provides thread-safe storage, TTL-based health monitoring, and lifecycle callbacks.
    Subclasses should provide entity-specific method aliases for backward compatibility.
    """

    def __init__(
        self,
        entity_name: str,
        on_added: Optional[Callable[[AgentCard], None]] = None,
        on_removed: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the registry.

        Args:
            entity_name: Type of entity being tracked (e.g., "agent" or "gateway")
            on_added: Optional callback(card) when a new entity is discovered
            on_removed: Optional callback(item_id) when an entity is removed
        """
        self._entity_name = entity_name
        self._items: Dict[str, AgentCard] = {}
        self._last_seen: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._on_added = on_added
        self._on_removed = on_removed

    def set_on_added_callback(self, callback: Callable[[AgentCard], None]):
        """Sets the callback function to be called when a new entity is added."""
        self._on_added = callback

    def set_on_removed_callback(self, callback: Callable[[str], None]):
        """Sets the callback function to be called when an entity is removed."""
        self._on_removed = callback

    def add_or_update(self, card: AgentCard) -> bool:
        """
        Adds a new entity or updates an existing one.

        Args:
            card: AgentCard representing the entity

        Returns:
            True if this is a new entity, False if updating existing or if card is invalid
        """
        if not card or not card.name:
            log.warning(
                "Attempted to register %s with invalid card or missing name",
                self._entity_name,
            )
            return False

        with self._lock:
            is_new = card.name not in self._items
            current_time = time.time()

            self._items[card.name] = card
            self._last_seen[card.name] = current_time

        if is_new and self._on_added:
            try:
                self._on_added(card)
            except Exception as e:
                log.error(
                    "Error in %s added callback for %s: %s",
                    self._entity_name,
                    card.name,
                    e,
                    exc_info=True,
                )

        return is_new

    def get(self, item_id: str) -> Optional[AgentCard]:
        """
        Retrieves a card by ID.

        Args:
            item_id: The entity ID (matches AgentCard.name)

        Returns:
            The entity's AgentCard or None if not found
        """
        with self._lock:
            return self._items.get(item_id)

    def get_ids(self) -> List[str]:
        """
        Returns a sorted list of discovered entity IDs.

        Returns:
            Sorted list of entity IDs
        """
        with self._lock:
            return sorted(list(self._items.keys()))

    def get_last_seen(self, item_id: str) -> Optional[float]:
        """
        Returns the timestamp when the entity was last seen.

        Args:
            item_id: The entity ID

        Returns:
            Unix timestamp of last heartbeat, or None if not found
        """
        with self._lock:
            return self._last_seen.get(item_id)

    def check_ttl_expired(
        self, item_id: str, ttl_seconds: int = 90
    ) -> Tuple[bool, int]:
        """
        Checks if an entity's TTL has expired (heartbeat timeout).

        Args:
            item_id: The entity ID to check
            ttl_seconds: The TTL in seconds (default: 90)

        Returns:
            A tuple of (is_expired, seconds_since_last_seen)
        """
        with self._lock:
            if item_id not in self._last_seen:
                log.debug(
                    "Attempted to check TTL for non-existent %s '%s'",
                    self._entity_name,
                    item_id,
                )
                return False, 0

            last_seen_time = self._last_seen.get(item_id)
            current_time = time.time()
            time_since_last_seen = (
                int(current_time - last_seen_time) if last_seen_time else 0
            )

            is_expired = time_since_last_seen > ttl_seconds

            if is_expired:
                log.warning(
                    "%s HEALTH CRITICAL: %s '%s' TTL expired. "
                    "Last seen: %s seconds ago, TTL: %d seconds",
                    self._entity_name.upper(),
                    self._entity_name.capitalize(),
                    item_id,
                    time_since_last_seen,
                    ttl_seconds,
                )

            return is_expired, time_since_last_seen

    def remove(self, item_id: str) -> bool:
        """
        Removes an entity from the registry.

        Args:
            item_id: The entity ID to remove

        Returns:
            True if entity was removed, False if it didn't exist
        """
        with self._lock:
            if item_id not in self._items:
                log.debug(
                    "Attempted to remove non-existent %s '%s' from registry",
                    self._entity_name,
                    item_id,
                )
                return False

            last_seen_time = self._last_seen.get(item_id)
            current_time = time.time()
            time_since_last_seen = (
                int(current_time - last_seen_time) if last_seen_time else "unknown"
            )

            log.info(
                "%s '%s' removed from registry (last seen: %s seconds ago)",
                self._entity_name.capitalize(),
                item_id,
                time_since_last_seen,
            )

            del self._items[item_id]
            if item_id in self._last_seen:
                del self._last_seen[item_id]

        if self._on_removed:
            try:
                self._on_removed(item_id)
            except Exception as e:
                log.error(
                    "Error in %s removed callback for %s: %s",
                    self._entity_name,
                    item_id,
                    e,
                    exc_info=True,
                )

        return True

    def clear(self):
        """Clears all registered entities."""
        with self._lock:
            count = len(self._items)
            self._items.clear()
            self._last_seen.clear()
        if count > 0:
            log.info("Cleared %d %s(s) from registry", count, self._entity_name)

    def __len__(self) -> int:
        """Returns the number of entities in the registry."""
        with self._lock:
            return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        """Check if an entity is in the registry."""
        with self._lock:
            return item_id in self._items

    def __bool__(self) -> bool:
        """
        Always returns True since the registry object exists.

        This prevents empty registries from being treated as falsy,
        allowing `if registry is None` checks to work correctly.
        """
        return True
