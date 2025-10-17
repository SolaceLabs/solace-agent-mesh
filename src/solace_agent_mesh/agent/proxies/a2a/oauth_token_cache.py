"""
OAuth 2.0 token caching for A2A proxy authentication.

This module provides an in-memory cache for OAuth 2.0 access tokens
with automatic expiration. Tokens are cached per agent to minimize
token acquisition overhead and reduce load on authorization servers.

The cache is thread-safe using asyncio.Lock and implements lazy
expiration (tokens are checked for expiration on retrieval).
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional

from solace_ai_connector.common.log import log


@dataclass
class CachedToken:
    """Represents a cached OAuth token with expiration."""

    access_token: str
    expires_at: float  # Unix timestamp when token expires (time.time() + cache_duration)


class OAuth2TokenCache:
    """
    Thread-safe in-memory cache for OAuth 2.0 access tokens.

    Tokens are cached per agent and automatically expire based on
    the configured cache duration.
    """

    def __init__(self):
        """Initialize the token cache with an empty dictionary and lock."""
        self._cache: Dict[str, CachedToken] = {}
        self._lock = asyncio.Lock()

    async def get(self, agent_name: str) -> Optional[str]:
        """
        Retrieves a cached token if it exists and hasn't expired.

        Args:
            agent_name: The name of the agent to get the token for.

        Returns:
            The access token if cached and valid, None otherwise.
        """
        async with self._lock:
            cached = self._cache.get(agent_name)
            if not cached:
                return None

            # Check if token has expired
            if time.time() >= cached.expires_at:
                log.debug(
                    "Cached token for '%s' has expired. Removing from cache.",
                    agent_name,
                )
                del self._cache[agent_name]
                return None

            log.debug(
                "Using cached OAuth token for '%s' (expires in %.0fs)",
                agent_name,
                cached.expires_at - time.time(),
            )
            return cached.access_token

    async def set(
        self, agent_name: str, access_token: str, cache_duration_seconds: int
    ):
        """
        Caches a token with an expiration time.

        Args:
            agent_name: The name of the agent.
            access_token: The OAuth 2.0 access token.
            cache_duration_seconds: How long the token should be cached.
        """
        async with self._lock:
            expires_at = time.time() + cache_duration_seconds
            self._cache[agent_name] = CachedToken(
                access_token=access_token, expires_at=expires_at
            )
            log.debug(
                "Cached token for '%s' (expires in %ds)",
                agent_name,
                cache_duration_seconds,
            )

    async def invalidate(self, agent_name: str):
        """
        Removes a token from the cache.

        Args:
            agent_name: The name of the agent.
        """
        async with self._lock:
            if agent_name in self._cache:
                del self._cache[agent_name]
                log.info("Invalidated cached token for '%s'", agent_name)
