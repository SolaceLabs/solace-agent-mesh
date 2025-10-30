"""
OAuth Flow Proxy Handler for MCP Gateway.

This module implements OAuth 2.0 Authorization Code Flow endpoints that proxy
to SAM's OAuth2 service. It handles:
- Authorization requests (redirects to SAM OAuth2 service)
- OAuth callbacks (exchanges authorization code for tokens)
- Token refresh (refreshes expired access tokens)

The handler maintains minimal state (only OAuth state/PKCE) and delegates
all token management to SAM's OAuth2 service.
"""

import asyncio
import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse

log = logging.getLogger(__name__)


class OAuthStateManager:
    """
    Manages OAuth state and PKCE values for the authorization flow.

    This prevents CSRF attacks by validating that the authorization callback
    includes the same state value that was sent in the authorization request.
    """

    def __init__(self, ttl_seconds: int = 600):
        """
        Initialize the state manager.

        Args:
            ttl_seconds: How long state values are valid (default: 10 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._states: Dict[str, Dict[str, Any]] = {}  # state -> {created_at, data}
        self._lock = asyncio.Lock()

    async def create_state(self, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new OAuth state value.

        Args:
            data: Optional data to associate with this state

        Returns:
            Cryptographically random state string
        """
        state = secrets.token_urlsafe(32)

        async with self._lock:
            import time

            self._states[state] = {
                "created_at": time.time(),
                "data": data or {},
            }

        log.debug("Created OAuth state: %s", state[:8] + "...")
        return state

    async def validate_and_consume_state(
        self, state: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate and consume a state value (one-time use).

        Args:
            state: The state value to validate

        Returns:
            The data associated with the state, or None if invalid/expired
        """
        async with self._lock:
            import time

            state_data = self._states.get(state)

            if not state_data:
                log.warning("OAuth state not found: %s", state[:8] + "...")
                return None

            # Check if expired
            age = time.time() - state_data["created_at"]
            if age > self.ttl_seconds:
                log.warning("OAuth state expired (age: %.1fs)", age)
                del self._states[state]
                return None

            # Valid and not expired - consume it (remove)
            del self._states[state]
            log.debug("Validated and consumed OAuth state: %s", state[:8] + "...")
            return state_data["data"]

    async def cleanup_expired(self):
        """Remove expired state entries."""
        async with self._lock:
            import time

            now = time.time()
            expired = [
                state
                for state, data in self._states.items()
                if now - data["created_at"] > self.ttl_seconds
            ]

            for state in expired:
                del self._states[state]

            if expired:
                log.debug("Cleaned up %d expired OAuth states", len(expired))


class OAuthFlowHandler:
    """
    Handles OAuth 2.0 Authorization Code Flow by proxying to SAM's OAuth2 service.

    This handler does NOT implement its own OAuth server - it delegates to SAM's
    existing OAuth2 service and acts as a thin proxy layer for MCP clients.
    """

    def __init__(
        self,
        oauth_service_url: str,
        oauth_provider: str,
        callback_base_url: str,
        callback_path: str = "/oauth/callback",
    ):
        """
        Initialize the OAuth flow handler.

        Args:
            oauth_service_url: URL of SAM's OAuth2 service (e.g., "http://localhost:8050")
            oauth_provider: Provider name (e.g., "azure", "google")
            callback_base_url: Base URL for OAuth callback (e.g., "http://localhost:8000")
            callback_path: Path for OAuth callback (default: "/oauth/callback")
        """
        self.oauth_service_url = oauth_service_url.rstrip("/")
        self.oauth_provider = oauth_provider
        self.callback_base_url = callback_base_url.rstrip("/")
        self.callback_path = callback_path
        self.callback_url = f"{self.callback_base_url}{self.callback_path}"

        # State management for CSRF protection
        self.state_manager = OAuthStateManager()

        log.info(
            "OAuthFlowHandler initialized: service=%s, provider=%s, callback=%s",
            self.oauth_service_url,
            self.oauth_provider,
            self.callback_url,
        )

    async def handle_authorize(
        self, request: Request, redirect_uri: Optional[str] = None
    ) -> RedirectResponse:
        """
        Handle authorization request from MCP client.

        This redirects the user to SAM's OAuth2 service, which will then
        redirect to the identity provider (Azure AD, Google, etc.).

        Args:
            request: FastAPI request object
            redirect_uri: Optional redirect URI override

        Returns:
            Redirect response to SAM OAuth2 service
        """
        log.info("Handling OAuth authorization request")

        # Create state for CSRF protection
        state = await self.state_manager.create_state(
            {"redirect_uri": redirect_uri or self.callback_url}
        )

        # Build authorization URL for SAM's OAuth2 service
        # SAM OAuth2 service will handle the actual provider redirect
        params = {
            "provider": self.oauth_provider,
            "redirect_uri": self.callback_url,
            "state": state,
        }

        auth_url = f"{self.oauth_service_url}/login?{urlencode(params)}"

        log.debug("Redirecting to SAM OAuth2 service: %s", auth_url)
        return RedirectResponse(url=auth_url, status_code=302)

    async def handle_callback(
        self, request: Request, code: Optional[str] = None, state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle OAuth callback from SAM's OAuth2 service.

        This receives the authorization code and exchanges it for tokens
        by calling SAM's /exchange-code endpoint.

        Args:
            request: FastAPI request object
            code: Authorization code from OAuth provider
            state: State value for CSRF validation

        Returns:
            Dictionary with access_token, refresh_token, expires_in, etc.

        Raises:
            HTTPException: If validation fails or token exchange fails
        """
        log.info("Handling OAuth callback")

        # Validate required parameters
        if not code:
            log.error("OAuth callback missing authorization code")
            raise HTTPException(status_code=400, detail="Missing authorization code")

        if not state:
            log.error("OAuth callback missing state parameter")
            raise HTTPException(status_code=400, detail="Missing state parameter")

        # Validate state (CSRF protection)
        state_data = await self.state_manager.validate_and_consume_state(state)
        if not state_data:
            log.error("Invalid or expired OAuth state")
            raise HTTPException(
                status_code=400, detail="Invalid or expired state parameter"
            )

        # Exchange authorization code for tokens via SAM's OAuth2 service
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                exchange_response = await client.post(
                    f"{self.oauth_service_url}/exchange-code",
                    json={
                        "code": code,
                        "redirect_uri": self.callback_url,
                        "provider": self.oauth_provider,
                    },
                )

                if exchange_response.status_code != 200:
                    log.error(
                        "Token exchange failed with status %d: %s",
                        exchange_response.status_code,
                        exchange_response.text,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail="Failed to exchange authorization code for tokens",
                    )

                tokens = exchange_response.json()
                log.info("Successfully exchanged authorization code for tokens")
                return tokens

        except httpx.RequestError as e:
            log.error("Failed to connect to OAuth service for token exchange: %s", e)
            raise HTTPException(
                status_code=503, detail="OAuth service unavailable"
            ) from e
        except Exception as e:
            log.exception("Unexpected error during token exchange: %s", e)
            raise HTTPException(
                status_code=500, detail="Internal error during token exchange"
            ) from e

    async def handle_refresh(
        self, refresh_token: str
    ) -> Dict[str, Any]:
        """
        Handle token refresh request.

        This calls SAM's /refresh_token endpoint to get a new access token.

        Args:
            refresh_token: The refresh token to use

        Returns:
            Dictionary with new access_token, refresh_token (possibly rotated), expires_in, etc.

        Raises:
            HTTPException: If refresh fails
        """
        log.info("Handling token refresh request")

        if not refresh_token:
            log.error("Missing refresh token")
            raise HTTPException(status_code=400, detail="Missing refresh token")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                refresh_response = await client.post(
                    f"{self.oauth_service_url}/refresh_token",
                    json={
                        "refresh_token": refresh_token,
                        "provider": self.oauth_provider,
                    },
                )

                if refresh_response.status_code != 200:
                    log.error(
                        "Token refresh failed with status %d: %s",
                        refresh_response.status_code,
                        refresh_response.text,
                    )
                    raise HTTPException(
                        status_code=401, detail="Failed to refresh access token"
                    )

                tokens = refresh_response.json()
                log.info("Successfully refreshed access token")
                return tokens

        except httpx.RequestError as e:
            log.error("Failed to connect to OAuth service for token refresh: %s", e)
            raise HTTPException(
                status_code=503, detail="OAuth service unavailable"
            ) from e
        except Exception as e:
            log.exception("Unexpected error during token refresh: %s", e)
            raise HTTPException(
                status_code=500, detail="Internal error during token refresh"
            ) from e

    async def get_oauth_metadata(self) -> Dict[str, Any]:
        """
        Get OAuth metadata for MCP clients.

        Returns information about the OAuth endpoints that clients need
        to implement the authorization flow.

        Returns:
            Dictionary with authorization_url, token_url, scopes, etc.
        """
        return {
            "authorization_url": f"{self.callback_base_url}/oauth/authorize",
            "token_url": f"{self.callback_base_url}/oauth/token",
            "callback_url": self.callback_url,
            "provider": self.oauth_provider,
            "grant_types_supported": ["authorization_code", "refresh_token"],
        }
