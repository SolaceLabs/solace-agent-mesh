"""OAuth 2.0 Client Credentials Token Manager.

This module provides OAuth 2.0 Client Credentials flow implementation for LLM authentication.
It handles token acquisition, caching, and automatic refresh with proper error handling.
"""

import asyncio
import logging
from typing import Optional

from solace_agent_mesh.common.oauth import OAuth2RetryClient, is_token_expired
from solace_agent_mesh.common.utils.in_memory_cache import InMemoryCache

logger = logging.getLogger(__name__)


class OAuth2ClientCredentialsTokenManager:
    """Manages OAuth 2.0 Client Credentials tokens with caching and automatic refresh.
    
    This class implements the OAuth 2.0 Client Credentials flow as defined in RFC 6749.
    It provides thread-safe token management with automatic refresh before expiration
    and integrates with the existing InMemoryCache for token storage.
    
    Attributes:
        token_url: OAuth 2.0 token endpoint URL
        client_id: OAuth client identifier
        client_secret: OAuth client secret
        scope: OAuth scope (optional)
        ca_cert_path: Path to custom CA certificate (optional)
        refresh_buffer_seconds: Seconds before expiry to refresh token
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        refresh_buffer_seconds: int = 300,
        max_retries: int = 3,
    ):
        """Initialize the OAuth2 Client Credentials Token Manager.
        
        Args:
            token_url: OAuth 2.0 token endpoint URL
            client_id: OAuth client identifier
            client_secret: OAuth client secret
            scope: OAuth scope (optional, space-separated string)
            ca_cert_path: Path to custom CA certificate file (optional)
            refresh_buffer_seconds: Seconds before actual expiry to refresh token
            max_retries: Maximum number of retry attempts for token requests
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not token_url:
            raise ValueError("token_url is required")
        if not client_id:
            raise ValueError("client_id is required")
        if not client_secret:
            raise ValueError("client_secret is required")
        if refresh_buffer_seconds < 0:
            raise ValueError("refresh_buffer_seconds must be non-negative")
            
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.ca_cert_path = ca_cert_path
        self.refresh_buffer_seconds = refresh_buffer_seconds

        # Thread-safe token access
        self._lock = asyncio.Lock()

        # Token cache using existing InMemoryCache singleton
        self._cache = InMemoryCache()

        # Cache key for this token manager instance
        self._cache_key = f"oauth_token_{hash((token_url, client_id))}"

        # OAuth client with retry logic
        self._oauth_client = OAuth2RetryClient(max_retries=max_retries)

        logger.info(
            "OAuth2ClientCredentialsTokenManager initialized for endpoint: %s",
            token_url
        )

    async def get_token(self) -> str:
        """Get a valid OAuth 2.0 access token.
        
        This method checks the cache first and returns a cached token if it's still valid.
        If no token exists or the token is expired/near expiry, it fetches a new token.
        
        Returns:
            Valid OAuth 2.0 access token
            
        Raises:
            httpx.HTTPError: If token request fails
            ValueError: If token response is invalid
        """
        async with self._lock:
            # Check if we have a cached token
            cached_token_data = self._cache.get(self._cache_key)

            if cached_token_data and not is_token_expired(
                cached_token_data["expires_at"], buffer_seconds=self.refresh_buffer_seconds
            ):
                logger.debug("Using cached OAuth token")
                return cached_token_data["access_token"]

            # Fetch new token using common OAuth client
            logger.info("Fetching new OAuth token from %s", self.token_url)
            verify = self.ca_cert_path if self.ca_cert_path else True
            token_data = await self._oauth_client.fetch_client_credentials_token(
                token_url=self.token_url,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scope=self.scope,
                verify=verify,
                timeout=30.0,
            )
            
            # Cache the token with TTL
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            cache_ttl = max(expires_in - self.refresh_buffer_seconds, 60)  # Min 1 minute
            
            self._cache.set(self._cache_key, token_data, ttl=cache_ttl)
            
            logger.info("OAuth token cached with TTL: %d seconds", cache_ttl)
            return token_data["access_token"]
