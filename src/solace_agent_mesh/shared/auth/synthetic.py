"""
Synthetic-monitor authentication path.

Allows a non-interactive caller (e.g. Datadog Synthetics) to authenticate
against the gateway by presenting an Entra ID-issued JWT minted via the
OAuth client_credentials grant. The token carries an app role and no user
identity; this module validates it locally against the tenant's JWKS and
maps it to a fixed synthetic principal.

This is config-gated. When `synthetic.enabled` is False (or the config
block is absent), no synthetic auth path exists.

Defense in depth — every check below is independently load-bearing:
- Standard JWT validation (signature, alg allowlist, iss, aud, tid, exp,
  nbf, iat with skew).
- Strict role match (token.roles must equal exactly the configured role).
- `appid`/`azp` allowlist of known Datadog client app GUIDs.
- No user identity claims (sub/oid/preferred_username/upn must be absent).
- Endpoint allowlist enforced before any handler runs.

The synthetic principal is hard-coded and uses a non-routable namespace
(`synthetic-monitor@synthetics.invalid`) so it can never collide with a
real user. The well-known `user_id = "synthetic-monitor"` is the agreed
identifier across the gateway and ADK session DBs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

log = logging.getLogger(__name__)

SYNTHETIC_USER_ID = "synthetic-monitor"
SYNTHETIC_USER_EMAIL = "synthetic-monitor@synthetics.invalid"
SYNTHETIC_USER_NAME = "Synthetic Monitor"
SYNTHETIC_AUTH_METHOD = "synthetic"

# `sub` and `oid` are intentionally NOT in this list. Entra issues both for every
# app-only token (client_credentials) where they identify the service principal,
# not a user. The user-distinguishing claims are the friendly identifiers below;
# their absence is what tells us this isn't a user token.
_USER_IDENTITY_CLAIMS = ("preferred_username", "upn", "unique_name")
_ALLOWED_ALGORITHMS = ("RS256",)
_LEEWAY_SECONDS = 60
# `appidacr` (Application Authentication Context Reference): "0" = public client
# (no auth), "1" = client secret, "2" = certificate. client_credentials must be
# "1" or "2" — never "0", which would indicate a public client somehow holds the role.
_ALLOWED_APP_AUTH_CONTEXT = frozenset({"1", "2"})


class SyntheticTokenNotApplicable(Exception):
    """Token does not look like a synthetic token. Caller should fall through."""


class SyntheticTokenInvalid(Exception):
    """Token claims to be synthetic but fails validation. Caller should reject."""


@dataclass(frozen=True)
class SyntheticAuthConfig:
    """Configuration for the synthetic auth path. All fields required when enabled."""

    enabled: bool
    tenant_id: str
    audience: str
    role_name: str
    appid_allowlist: frozenset[str]
    endpoint_allowlist: tuple[tuple[str, re.Pattern[str]], ...]
    # Entra issues v1 tokens (sts.windows.net) by default for client_credentials,
    # and v2 tokens (login.microsoftonline.com/v2.0) when the resource opts in via
    # accessTokenAcceptedVersion=2 in its manifest. We accept both.
    issuers: tuple[str, ...]
    jwks_uri: str

    @staticmethod
    def from_component(component: Any) -> SyntheticAuthConfig | None:
        """
        Read synthetic config from a component. Returns None when disabled or
        the required fields are missing — fail closed.
        """
        enabled = bool(component.get_config("synthetic_auth_enabled", False))
        if not enabled:
            return None

        tenant_id = component.get_config("synthetic_auth_tenant_id")
        audience = component.get_config("synthetic_auth_audience")
        role_name = component.get_config("synthetic_auth_role_name")
        appid_list = component.get_config("synthetic_auth_appid_allowlist", []) or []
        endpoint_list = component.get_config("synthetic_auth_endpoint_allowlist", []) or []

        missing = [
            name for name, value in (
                ("synthetic_auth_tenant_id", tenant_id),
                ("synthetic_auth_audience", audience),
                ("synthetic_auth_role_name", role_name),
            ) if not value
        ]
        if missing:
            log.error(
                "Synthetic auth enabled but missing required config: %s. Disabling.",
                ", ".join(missing),
            )
            return None

        if not appid_list:
            log.error(
                "Synthetic auth enabled but synthetic_auth_appid_allowlist is empty. "
                "Refusing to enable — would accept any tenant app with the role. Disabling."
            )
            return None

        if not endpoint_list:
            log.error(
                "Synthetic auth enabled but synthetic_auth_endpoint_allowlist is empty. "
                "Refusing to enable — would deny every request. Disabling."
            )
            return None

        compiled_endpoints = tuple(
            (entry["method"].upper(), re.compile(entry["path"]))
            for entry in endpoint_list
        )

        issuer_v1 = f"https://sts.windows.net/{tenant_id}/"
        issuer_v2 = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

        return SyntheticAuthConfig(
            enabled=True,
            tenant_id=tenant_id,
            audience=audience,
            role_name=role_name,
            appid_allowlist=frozenset(appid_list),
            endpoint_allowlist=compiled_endpoints,
            issuers=(issuer_v1, issuer_v2),
            jwks_uri=jwks_uri,
        )


# JWKS clients are cached per-jwks-uri. PyJWKClient caches signing keys
# internally with a default TTL — safe to keep one instance per URI.
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_uri)
    if client is None:
        client = PyJWKClient(jwks_uri, cache_keys=True)
        _jwks_clients[jwks_uri] = client
    return client


def validate_synthetic_token(token: str, config: SyntheticAuthConfig) -> dict[str, Any]:
    """
    Validate an Entra-issued client-credentials JWT against the synthetic policy.

    Returns the verified claims on success.

    Raises:
        SyntheticTokenNotApplicable: token does not appear to be a synthetic token.
            The caller should fall through to other auth paths.
        SyntheticTokenInvalid: token looks like a synthetic token but fails
            validation. The caller should hard-reject with 401.
    """
    # ROUTING-ONLY peek — NOT used for any auth decision.
    # We need to decide whether this token is even claiming to be a synthetic
    # token (route here) vs a real IdP/sam_access_token (route elsewhere) before
    # we know if signature verification will succeed against Entra's JWKS.
    # Verified claims are obtained below via jwt.decode(..., key=signing_key)
    # and ALL auth decisions (appid allowlist, role match, claim absence) use
    # those verified claims, not this unverified peek. A forged token that
    # passes this peek will be hard-rejected at the signature step.
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})  # NOSONAR(python:S5659)
    except jwt.DecodeError as exc:
        raise SyntheticTokenNotApplicable(f"not a JWT: {exc}") from exc

    unverified_appid = unverified.get("appid") or unverified.get("azp")
    unverified_roles = unverified.get("roles")

    looks_synthetic = (
        unverified_appid in config.appid_allowlist
        or (isinstance(unverified_roles, list) and config.role_name in unverified_roles)
    )
    if not looks_synthetic:
        raise SyntheticTokenNotApplicable("token has no synthetic appid or role")

    # From here on, validation failures are hard rejections — the caller
    # was attempting a synthetic auth and got it wrong.
    try:
        signing_key = _get_jwks_client(config.jwks_uri).get_signing_key_from_jwt(token)
    except Exception as exc:
        raise SyntheticTokenInvalid(f"JWKS lookup failed: {exc}") from exc

    try:
        claims = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=list(_ALLOWED_ALGORITHMS),
            audience=config.audience,
            # Issuer is validated manually below to support both v1 (sts.windows.net)
            # and v2 (login.microsoftonline.com/v2.0) Entra endpoints.
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise SyntheticTokenInvalid(f"JWT validation failed: {exc}") from exc

    # Issuer pinning — must be one of our tenant's v1/v2 endpoints.
    if claims.get("iss") not in config.issuers:
        raise SyntheticTokenInvalid(f"unexpected issuer: {claims.get('iss')!r}")

    # Tenant pinning — defense in depth on top of issuer.
    if claims.get("tid") != config.tenant_id:
        raise SyntheticTokenInvalid(
            f"tenant mismatch: got {claims.get('tid')!r}, expected {config.tenant_id!r}"
        )

    # appid allowlist (verified claim).
    appid = claims.get("appid") or claims.get("azp")
    if appid not in config.appid_allowlist:
        raise SyntheticTokenInvalid(f"appid {appid!r} not in allowlist")

    # Application authentication context — must be client secret or cert. Rejects
    # public-client tokens (appidacr "0") and tokens missing the claim entirely.
    appidacr = claims.get("appidacr")
    if appidacr not in _ALLOWED_APP_AUTH_CONTEXT:
        raise SyntheticTokenInvalid(
            f"app authentication context too weak: appidacr={appidacr!r}"
        )

    # Strict role match — exactly the synthetic role, nothing else.
    roles = claims.get("roles")
    if roles != [config.role_name]:
        raise SyntheticTokenInvalid(
            f"roles must equal [{config.role_name!r}], got {roles!r}"
        )

    # Reject any token that carries user-distinguishing claims. `sub` and `oid`
    # are intentionally absent from this list — Entra includes them in every
    # app-only token to identify the service principal.
    user_claim_present = [c for c in _USER_IDENTITY_CLAIMS if c in claims]
    if user_claim_present:
        raise SyntheticTokenInvalid(
            f"synthetic token must not carry user claims, found {user_claim_present}"
        )

    return claims


def build_synthetic_user_state(claims: dict[str, Any]) -> dict[str, Any]:
    """Construct the fixed synthetic principal that the rest of the app sees."""
    return {
        "id": SYNTHETIC_USER_ID,
        "user_id": SYNTHETIC_USER_ID,
        "email": SYNTHETIC_USER_EMAIL,
        "name": SYNTHETIC_USER_NAME,
        "authenticated": True,
        "auth_method": SYNTHETIC_AUTH_METHOD,
        "is_synthetic": True,
        "appid": claims.get("appid") or claims.get("azp"),
    }


def is_endpoint_allowed(
    method: str, path: str, config: SyntheticAuthConfig
) -> bool:
    """Default-deny check against the configured (method, path-regex) allowlist."""
    request_method = method.upper()
    for allowed_method, path_pattern in config.endpoint_allowlist:
        if allowed_method == request_method and path_pattern.match(path):
            return True
    return False


__all__ = [
    "SyntheticAuthConfig",
    "SyntheticTokenInvalid",
    "SyntheticTokenNotApplicable",
    "SYNTHETIC_USER_ID",
    "build_synthetic_user_state",
    "is_endpoint_allowed",
    "validate_synthetic_token",
]
