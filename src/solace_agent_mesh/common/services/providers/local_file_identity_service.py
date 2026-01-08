"""
A simple, file-based implementation of the BaseIdentityService.
Useful for development, testing, or small-scale deployments.
"""

import logging
import json
from typing import Any, Dict, List, Optional

from ..identity_service import BaseIdentityService
from ...sac.sam_component_base import SamComponentBase


log = logging.getLogger(__name__)

class LocalFileIdentityService(BaseIdentityService):
    """
    Identity service that sources user data from a local JSON file.

    The JSON file should be a list of user profile objects.
    Example:
    [
      {
        "id": "jdoe",
        "email": "jane.doe@example.com",
        "name": "Jane Doe",
        "title": "Senior Engineer",
        "manager_id": "ssmith"
      },
      ...
    ]
    """

    def __init__(self, config: Dict[str, Any], component: Optional[SamComponentBase] = None):
        super().__init__(config, component)
        self.file_path = self.config.get("file_path")
        if not self.file_path:
            raise ValueError("LocalFileIdentityService config requires 'file_path'.")
        self.lookup_key = self.config.get("lookup_key", "id")
        self._load_data()

    def _load_data(self):
        """Loads and indexes the data from the JSON file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.all_users: List[Dict[str, Any]] = json.load(f)
            self.user_index: Dict[str, Dict[str, Any]] = {
                user.get(self.lookup_key): user
                for user in self.all_users
                if user.get(self.lookup_key)
            }
            log.info(
                "%s Loaded and indexed %d users from %s using key '%s'.",
                self.log_identifier,
                len(self.user_index),
                self.file_path,
                self.lookup_key,
            )
        except FileNotFoundError:
            log.error(
                "%s Identity file not found at: %s", self.log_identifier, self.file_path
            )
            raise
        except json.JSONDecodeError:
            log.error(
                "%s Failed to decode JSON from: %s", self.log_identifier, self.file_path
            )
            raise
        except Exception as e:
            log.exception("%s Error loading identity file: %s", self.log_identifier, e)
            raise

    async def get_user_profile(
        self, auth_claims: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Looks up a user profile from the in-memory index."""
        lookup_value = auth_claims.get(self.lookup_key)
        if not lookup_value:
            log.warning(
                "%s Cannot find lookup_key '%s' in auth_claims.",
                self.log_identifier,
                self.lookup_key,
            )
            return None

        if self.cache:
            cache_key = f"profile:{lookup_value}"
            cached_profile = self.cache.get(cache_key)
            if cached_profile:
                log.debug(
                    "%s Returning cached profile for '%s'.",
                    self.log_identifier,
                    lookup_value,
                )
                return cached_profile

        profile = self.user_index.get(lookup_value)

        if profile and self.cache:
            self.cache.set(cache_key, profile, ttl=self.cache_ttl)
            log.debug(
                "%s Stored profile for '%s' in cache.",
                self.log_identifier,
                lookup_value,
            )

        return profile

    async def search_users(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Performs a simple, case-insensitive search on user names and emails."""
        if not query:
            return []

        if self.cache:
            cache_key = f"search:{query}:{limit}"
            cached_results = self.cache.get(cache_key)
            if cached_results is not None:
                log.debug(
                    "%s Returning cached search results for '%s'.",
                    self.log_identifier,
                    query,
                )
                return cached_results

        lower_query = query.lower()
        results = []
        for user in self.all_users:
            if len(results) >= limit:
                break
            if (
                lower_query in str(user.get("name", "")).lower()
                or lower_query in str(user.get("email", "")).lower()
            ):
                results.append(
                    {
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "title": user.get("title"),
                    }
                )

        if self.cache:
            self.cache.set(cache_key, results, ttl=min(self.cache_ttl, 60))
            log.debug(
                "%s Stored search results for '%s' in cache.",
                self.log_identifier,
                query,
            )

        return results
