"""
Shared OAuth utilities for gateway adapters.

This module provides reusable OAuth validation and user info extraction
functions that can be used by any gateway adapter that needs to integrate
with SAM's OAuth2 service (enterprise feature).

The functions in this module follow the OAuth proxy pattern:
- Validate tokens against external OAuth2 service
- Retrieve user information from external OAuth2 service
- Map external user info to SAM's AuthClaims model

This allows gateway adapters to remain thin and focused on their platform-specific
concerns while delegating all OAuth logic to SAM's centralized OAuth2 service.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from .types import AuthClaims

log = logging.getLogger(__name__)


def extract_bearer_token_from_dict(
    data: Dict[str, Any],
    token_keys: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Extract Bearer token from a dictionary (e.g., headers, query params, external_input).

    This is a generic helper that can be used by adapters to extract tokens
    from various sources (HTTP headers, MCP context, custom transport metadata, etc.).

    Args:
        data: Dictionary to search for token (e.g., headers, query params, metadata)
        token_keys: List of keys to check for token. If None, uses common defaults:
                   ["Authorization", "authorization", "access_token", "token"]

    Returns:
        The extracted token string, or None if not found

    Example:
        # From HTTP headers
        token = extract_bearer_token_from_dict(
            {"Authorization": "Bearer abc123"}
        )

        # From custom MCP context
        token = extract_bearer_token_from_dict(
            mcp_context.metadata,
            token_keys=["mcp_auth_token", "access_token"]
        )
    """
    if token_keys is None:
        token_keys = ["Authorization", "authorization", "access_token", "token"]

    for key in token_keys:
        value = data.get(key)
        if value:
            # Handle "Bearer <token>" format
            if isinstance(value, str):
                if value.startswith("Bearer "):
                    return value[7:]  # Strip "Bearer " prefix
                elif value.startswith("bearer "):
                    return value[7:]  # Handle lowercase
                else:
                    # Assume it's already a raw token
                    return value

    return None


async def validate_token_with_oauth_service(
    auth_service_url: str,
    auth_provider: str,
    access_token: str,
    timeout_seconds: float = 5.0,
) -> bool:
    """
    Validate an access token against SAM's OAuth2 service.

    This function calls the external OAuth2 service's /is_token_valid endpoint
    to verify that the provided access token is valid.

    Args:
        auth_service_url: Base URL of the OAuth2 service (e.g., "http://localhost:8050")
        auth_provider: Provider name configured in OAuth2 service (e.g., "azure", "google")
        access_token: The access token to validate
        timeout_seconds: Request timeout (default: 5 seconds)

    Returns:
        True if token is valid, False otherwise

    Raises:
        httpx.RequestError: If unable to connect to OAuth service
        httpx.HTTPStatusError: If OAuth service returns unexpected error
    """
    if not auth_service_url or not access_token:
        log.warning("Missing auth_service_url or access_token for validation")
        return False

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{auth_service_url}/is_token_valid",
                json={"provider": auth_provider},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                log.debug("Token validation successful")
                return True
            else:
                log.warning(
                    "Token validation failed with status %d: %s",
                    response.status_code,
                    response.text,
                )
                return False

    except httpx.TimeoutException:
        log.error("Token validation timed out after %s seconds", timeout_seconds)
        return False
    except httpx.RequestError as e:
        log.error("Failed to connect to OAuth service: %s", e)
        raise
    except Exception as e:
        log.exception("Unexpected error during token validation: %s", e)
        return False


