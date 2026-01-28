"""Abstract interface for gateway authentication.

This module defines the auth interface that enterprise implementations
must follow. The community repo provides only the interface - the actual
OAuth implementation lives in solace-agent-mesh-enterprise.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AuthHandler(ABC):
    """
    Base interface for authentication handlers.

    Enterprise implementations (e.g., SAMOAuth2Handler) implement this interface
    to provide OAuth2, API key, or other authentication mechanisms.

    The handler is responsible for:
    - Initiating authorization flows (OAuth, API key setup, etc.)
    - Handling callbacks from auth providers
    - Providing auth headers for outgoing requests
    - Managing authentication state
    """

    @abstractmethod
    async def handle_authorize(self, request: Any) -> Any:
        """
        Initiate authorization flow.

        For OAuth2, this typically redirects to the OAuth2 service.
        For API keys, this might return a setup page.

        Args:
            request: Framework-specific request object (FastAPI Request, etc.)

        Returns:
            Framework-specific redirect response or dict with redirect_url.
            For dict responses, should contain:
            - redirect_url: str - URL to redirect to
            - status_code: int - HTTP status code (default 302)

        Raises:
            Exception: If authorization initiation fails
        """
        pass

    @abstractmethod
    async def handle_callback(self, request: Any) -> Dict[str, Any]:
        """
        Handle OAuth callback or auth completion.

        For OAuth2, this exchanges authorization codes for tokens.
        For API keys, this might process key submission.

        Args:
            request: Framework-specific request object with callback params
                    (e.g., code, state for OAuth2)

        Returns:
            Dictionary with callback result:
            - success: bool - Whether auth succeeded
            - message: str - Human-readable status message
            - (optional) redirect_url: str - URL to redirect to after callback

        Raises:
            ValueError: If callback parameters are invalid
            Exception: If auth exchange/completion fails
        """
        pass

    @abstractmethod
    async def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for outgoing API requests.

        Returns headers that should be included in HTTP requests to
        authenticate with external services.

        Returns:
            Dictionary of HTTP headers (e.g., {"Authorization": "Bearer ..."})
            Returns empty dict {} if not authenticated or no headers needed.

        Examples:
            OAuth2: {"Authorization": "Bearer eyJhbGc..."}
            API Key: {"X-API-Key": "sk-..."}
            Basic Auth: {"Authorization": "Basic dXNlcjpwYXNz"}
        """
        pass

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """
        Check if currently authenticated.

        Returns:
            True if authenticated with valid credentials, False otherwise.

        Notes:
            This should check if credentials are present AND valid.
            For token-based auth, this might check token expiration.
        """
        pass
