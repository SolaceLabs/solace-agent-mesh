"""
Token service for managing access tokens.

Base implementation returns IdP tokens unchanged (passthrough mode).
Enterprise can override to provide self-signed SAM tokens.
"""
import logging
from typing import Optional, Dict, Any

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


class TokenServiceRegistry:
    """
    Registry for token service implementations.

    Allows enterprise repository to bind custom token service.
    """

    _token_service_class: type = TokenService

    @classmethod
    def bind_token_service(cls, service_class: type) -> None:
        """
        Bind a custom token service implementation.

        Args:
            service_class: Token service class (must extend TokenService)
        """
        if not issubclass(service_class, TokenService):
            raise TypeError(
                f"Token service must extend TokenService, got {service_class}"
            )

        cls._token_service_class = service_class
        log.info("TokenServiceRegistry: Bound custom token service: %s", service_class.__name__)

    @classmethod
    def get_token_service_class(cls) -> type:
        """
        Get the bound token service class.

        Returns:
            Token service class (TokenService or custom implementation)
        """
        return cls._token_service_class

    @classmethod
    def reset(cls) -> None:
        """Reset to default token service (for testing)."""
        cls._token_service_class = TokenService
