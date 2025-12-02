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
        self.component = component
        self.log_identifier = getattr(component, 'log_identifier', 'TokenService')

    async def get_access_token(
        self,
        idp_access_token: str,
        user_claims: Optional[Dict[str, Any]],
    ) -> str:
        """
        Return the appropriate access token.

        Base: returns IdP token (passthrough)
        Enterprise: may mint and return SAM token
        """
        log.debug(
            "%s Base TokenService: Returning IdP access token (passthrough mode)",
            self.log_identifier
        )
        return idp_access_token

    def extract_token_claims(
        self,
        verified_claims: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract standardized claims (sub, email, name, roles, scopes)."""
        return {
            "sub": verified_claims.get("sub"),
            "email": verified_claims.get("email"),
            "name": verified_claims.get("name"),
            "roles": verified_claims.get("roles", []),
            "scopes": verified_claims.get("scopes", []),
        }

    def is_sam_token(self, token: str) -> bool:
        """
        Check if token is a SAM token.

        Base: always False (only uses IdP tokens)
        Enterprise: can override to check SAM signatures
        """
        return False

    async def validate_token_with_fallback(
        self,
        token: str,
        auth_service_url: Optional[str] = None,
        auth_provider: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate token with automatic fallback.

        Base: validates IdP tokens via HTTP to external auth service
        Enterprise: validates SAM tokens locally, falls back to IdP validation

        Returns user claims dict if valid, None otherwise.
        """
        if not auth_service_url or not auth_provider:
            log.warning(
                "%s Cannot validate token: auth_service_url and auth_provider required",
                self.log_identifier
            )
            return None

        try:
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
        cls._token_service_class = service_class

    @classmethod
    def get_token_service_class(cls) -> type:
        return cls._token_service_class
