"""
Token service for managing access tokens.

Base implementation returns IdP tokens unchanged (passthrough mode).
Enterprise can override to provide self-signed SAM tokens.
"""
import logging
from typing import Optional, Dict, Any
import httpx

log = logging.getLogger(__name__)


class TokenService:
    """
    Base token service that passes through IdP access tokens.

    This is a concrete, working implementation that maintains backwards
    compatibility. The enterprise repository can extend this to provide
    self-signed SAM tokens.
    """

    def __init__(self, component: Any):
        """
        Initialize the token service.

        Args:
            component: The gateway component instance
        """
        self.component = component
        self.log_identifier = getattr(component, 'log_identifier', 'TokenService')

    async def mint_token(
        self,
        user_claims: Dict[str, Any],
        idp_access_token: str,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Mint an access token for the user.

        Base implementation returns the IdP access token unchanged.
        Enterprise implementation returns a self-signed SAM token.

        Args:
            user_claims: Claims from id_token (sub, email, name, groups, etc.)
            idp_access_token: IdP access token (fallback if minting fails)
            task_id: Optional task ID for token binding

        Returns:
            Access token string (IdP token in base, SAM token in enterprise)
        """
        log.debug(
            "%s Base TokenService: Returning IdP access token (passthrough mode)",
            self.log_identifier
        )
        return idp_access_token

    async def get_access_token(
        self,
        idp_access_token: str,
        user_claims: Optional[Dict[str, Any]],
        task_id: Optional[str] = None,
    ) -> str:
        """
        Determine and return the appropriate access token for the user.

        Encapsulates the decision of which token to use:
        - Base implementation: always returns IdP token (passthrough)
        - Enterprise implementation: may mint and return SAM token

        The router should call this method instead of directly calling mint_token()
        and comparing results. This centralizes the token selection logic.

        Args:
            idp_access_token: IdP access token from OAuth provider
            user_claims: User claims from id_token (None if validation failed)
            task_id: Optional task ID for SAM token binding

        Returns:
            Access token string (either IdP token or SAM token)
        """
        log.debug(
            "%s Base TokenService: Returning IdP access token (passthrough mode)",
            self.log_identifier
        )
        return idp_access_token

    def validate_token(
        self,
        token: str,
        task_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an access token and return claims.

        Base implementation cannot validate IdP tokens locally (returns None).
        Enterprise implementation validates SAM token signatures.

        Args:
            token: Access token string
            task_id: Optional task ID for binding verification

        Returns:
            Verified claims dict if valid, None if cannot validate
        """
        log.debug(
            "%s Base TokenService: Cannot validate IdP tokens locally",
            self.log_identifier
        )
        return None

    def extract_token_claims(
        self,
        verified_claims: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract standardized claims from verified token.

        Args:
            verified_claims: Claims dict from validate_token()

        Returns:
            Standardized claims dict with user info and permissions
        """
        return {
            "sub": verified_claims.get("sub"),
            "email": verified_claims.get("email"),
            "name": verified_claims.get("name"),
            "roles": verified_claims.get("roles", []),
            "scopes": verified_claims.get("scopes", []),
        }

    def is_sam_token(self, token: str) -> bool:
        """
        Check if the given token is a SAM token.

        Base implementation always returns False since it only uses IdP tokens.
        Enterprise implementation can override to check SAM token signatures.

        Args:
            token: Access token string

        Returns:
            True if token is a SAM token, False otherwise
        """
        return False

    async def validate_token_with_fallback(
        self,
        token: str,
        task_id: Optional[str] = None,
        auth_service_url: Optional[str] = None,
        auth_provider: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a token with automatic fallback strategy.

        Base implementation validates IdP tokens via HTTP call to external auth service.
        Enterprise implementation validates SAM tokens locally and falls back to IdP validation.

        Args:
            token: Access token to validate
            task_id: Optional task ID for SAM token binding verification
            auth_service_url: External auth service URL (required for IdP validation)
            auth_provider: Auth provider name (required for IdP validation)

        Returns:
            User claims dict if valid, None if invalid or validation failed
        """
        # Base implementation: validate IdP token via HTTP
        if not auth_service_url or not auth_provider:
            log.warning(
                "%s Cannot validate token: auth_service_url and auth_provider required",
                self.log_identifier
            )
            return None

        try:
            # Validate token via HTTP call
            async with httpx.AsyncClient() as client:
                validation_response = await client.post(
                    f"{auth_service_url}/is_token_valid",
                    json={"provider": auth_provider},
                    headers={"Authorization": f"Bearer {token}"},
                )

            if validation_response.status_code != 200:
                log.debug(
                    "%s IdP token validation failed (HTTP %d)",
                    self.log_identifier,
                    validation_response.status_code
                )
                return None

            # Get user info via HTTP call
            async with httpx.AsyncClient() as client:
                userinfo_response = await client.get(
                    f"{auth_service_url}/user_info?provider={auth_provider}",
                    headers={"Authorization": f"Bearer {token}"},
                )

            if userinfo_response.status_code != 200:
                log.warning(
                    "%s Failed to get user info from auth service (HTTP %d)",
                    self.log_identifier,
                    userinfo_response.status_code
                )
                return None

            user_info = userinfo_response.json()
            log.debug(
                "%s IdP token validated successfully via HTTP",
                self.log_identifier
            )
            return user_info

        except httpx.RequestError as exc:
            log.error(
                "%s HTTP error during token validation: %s",
                self.log_identifier,
                exc
            )
            return None
        except Exception as exc:
            log.error(
                "%s Unexpected error during token validation: %s",
                self.log_identifier,
                exc
            )
            return None


class TokenServiceRegistry:
    """Registry for token service implementations."""

    _token_service_class: type = TokenService

    @classmethod
    def bind_token_service(cls, service_class: type) -> None:
        """Bind a custom token service implementation."""
        cls._token_service_class = service_class

    @classmethod
    def get_token_service_class(cls) -> type:
        """Get the bound token service class."""
        return cls._token_service_class
