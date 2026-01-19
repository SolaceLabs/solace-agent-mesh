"""
Defines the abstract base class and factory for creating Identity Service providers.
"""

import logging
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import importlib.metadata as metadata

from ..utils.in_memory_cache import InMemoryCache
from ..sac.sam_component_base import SamComponentBase

log = logging.getLogger(__name__)

class BaseIdentityService(ABC):
    """Abstract base class for all Identity Service providers."""

    def __init__(self, config: Dict[str, Any], component: Optional[SamComponentBase] = None):
        """
        Initializes the service with its specific configuration block.

        Args:
            config: The dictionary of configuration parameters for this provider.
        """
        self.config = config
        self.component = component
        self.log_identifier = f"[{self.__class__.__name__}]"
        self.cache_ttl = config.get("cache_ttl_seconds", 3600)
        self.cache = InMemoryCache() if self.cache_ttl > 0 else None
        log.info(
            "%s Initialized. Cache TTL: %d seconds.",
            self.log_identifier,
            self.cache_ttl,
        )

    @abstractmethod
    async def get_user_profile(
        self, auth_claims: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches additional profile details for an already authenticated user.

        Args:
            auth_claims: A dictionary of claims from the primary authentication
                         system (e.g., decoded JWT, session data). It's guaranteed
                         to contain at least a primary user identifier.
            kwargs: Optional additional parameters for provider-specific logic.

        Returns:
            A dictionary containing additional user details (e.g., title, manager)
            or None if the user is not found in this identity system.
        """
        pass

    @abstractmethod
    async def search_users(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches for users based on a query string for autocomplete.

        Args:
            query: The partial name or email to search for.
            limit: The maximum number of results to return.

        Returns:
            A list of dictionaries, each containing basic user info
            (e.g., id, displayName, workEmail, jobTitle).
        """
        pass


def create_identity_service(
    config: Optional[Dict[str, Any]],
    component: Optional[SamComponentBase] = None,
) -> Optional[BaseIdentityService]:
    """
    Factory function to create an instance of an Identity Service provider
    based on the provided configuration.
    """
    if not config:
        log.info(
            "[IdentityFactory] No 'identity_service' configuration found. Skipping creation."
        )
        return None

    provider_type = config.get("type")
    if not provider_type:
        raise ValueError("Identity service config must contain a 'type' key.")

    log.info(
        f"[IdentityFactory] Attempting to create identity service of type: {provider_type}"
    )

    if provider_type == "local_file":
        from .providers.local_file_identity_service import LocalFileIdentityService

        return LocalFileIdentityService(config, component)

    else:
        try:
            entry_points = metadata.entry_points(group="solace_agent_mesh.plugins")
            provider_info_entry = next(
                (ep for ep in entry_points if ep.name == provider_type), None
            )

            if not provider_info_entry:
                raise ValueError(
                    f"No plugin provider found for type '{provider_type}' under the 'solace_agent_mesh.plugins' entry point."
                )

            provider_info = provider_info_entry.load()
            class_path = provider_info.get("class_path")
            if not class_path:
                raise ValueError(
                    f"Plugin '{provider_type}' is missing 'class_path' in its info dictionary."
                )

            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)

            if not issubclass(provider_class, BaseIdentityService):
                raise TypeError(
                    f"Provider class '{class_path}' does not inherit from BaseIdentityService."
                )

            log.info(f"Successfully loaded identity provider plugin: {provider_type}")
            return provider_class(config, component)
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            log.exception(
                f"[IdentityFactory] Failed to load identity provider plugin '{provider_type}'. "
                "Ensure the plugin is installed and the entry point is correct."
            )
            raise ValueError(f"Could not load identity provider plugin: {e}") from e
