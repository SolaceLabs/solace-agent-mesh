"""OAuth 2.0 Client Credentials Token Manager.

This module provides OAuth 2.0 Client Credentials flow implementation for LLM authentication.
It handles token acquisition, caching, and automatic refresh with proper error handling.
"""

import asyncio
import logging
import random
import time
from typing import Any, Dict, Optional

import httpx

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
        self.max_retries = max_retries
        
        # Thread-safe token access
        self._lock = asyncio.Lock()
        
        # Token cache using existing InMemoryCache singleton
        self._cache = InMemoryCache()
        
        # Cache key for this token manager instance
        self._cache_key = f"oauth_token_{hash((token_url, client_id))}"
        
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
            
            if cached_token_data and not self._is_token_expired(cached_token_data):
                logger.debug("Using cached OAuth token")
                return cached_token_data["access_token"]
            
            # Fetch new token
            logger.info("Fetching new OAuth token from %s", self.token_url)
            token_data = await self._fetch_token()
            
            # Cache the token with TTL
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            cache_ttl = max(expires_in - self.refresh_buffer_seconds, 60)  # Min 1 minute
            
            self._cache.set(self._cache_key, token_data, ttl=cache_ttl)
            
            logger.info("OAuth token cached with TTL: %d seconds", cache_ttl)
            return token_data["access_token"]

    def _is_token_expired(self, token_data: Dict[str, Any]) -> bool:
        """Check if a token is expired or near expiry.
        
        Args:
            token_data: Token data dictionary with 'expires_at' timestamp
            
        Returns:
            True if token is expired or near expiry, False otherwise
        """
        if "expires_at" not in token_data:
            return True
            
        current_time = time.time()
        expires_at = token_data["expires_at"]
        
        # Consider token expired if it expires within the buffer time
        return current_time >= (expires_at - self.refresh_buffer_seconds)

    async def _fetch_token(self) -> Dict[str, Any]:
        """Fetch a new OAuth 2.0 access token from the token endpoint.

        Implements retry logic with exponential backoff for transient failures.

        Returns:
            Token data dictionary containing access_token, expires_in, etc.

        Raises:
            httpx.HTTPError: If HTTP request fails after all retries
            ValueError: If response is invalid or missing required fields
        """
        # Prepare request payload
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        if self.scope:
            payload["scope"] = self.scope
        
        # Configure HTTP client with SSL settings
        verify = True
        if self.ca_cert_path:
            verify = self.ca_cert_path
            
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(verify=verify) as client:
                    response = await client.post(
                        self.token_url,
                        data=payload,
                        headers=headers,
                        timeout=30.0,
                    )
                    response.raise_for_status()

                    token_data = response.json()

                    # Validate response
                    if "access_token" not in token_data:
                        raise ValueError("Token response missing 'access_token' field")

                    # Add expiration timestamp for cache management
                    expires_in = token_data.get("expires_in", 3600)
                    token_data["expires_at"] = time.time() + expires_in

                    logger.info("Successfully fetched OAuth token, expires in %d seconds", expires_in)
                    return token_data

            except httpx.HTTPStatusError as e:
                last_exception = e
                # Don't retry on 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    logger.error(
                        "OAuth token request failed with client error %d: %s",
                        e.response.status_code,
                        e.response.text
                    )
                    raise

                logger.warning(
                    "OAuth token request failed with status %d (attempt %d/%d): %s",
                    e.response.status_code,
                    attempt + 1,
                    self.max_retries + 1,
                    e.response.text
                )

            except httpx.RequestError as e:
                last_exception = e
                logger.warning(
                    "OAuth token request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except Exception as e:
                last_exception = e
                logger.error("Unexpected error during OAuth token fetch: %s", str(e))
                raise

            # Exponential backoff with jitter for retries
            if attempt < self.max_retries:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.info("Retrying OAuth token request in %.2f seconds", delay)
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error("OAuth token request failed after %d attempts", self.max_retries + 1)
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("OAuth token request failed after all retries")
