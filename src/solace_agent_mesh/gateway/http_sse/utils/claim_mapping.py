"""
Claim mapping utilities for sam_access_token generation.

This module defines which claims from the IdP id_token are included
in the sam_access_token. Currently hardcoded but designed for easy
migration to configuration-based mapping.

To make configurable later:
    1. Move claim list to sam_access_token.included_claims config
    2. Update extract_token_claims() to read from config
"""

from typing import Any, Optional


# Claims to copy directly from id_token to sam_access_token
# These are scalar values only - NO arrays/objects to control token size
SAM_TOKEN_INCLUDED_CLAIMS: tuple[str, ...] = (
    # Core identity (required)
    "sub",
    "email",
    "name",
    # Standard OIDC claims
    "given_name",
    "family_name",
    "preferred_username",
    # Enterprise claims
    "department",
    "employee_id",
    "cost_center",
    "manager",
    "title",
    "company",
    # Azure AD specific (commonly needed)
    "oid",  # Object ID - stable user identifier
    "tid",  # Tenant ID
    "upn",  # User Principal Name
)

# Claims that should NEVER be included from id_token (even if in included list)
# These are arrays/objects that could blow up token size, plus reserved claims
SAM_TOKEN_EXCLUDED_CLAIMS: frozenset[str] = frozenset(
    {
        # Arrays/objects that blow up token size
        "groups",  # Can be 50-100+ items
        "wids",  # Azure AD role template IDs
        "xms_cc",  # Client capabilities
        "xms_ssm",  # Session management
        "amr",  # Authentication methods array
        "acrs",  # Authentication context class references
        # Reserved JWT claims (gateway sets these explicitly - never from id_token)
        "iss",  # Issuer - set by gateway
        "iat",  # Issued at - set by gateway
        "exp",  # Expiration - set by gateway
        "nbf",  # Not before
        "aud",  # Audience
        "jti",  # JWT ID - set by gateway
        # Authorization claims (gateway sets these explicitly)
        "roles",  # Set by gateway from authorization_service, NOT from IdP
        "scopes",  # Never in token - resolved at request time
    }
)


def extract_token_claims(
    user_claims: dict[str, Any],
    included_claims: Optional[tuple[str, ...]] = None,
) -> dict[str, Any]:
    """
    Extract claims from id_token for inclusion in sam_access_token.

    Only includes scalar values (strings, numbers, booleans).
    Arrays and objects are excluded to control token size.

    Args:
        user_claims: Claims from the id_token
        included_claims: Optional override for claim list (for future config support)

    Returns:
        Dict of claims to include in sam_access_token

    Example:
        >>> user_claims = {
        ...     "email": "user@example.com",
        ...     "groups": ["a", "b"],
        ...     "department": "Eng"
        ... }
        >>> extract_token_claims(user_claims)
        {"email": "user@example.com", "department": "Eng"}
    """
    claims_to_include = included_claims or SAM_TOKEN_INCLUDED_CLAIMS

    extracted = {}
    for claim_name in claims_to_include:
        if claim_name in SAM_TOKEN_EXCLUDED_CLAIMS:
            continue  # Safety check - never include blocklisted claims

        value = user_claims.get(claim_name)
        if value is None:
            continue

        # Only include scalar values (no arrays/objects)
        if isinstance(value, (str, int, float, bool)):
            extracted[claim_name] = value

    return extracted