async def get_user_info_from_oauth_service(
    auth_service_url: str,
    auth_provider: str,
    access_token: str,
    timeout_seconds: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve user information from SAM's OAuth2 service.

    This function calls the external OAuth2 service's /user_info endpoint
    to get the authenticated user's claims (sub, email, name, etc.).

    Args:
        auth_service_url: Base URL of the OAuth2 service (e.g., "http://localhost:8050")
        auth_provider: Provider name configured in OAuth2 service (e.g., "azure", "google")
        access_token: The validated access token
        timeout_seconds: Request timeout (default: 5 seconds)

    Returns:
        Dictionary containing user claims, or None if request failed

    Raises:
        httpx.RequestError: If unable to connect to OAuth service
        httpx.HTTPStatusError: If OAuth service returns unexpected error
    """
    if not auth_service_url or not access_token:
        log.warning("Missing auth_service_url or access_token for user info")
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(
                f"{auth_service_url}/user_info",
                params={"provider": auth_provider},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                user_info = response.json()
                log.debug("Retrieved user info: %s", user_info.keys())
                return user_info
            else:
                log.warning(
                    "Failed to get user info with status %d: %s",
                    response.status_code,
                    response.text,
                )
                return None

    except httpx.TimeoutException:
        log.error("User info request timed out after %s seconds", timeout_seconds)
        return None
    except httpx.RequestError as e:
        log.error("Failed to connect to OAuth service for user info: %s", e)
        raise
    except Exception as e:
        log.exception("Unexpected error retrieving user info: %s", e)
        return None


def extract_user_identifier(user_info: Dict[str, Any]) -> Optional[str]:
    """
    Extract the primary user identifier from OAuth user info.

    Tries multiple standard OAuth/OIDC claim names in order of preference.
    This handles variations across different identity providers (Azure AD, Google, etc.).

    Args:
        user_info: Dictionary of user claims from OAuth provider

    Returns:
        The user's primary identifier, or None if not found
    """
    # Try standard OIDC/OAuth claims in order of preference
    identifier = (
        user_info.get("sub")  # Standard OIDC subject claim
        or user_info.get("email")  # Email is common primary identifier
        or user_info.get("preferred_username")  # Azure AD
        or user_info.get("upn")  # Azure AD User Principal Name
        or user_info.get("unique_name")  # Azure AD
        or user_info.get("oid")  # Azure AD Object ID
        or user_info.get("client_id")  # For service accounts
        or user_info.get("username")  # Generic username
        or user_info.get("user_id")  # Custom claim
        or user_info.get("azp")  # Authorized party (for client credentials)
        or user_info.get("name")  # Fallback to display name
    )

    # Validate the identifier
    if identifier and isinstance(identifier, str):
        # Handle edge cases where provider returns "Unknown" or similar
        if identifier.lower() in ["unknown", "null", "none", ""]:
            log.warning(
                "OAuth provider returned invalid user identifier: %s", identifier
            )
            return None
        return identifier

    return None


def create_auth_claims_from_user_info(
    user_info: Dict[str, Any],
    access_token: Optional[str] = None,
    source: str = "oauth",
) -> Optional[AuthClaims]:
    """
    Create an AuthClaims object from OAuth user info.

    Maps OAuth/OIDC user claims to SAM's AuthClaims model, which is used
    by the generic gateway framework for authentication and authorization.

    Args:
        user_info: Dictionary of user claims from OAuth provider
        access_token: The validated access token (optional, for token_type="bearer")
        source: Authentication source identifier (default: "oauth")

    Returns:
        AuthClaims object, or None if no valid user identifier found
    """
    user_id = extract_user_identifier(user_info)

    if not user_id:
        log.error("Could not extract user identifier from user_info: %s", user_info)
        return None

    # Extract email (try multiple claim names)
    email = (
        user_info.get("email")
        or user_info.get("preferred_username")
        or user_info.get("upn")
        or user_id  # Fallback to user_id if it looks like an email
    )

    # Create AuthClaims
    claims = AuthClaims(
        id=user_id,
        email=email if email and "@" in email else None,
        token=access_token,
        token_type="bearer" if access_token else None,
        source=source,
        raw_context=user_info,  # Store full user_info for enterprise enrichment
    )

    log.debug("Created AuthClaims for user: %s (source: %s)", user_id, source)
    return claims


async def validate_and_create_auth_claims(
    auth_service_url: str,
    auth_provider: str,
    access_token: str,
    source: str = "oauth",
    timeout_seconds: float = 5.0,
) -> Optional[AuthClaims]:
    """
    Convenience function that validates a token and creates AuthClaims in one step.

    This is the most common pattern for gateway adapters:
    1. Validate the token
    2. Get user info
    3. Create AuthClaims

    Args:
        auth_service_url: Base URL of the OAuth2 service
        auth_provider: Provider name configured in OAuth2 service
        access_token: The access token to validate
        source: Authentication source identifier (default: "oauth")
        timeout_seconds: Request timeout (default: 5 seconds)

    Returns:
        AuthClaims object if validation succeeds, None otherwise

    Example:
        claims = await validate_and_create_auth_claims(
            auth_service_url="http://localhost:8050",
            auth_provider="azure",
            access_token=token_from_client,
            source="mcp"
        )
    """
    # Step 1: Validate token
    is_valid = await validate_token_with_oauth_service(
        auth_service_url, auth_provider, access_token, timeout_seconds
    )

    if not is_valid:
        log.warning("Token validation failed, cannot create auth claims")
        return None

    # Step 2: Get user info
    user_info = await get_user_info_from_oauth_service(
        auth_service_url, auth_provider, access_token, timeout_seconds
    )

    if not user_info:
        log.error("Failed to retrieve user info after successful token validation")
        return None

    # Step 3: Create AuthClaims
    claims = create_auth_claims_from_user_info(user_info, access_token, source)

    return claims
