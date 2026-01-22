"""
OAuth2 authentication middleware for both gateways and services.

Provides reusable OAuth2 token validation middleware that works with any
component that has OAuth configuration.
"""

import httpx
import logging
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse
from fastapi import status

from solace_agent_mesh.gateway.http_sse.utils.sam_token_helpers import (
    is_sam_token_enabled,
)

log = logging.getLogger(__name__)


def _extract_access_token(request: FastAPIRequest) -> str:
    """
    Extract access token from request (header, session, or query param).

    Args:
        request: FastAPI request object

    Returns:
        Access token string if found, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    try:
        if "access_token" in request.session:
            log.debug("AuthMiddleware: Found token in session.")
            return request.session["access_token"]
    except AssertionError:
        log.debug("AuthMiddleware: Could not access request.session.")

    if "token" in request.query_params:
        return request.query_params["token"]

    return None


async def _validate_token(
    auth_service_url: str, auth_provider: str, access_token: str
) -> bool:
    """
    Validate token with external OAuth service.

    Args:
        auth_service_url: Base URL of OAuth service
        auth_provider: OAuth provider name (azure, google, okta, etc.)
        access_token: Bearer token to validate

    Returns:
        True if token is valid, False otherwise
    """
    async with httpx.AsyncClient() as client:
        validation_response = await client.post(
            f"{auth_service_url}/is_token_valid",
            json={"provider": auth_provider},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return validation_response.status_code == 200


async def _get_user_info(
    auth_service_url: str, auth_provider: str, access_token: str
) -> dict:
    """
    Get user info from OAuth service.

    Args:
        auth_service_url: Base URL of OAuth service
        auth_provider: OAuth provider name
        access_token: Bearer token

    Returns:
        User info dictionary if successful, None otherwise
    """
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            f"{auth_service_url}/user_info?provider={auth_provider}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.status_code != 200:
        return None

    return userinfo_response.json()


def _extract_user_identifier(user_info: dict) -> str:
    """Extract user identifier from OAuth user info."""
    user_identifier = (
        user_info.get("sub")
        or user_info.get("client_id")
        or user_info.get("username")
        or user_info.get("oid")
        or user_info.get("preferred_username")
        or user_info.get("upn")
        or user_info.get("unique_name")
        or user_info.get("email")
        or user_info.get("name")
        or user_info.get("azp")
        or user_info.get("user_id")
    )

    if user_identifier and user_identifier.lower() == "unknown":
        log.warning("AuthMiddleware: IDP returned 'Unknown' as user identifier. Using fallback.")
        return "sam_dev_user"

    return user_identifier


def _extract_user_details(user_info: dict, user_identifier: str) -> tuple:
    """Extract email and display name from OAuth user info."""
    email_from_auth = (
        user_info.get("email")
        or user_info.get("preferred_username")
        or user_info.get("upn")
        or user_identifier
    )

    display_name = (
        user_info.get("name")
        or user_info.get("given_name", "") + " " + user_info.get("family_name", "")
        or user_info.get("preferred_username")
        or user_identifier
    ).strip()

    return email_from_auth, display_name


async def _create_user_state(
    user_identifier: str, email_from_auth: str, display_name: str
) -> dict:
    """Create user state dictionary from OAuth info."""
    final_user_id = user_identifier or email_from_auth or "sam_dev_user"
    if not final_user_id or final_user_id.lower() in ["unknown", "null", "none", ""]:
        final_user_id = "sam_dev_user"
        log.warning("AuthMiddleware: Had to use fallback user ID due to invalid identifier")

    return {
        "id": final_user_id,
        "email": email_from_auth or final_user_id,
        "name": display_name or final_user_id,
        "authenticated": True,
        "auth_method": "oidc",
    }


def create_oauth_middleware(component):
    """
    Create OAuth2 authentication middleware for any component (gateway or service).

    Works with any component that has:
    - external_auth_service_url config
    - external_auth_provider config
    - use_authorization config

    Args:
        component: Component instance (gateway or service)

    Returns:
        AuthMiddleware class configured for the component
    """

    class AuthMiddleware:
        def __init__(self, app, component):
            self.app = app
            self.component = component

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            request = FastAPIRequest(scope, receive)

            if not request.url.path.startswith("/api"):
                await self.app(scope, receive, send)
                return

            skip_paths = [
                "/api/v1/config",
                "/api/v1/auth/callback",
                "/api/v1/auth/tool/callback",
                "/api/v1/auth/login",
                "/api/v1/auth/refresh",
                "/api/v1/csrf-token",
                "/api/v1/platform/mcp/oauth/callback",
                "/api/v1/platform/health",
                "/health",
            ]

            if any(request.url.path.startswith(path) for path in skip_paths):
                await self.app(scope, receive, send)
                return

            if request.method == "OPTIONS":
                await self.app(scope, receive, send)
                return

            use_auth = self.component.get_config("frontend_use_authorization", False)

            if use_auth:
                if await self._handle_authenticated_request(request, scope, receive, send):
                    return
            else:
                request.state.user = {
                    "id": "sam_dev_user",
                    "name": "Sam Dev User",
                    "email": "sam@dev.local",
                    "authenticated": True,
                    "auth_method": "development",
                }
                log.debug("AuthMiddleware: Set development user (frontend_use_authorization=false)")

            await self.app(scope, receive, send)

        async def _handle_authenticated_request(self, request, scope, receive, send) -> bool:
            """
            Handle authentication for a request.

            Supports both sam_access_token (new) and IdP access_token (existing)
            for backwards compatibility. Tries sam_access_token validation first
            (fast, local JWT verification), then falls back to IdP validation.

            Returns:
                True if an error response was sent (caller should not continue),
                False if authentication succeeded (caller should proceed with app).
            """
            access_token = _extract_access_token(request)

            if not access_token:
                log.warning("AuthMiddleware: No access token found. Returning 401.")
                response = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Not authenticated",
                        "error_type": "authentication_required",
                    },
                )
                await response(scope, receive, send)
                return True

            # Try sam_access_token validation first (fast, local JWT verification)
            # This is an enterprise feature - trust_manager and authorization_service
            # are set on the component by enterprise initialization code.
            # If not present, we safely skip to IdP validation.
            trust_manager = getattr(self.component, "trust_manager", None)
            authorization_service = getattr(self.component, "authorization_service", None)

            if trust_manager and is_sam_token_enabled(self.component):
                try:
                    # Validate as sam_access_token using trust_manager (no task_id binding)
                    claims = trust_manager.verify_user_claims_without_task_binding(access_token)
                    user_identifier = claims.get("sam_user_id")
                    # Success! It's a valid sam_access_token
                    # Extract roles from token, resolve scopes at request time
                    roles = claims.get("roles", [])
                    scopes = []
                    if authorization_service:
                        # Use existing get_scopes_for_user with roles param to skip role lookup
                        scopes = await authorization_service.get_scopes_for_user(
                            user_identity=user_identifier,
                            gateway_context={},
                            roles=roles,
                        )
                    else:
                        log.warning(
                            "AuthMiddleware: Access token is enabled and provided but authorization service not available. "
                            "Cannot resolve scopes for sam_access_token."
                        )

                    request.state.user = {
                        "id": user_identifier,
                        "email": claims.get("email", user_identifier),
                        "name": claims.get("name", user_identifier),
                        "authenticated": True,
                        "auth_method": "sam_access_token",
                        "roles": roles,
                        "scopes": scopes,
                    }
                    log.debug(
                        f"AuthMiddleware: Validated sam_access_token for user '{user_identifier}' "
                        f"with roles={roles}, resolved scopes={len(scopes)}"
                    )
                    return False  # Success - continue to app

                except Exception as e:
                    # Not a sam_access_token or verification failed
                    # Fall through to IdP token validation below
                    log.error(f"AuthMiddleware: Token is not a valid sam_access_token: {e}")

            # EXISTING: Fall back to IdP token validation (unchanged logic)
            auth_service_url = getattr(self.component, "external_auth_service_url", None)
            auth_provider = getattr(self.component, "external_auth_provider", "generic")

            if not auth_service_url:
                log.error("Auth service URL not configured.")
                response = JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Auth service not configured"},
                )
                await response(scope, receive, send)
                return True

            if not await _validate_token(auth_service_url, auth_provider, access_token):
                log.warning("AuthMiddleware: Token validation failed")
                response = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token", "error_type": "invalid_token"},
                )
                await response(scope, receive, send)
                return True

            user_info = await _get_user_info(auth_service_url, auth_provider, access_token)
            if not user_info:
                log.warning("AuthMiddleware: Failed to get user info")
                response = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Could not retrieve user info"},
                )
                await response(scope, receive, send)
                return True

            user_identifier = _extract_user_identifier(user_info)
            email_from_auth, display_name = _extract_user_details(user_info, user_identifier)

            request.state.user = await _create_user_state(
                user_identifier, email_from_auth, display_name
            )

            log.debug(f"AuthMiddleware: Authenticated user: {request.state.user['id']}")
            return False

    return AuthMiddleware


__all__ = [
    "create_oauth_middleware",
    "_extract_access_token",
    "_validate_token",
    "_get_user_info",
]
