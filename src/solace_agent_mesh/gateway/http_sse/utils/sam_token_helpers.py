"""
SAM Access Token helper functions for auth endpoints.

This module provides shared functionality for /auth/callback and /auth/refresh
endpoints to ensure consistent validation, role resolution, and token minting.

Design Principle: Graceful Degradation
    All helper functions are designed to NEVER fail the auth flow.
    If sam_access_token cannot be minted, the flow continues with
    IdP tokens only. This ensures backward compatibility and resilience.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from solace_agent_mesh.gateway.http_sse.utils.claim_mapping import extract_token_claims

log = logging.getLogger(__name__)


def is_sam_token_enabled(component: Any) -> bool:
    """
    Check if sam_access_token feature is enabled.

    Checks the gateway-level sam_access_token config (Update 14 architecture).
    Also verifies trust_manager is available for signing.

    Args:
        component: Gateway component with config and trust_manager

    Returns:
        True if feature is enabled and trust_manager available, False otherwise
    """
    # Use get_config() which automatically looks in app_config
    # Safely check if get_config method exists
    get_config_func = getattr(component, "get_config", None)
    if get_config_func is None:
        return False

    sam_token_config = get_config_func("sam_access_token")
    if sam_token_config is None:
        return False

    # sam_token_config is a dict, use .get() not getattr()
    sam_token_enabled = sam_token_config.get("enabled", False)
    if not sam_token_enabled:
        return False

    # Also need trust_manager for signing
    trust_manager = getattr(component, "trust_manager", None)
    if trust_manager is None:
        return False

    return True


def get_sam_token_config(component: Any) -> Optional[Any]:
    """
    Get the sam_access_token configuration object.

    Args:
        component: Gateway component with config

    Returns:
        The sam_access_token config object, or None if not available
    """
    # Use get_config() which automatically looks in app_config
    return component.get_config("sam_access_token")


@dataclass
class SamTokenResult:
    """Result of sam_access_token preparation and minting."""

    token: Optional[str] = None
    user_identity: Optional[str] = None
    roles: Optional[list[str]] = None
    reason: Optional[str] = None  # Why token wasn't minted (for debugging)

    def __post_init__(self):
        if self.roles is None:
            self.roles = []

    @property
    def success(self) -> bool:
        return self.token is not None


async def prepare_and_mint_sam_token(
    component: Any,
    user_claims: Optional[dict],
    provider: str,
    context: str = "auth",
    log_identifier: str = "",
    authorization_service: Optional[Any] = None,  # Injected from route via Depends
) -> SamTokenResult:
    """
    Validate claims, resolve roles, and mint sam_access_token.

    This is the single source of truth for the entire sam_access_token
    preparation flow. Both /auth/callback and /auth/refresh use this
    function to ensure consistent validation and graceful degradation.

    Args:
        component: Gateway component with trust_manager and authorization_service
        user_claims: Claims from id_token (may be None)
        provider: OAuth2 provider name (e.g., "azure")
        context: Context string for logging ("auth_callback" or "refresh")
        log_identifier: Component's log identifier prefix for logging
        authorization_service: Authorization service (injected via Depends in route)

    Returns:
        SamTokenResult with token (if successful) or reason (if not)

    Graceful Degradation:
        This function NEVER raises exceptions. All failure cases return
        SamTokenResult with token=None and a reason string. The caller
        decides how to handle the result (typically return IdP tokens only).
    """
    log_prefix = f"{log_identifier}[{context}]" if log_identifier else f"[{context}]"

    # Step 1: Check feature flag
    if not is_sam_token_enabled(component):
        return SamTokenResult(reason="feature_disabled")

    # Step 2: Validate user_claims present
    if not user_claims:
        log.warning(
            "%s OAuth2Service did not return user_claims - "
            "sam_access_token will not be minted. "
            "Verify id_token decoding is enabled if sam_access_token is required.",
            log_prefix,
        )
        return SamTokenResult(reason="missing_user_claims")

    # Step 3: Extract user identity
    user_identity = user_claims.get("email") or user_claims.get("sub")
    if not user_identity:
        log.warning(
            "%s No user identity (email or sub) found in claims: %s - "
            "sam_access_token will not be minted",
            log_prefix,
            list(user_claims.keys()),
        )
        return SamTokenResult(reason="missing_user_identity")

    # Step 4: Resolve roles
    roles = []

    # Authorization service is passed in from route handler (injected via Depends)
    if authorization_service:
        gateway_context = {
            "gateway_id": getattr(component, "gateway_id", "unknown"),
            "idp_claims": user_claims,
        }

        # Build user_context for role providers (especially IdpClaimsRoleProvider)
        user_context = {
            "oidc_provider": provider,
            "idp_claims": user_claims,
        }

        try:
            # Check if authorization_service supports user_context parameter
            import inspect

            sig = inspect.signature(authorization_service.get_roles_for_user)
            if "user_context" in sig.parameters:
                roles = await authorization_service.get_roles_for_user(
                    user_identity=user_identity,
                    gateway_context=gateway_context,
                    user_context=user_context,
                )
            else:
                # Fallback for older authorization_service without user_context
                roles = await authorization_service.get_roles_for_user(
                    user_identity=user_identity,
                    gateway_context=gateway_context,
                )
            log.info("%s Resolved roles for '%s': %s", log_prefix, user_identity, roles)
        except Exception as e:
            log.warning(
                "%s Role resolution failed for '%s': %s - "
                "sam_access_token will not be minted",
                log_prefix,
                user_identity,
                e,
            )
            return SamTokenResult(
                user_identity=user_identity,
                reason=f"role_resolution_failed: {e}",
            )
    else:
        log.warning(
            "%s No authorization_service available - sam_access_token will have empty roles",
            log_prefix,
        )

    # Step 5: Mint the token
    try:
        trust_manager = component.trust_manager
        sam_token_config = get_sam_token_config(component)

        # Get TTL from sam_access_token config (Update 14 architecture)
        # sam_token_config is a dict, use .get() not getattr()
        ttl = sam_token_config.get("ttl_seconds", 3600)  # Default 1 hour

        # Extract selected claims from id_token (scalar values only)
        token_claims = extract_token_claims(user_claims)

        # Build custom claims for sam_access_token
        # Note: Standard JWT claims (iss, iat, exp, sub) are set by trust_manager
        custom_claims = {
            "jti": str(uuid.uuid4()),  # Unique token ID for future revocation support
            "roles": roles,
            # NOTE: scopes NOT included - resolved at request time by middleware
            "provider": provider,
            **token_claims,  # User claims from id_token (filtered by claim_mapping)
        }

        # Use the new sign_sam_access_token method which handles standard JWT claims
        sam_access_token = trust_manager.sign_sam_access_token(
            user_identity=user_identity,
            custom_claims=custom_claims,
            ttl_seconds=ttl,
        )

        log.info(
            "%s Minted sam_access_token for '%s' with "
            "roles=%s, claims=%s, TTL=%ds, size=%d bytes",
            log_prefix,
            user_identity,
            roles,
            list(token_claims.keys()),
            ttl,
            len(sam_access_token),
        )

        return SamTokenResult(
            token=sam_access_token,
            user_identity=user_identity,
            roles=roles,
        )

    except Exception as e:
        log.error(
            "%s Failed to mint sam_access_token for '%s': %s",
            log_prefix,
            user_identity,
            e,
            exc_info=True,
        )
        return SamTokenResult(
            user_identity=user_identity,
            roles=roles,
            reason=f"minting_failed: {e}",
        )
