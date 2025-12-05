"""Pure OAuth 2.0 protocol implementation.

This module provides stateless OAuth 2.0 flow implementations without any
caching, retry logic, or domain-specific behavior. It implements the core
OAuth 2.0 flows as defined in RFC 6749.
"""

import asyncio
import logging
import random
from typing import Any, Dict, Optional, Union

import httpx

from .utils import calculate_expires_at

logger = logging.getLogger(__name__)


class OAuth2Client:
    """Pure OAuth 2.0 protocol implementation.

    This class provides stateless OAuth 2.0 flow implementations without any
    caching, retry logic, or domain-specific behavior. Each method makes a
    single HTTP request to the token endpoint and returns the parsed response.

    All OAuth 2.0 flows follow RFC 6749 specification.
    """

    async def fetch_client_credentials_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute OAuth 2.0 Client Credentials flow (RFC 6749 Section 4.4).

        This flow is used for server-to-server authentication where the client
        acts on its own behalf rather than on behalf of a user.

        Args:
            token_url: OAuth 2.0 token endpoint URL
            client_id: OAuth 2.0 client identifier
            client_secret: OAuth 2.0 client secret
            scope: Optional space-separated list of scopes
            verify: SSL certificate verification (True, False, or path to CA bundle)
            timeout: Request timeout in seconds

        Returns:
            Token response dictionary containing:
                - access_token: The access token string
                - expires_in: Token lifetime in seconds
                - token_type: Token type (usually "Bearer")
                - scope: Granted scopes (optional)
                - expires_at: Unix timestamp when token expires (added by this method)

        Raises:
            httpx.HTTPStatusError: If the token request fails
            ValueError: If the response is missing required fields
        """
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        if scope:
            payload["scope"] = scope

        return await self._execute_token_request(
            token_url=token_url,
            payload=payload,
            verify=verify,
            timeout=timeout,
        )

    async def fetch_authorization_code_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute OAuth 2.0 Authorization Code flow (RFC 6749 Section 4.1).

        This flow is used for user-delegated authentication where the application
        acts on behalf of a user who has granted permission.

        Args:
            token_url: OAuth 2.0 token endpoint URL
            client_id: OAuth 2.0 client identifier
            client_secret: OAuth 2.0 client secret
            code: Authorization code received from authorization server
            redirect_uri: Redirect URI used in authorization request (must match)
            verify: SSL certificate verification (True, False, or path to CA bundle)
            timeout: Request timeout in seconds

        Returns:
            Token response dictionary containing:
                - access_token: The access token string
                - expires_in: Token lifetime in seconds
                - refresh_token: Refresh token for obtaining new access tokens (optional)
                - token_type: Token type (usually "Bearer")
                - scope: Granted scopes (optional)
                - expires_at: Unix timestamp when token expires (added by this method)

        Raises:
            httpx.HTTPStatusError: If the token request fails
            ValueError: If the response is missing required fields
        """
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        return await self._execute_token_request(
            token_url=token_url,
            payload=payload,
            verify=verify,
            timeout=timeout,
        )

    async def fetch_refresh_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scope: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute OAuth 2.0 Refresh Token flow (RFC 6749 Section 6).

        This flow is used to obtain a new access token using a refresh token,
        without requiring user interaction.

        Args:
            token_url: OAuth 2.0 token endpoint URL
            client_id: OAuth 2.0 client identifier
            client_secret: OAuth 2.0 client secret
            refresh_token: The refresh token
            scope: Optional space-separated list of scopes (must not exceed original grant)
            verify: SSL certificate verification (True, False, or path to CA bundle)
            timeout: Request timeout in seconds

        Returns:
            Token response dictionary containing:
                - access_token: The new access token string
                - expires_in: Token lifetime in seconds
                - refresh_token: New refresh token (optional, may be same as input)
                - token_type: Token type (usually "Bearer")
                - scope: Granted scopes (optional)
                - expires_at: Unix timestamp when token expires (added by this method)

        Raises:
            httpx.HTTPStatusError: If the token request fails
            ValueError: If the response is missing required fields
        """
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        if scope:
            payload["scope"] = scope

        return await self._execute_token_request(
            token_url=token_url,
            payload=payload,
            verify=verify,
            timeout=timeout,
        )

    async def _execute_token_request(
        self,
        token_url: str,
        payload: Dict[str, str],
        verify: Union[bool, str],
        timeout: float,
    ) -> Dict[str, Any]:
        """Execute a token request to the OAuth 2.0 token endpoint.

        This is the core HTTP operation shared by all OAuth flows.

        Args:
            token_url: OAuth 2.0 token endpoint URL
            payload: Request payload (grant-specific parameters)
            verify: SSL certificate verification
            timeout: Request timeout in seconds

        Returns:
            Token response dictionary with added expires_at field

        Raises:
            httpx.HTTPStatusError: If the token request fails
            ValueError: If the response is missing required fields
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.post(
                token_url,
                data=payload,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()

            token_data = response.json()

            # Validate response contains required fields
            if "access_token" not in token_data:
                raise ValueError(
                    f"Token response missing 'access_token' field. "
                    f"Response keys: {list(token_data.keys())}"
                )

            # Add expiration timestamp for convenience
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            token_data["expires_at"] = calculate_expires_at(expires_in)

            return token_data


class OAuth2RetryClient:
    """OAuth 2.0 client with configurable retry logic.

    This class wraps OAuth2Client and adds retry logic with exponential backoff
    for handling transient failures. Retry behavior:
    - 4xx errors (client errors): No retry - fail immediately
    - 5xx errors (server errors): Retry with exponential backoff
    - Network errors: Retry with exponential backoff
    """

    def __init__(
        self,
        max_retries: int = 0,
        backoff_base: float = 2.0,
        backoff_jitter: bool = True,
    ):
        """Initialize the retry client.

        Args:
            max_retries: Maximum number of retry attempts (0 = no retries)
            backoff_base: Base for exponential backoff (delay = base^attempt)
            backoff_jitter: Whether to add random jitter to backoff delay
        """
        self._base_client = OAuth2Client()
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_jitter = backoff_jitter

    async def fetch_client_credentials_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute Client Credentials flow with retry logic.

        See OAuth2Client.fetch_client_credentials_token for parameter details.
        """
        return await self._execute_with_retry(
            self._base_client.fetch_client_credentials_token,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            verify=verify,
            timeout=timeout,
        )

    async def fetch_authorization_code_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute Authorization Code flow with retry logic.

        See OAuth2Client.fetch_authorization_code_token for parameter details.
        """
        return await self._execute_with_retry(
            self._base_client.fetch_authorization_code_token,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            verify=verify,
            timeout=timeout,
        )

    async def fetch_refresh_token(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scope: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Execute Refresh Token flow with retry logic.

        See OAuth2Client.fetch_refresh_token for parameter details.
        """
        return await self._execute_with_retry(
            self._base_client.fetch_refresh_token,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            scope=scope,
            verify=verify,
            timeout=timeout,
        )

    async def _execute_with_retry(self, func, **kwargs) -> Dict[str, Any]:
        """Execute a function with retry logic.

        Args:
            func: Async function to execute
            **kwargs: Arguments to pass to the function

        Returns:
            Result from the function

        Raises:
            Exception: Last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                return await func(**kwargs)

            except httpx.HTTPStatusError as e:
                last_exception = e
                # Don't retry on 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    logger.error(
                        "OAuth token request failed with client error %d: %s",
                        e.response.status_code,
                        e.response.text,
                    )
                    raise

                logger.warning(
                    "OAuth token request failed with status %d (attempt %d/%d): %s",
                    e.response.status_code,
                    attempt + 1,
                    self._max_retries + 1,
                    e.response.text,
                )

            except httpx.RequestError as e:
                last_exception = e
                logger.warning(
                    "OAuth token request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                )

            except Exception as e:
                last_exception = e
                logger.error("Unexpected error during OAuth token fetch: %s", str(e))
                raise

            # Exponential backoff with optional jitter
            if attempt < self._max_retries:
                delay = self._backoff_base**attempt
                if self._backoff_jitter:
                    delay += random.uniform(0, 1)
                logger.info("Retrying OAuth token request in %.2f seconds", delay)
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "OAuth token request failed after %d attempts", self._max_retries + 1
        )
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("OAuth token request failed after all retries")