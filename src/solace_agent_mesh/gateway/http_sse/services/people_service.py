"""
Service layer for handling people-related operations, such as searching for users.
"""

import logging
from typing import Any, Dict, List, Optional

from ....common.services.identity_service import BaseIdentityService

log = logging.getLogger(__name__)

class PeopleService:
    """
    Provides methods for searching and retrieving user information,
    acting as a layer on top of the configured IdentityService.
    """

    def __init__(self, identity_service: Optional[BaseIdentityService]):
        """
        Initializes the PeopleService.

        Args:
            identity_service: An instance of a configured BaseIdentityService, or None.
        """
        self._identity_service = identity_service
        self.log_identifier = "[PeopleService]"
        log.info(
            "%s Initialized with Identity Service: %s",
            self.log_identifier,
            identity_service is not None,
        )

    async def search_for_users(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Searches for users via the identity service.

        Args:
            query: The search query string.
            limit: The maximum number of results to return.

        Returns:
            A list of user profile dictionaries.
        """
        if not self._identity_service:
            log.warning(
                "%s Search requested but no identity service is configured.",
                self.log_identifier,
            )
            return []

        if not query or len(query) < 2:
            return []

        try:
            log.debug(
                "%s Searching for users with query: '%s', limit: %d",
                self.log_identifier,
                query,
                limit,
            )
            results = await self._identity_service.search_users(query, limit)
            log.info(
                "%s Found %d users for query: '%s'",
                self.log_identifier,
                len(results),
                query,
            )
            return results
        except Exception as e:
            log.exception(
                "%s Error during user search for query '%s': %s",
                self.log_identifier,
                query,
                e,
            )
            return []
