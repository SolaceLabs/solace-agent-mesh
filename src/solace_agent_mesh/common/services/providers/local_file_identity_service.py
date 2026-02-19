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

    def __init__(
        self, config: Dict[str, Any], component: Optional[SamComponentBase] = None
    ):
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
        """
        Performs a case-insensitive search matching the start of first or last names, or email prefix.

        Examples:
        - "ed" matches "Edward Smith" (first name starts with "ed")
        - "smi" matches "Edward Smith" (last name starts with "smi")
        - "edward.s" matches "edward.smith@example.com" (email starts with "edward.s")
        """
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

            # Get user fields
            name = str(user.get("name", "")).lower()
            email = str(user.get("email", "")).lower()

            # Split name into parts (first, last, middle names)
            name_parts = name.split()

            # Check if query matches:
            # 1. Start of any name part (first, last, middle)
            # 2. Start of email (before @)
            match = False

            # Match start of any name part
            for part in name_parts:
                if part.startswith(lower_query):
                    match = True
                    break

            # Match start of email (before @)
            if not match and email:
                email_prefix = email.split("@")[0] if "@" in email else email
                if email_prefix.startswith(lower_query):
                    match = True

            if match:
                results.append(
                    {
                        "id": user.get("id"),
                        "displayName": user.get("name"),
                        "workEmail": user.get("email"),
                        "jobTitle": user.get("title"),
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
