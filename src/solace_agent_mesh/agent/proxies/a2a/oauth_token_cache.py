"""
OAuth 2.0 token caching for A2A proxy authentication.

This module provides an in-memory cache for OAuth 2.0 access tokens
with automatic expiration. Tokens are cached per agent and context
(agent_card vs task) to minimize token acquisition overhead and
reduce load on authorization servers.

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

    Tokens are cached per agent and context (agent_card vs task) and
    automatically expire based on the configured cache duration.

    The context parameter allows different OAuth tokens to be cached
    separately for agent card fetching vs task invocations when
    different authentication configs are used.
    """

    def __init__(self):
        """Initialize the token cache with an empty dictionary and lock."""
        self._cache: Dict[str, CachedToken] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_cache_key(agent_name: str, context: str) -> str:
        """
        Creates a cache key from agent name and context.

        Args:
            agent_name: The name of the agent.
            context: The authentication context ("agent_card" or "task").

        Returns:
            A composite cache key string.
        """
        return f"{agent_name}:{context}"

    async def get(self, agent_name: str, context: str = "task") -> Optional[str]:
        """
        Retrieves a cached token if it exists and hasn't expired.

        Args:
            agent_name: The name of the agent to get the token for.
            context: The authentication context ("agent_card" or "task").
                     Defaults to "task" for backward compatibility.

        Returns:
            The access token if cached and valid, None otherwise.
        """
        cache_key = self._make_cache_key(agent_name, context)
        async with self._lock:
            cached = self._cache.get(cache_key)
            if not cached:
                return None

            # Check if token has expired
            if time.time() >= cached.expires_at:
                log.debug(
                    "Cached token for '%s' (context: %s) has expired. Removing from cache.",
                    agent_name,
                    context,
                )
                del self._cache[cache_key]
                return None

            log.debug(
                "Using cached OAuth token for '%s' (context: %s, expires in %.0fs)",
                agent_name,
                context,
                cached.expires_at - time.time(),
            )
            return cached.access_token

    async def set(
        self,
        agent_name: str,
        access_token: str,
        cache_duration_seconds: int,
        context: str = "task",
    ):
        """
        Caches a token with an expiration time.

        Args:
            agent_name: The name of the agent.
            access_token: The OAuth 2.0 access token.
            cache_duration_seconds: How long the token should be cached.
            context: The authentication context ("agent_card" or "task").
                     Defaults to "task" for backward compatibility.
        """
        cache_key = self._make_cache_key(agent_name, context)
        async with self._lock:
            expires_at = time.time() + cache_duration_seconds
            self._cache[cache_key] = CachedToken(
                access_token=access_token, expires_at=expires_at
            )
            log.debug(
                "Cached token for '%s' (context: %s, expires in %ds)",
                agent_name,
                context,
                cache_duration_seconds,
            )

    async def invalidate(self, agent_name: str, context: str = "task"):
        """
        Removes a token from the cache.

        Args:
            agent_name: The name of the agent.
            context: The authentication context ("agent_card" or "task").
                     Defaults to "task" for backward compatibility.
        """
        cache_key = self._make_cache_key(agent_name, context)
        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                log.info(
                    "Invalidated cached token for '%s' (context: %s)",
                    agent_name,
                    context,
                )
