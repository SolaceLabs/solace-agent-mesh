"""
High-value tests for the synthetic auth path.

Each test exercises a real failure mode that, if it regressed silently, would
either let an attacker authenticate as the synthetic principal or break the
synthetic monitor entirely. Lower-value tests (constructor shape, getter
plumbing) are intentionally omitted.

JWTs are signed with a real RSA keypair generated per-test-session and the
JWKS client is monkeypatched to return that keypair's public key. This
exercises PyJWT's actual signature/claim validation rather than asserting
against mocks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from solace_agent_mesh.shared.auth import synthetic
from solace_agent_mesh.shared.auth.synthetic import (
    SyntheticAuthConfig,
    SyntheticTokenInvalid,
    SyntheticTokenNotApplicable,
    is_endpoint_allowed,
    validate_synthetic_token,
)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
AUDIENCE = "api://solace-chat-test"
ROLE = "Synthetics.Smoke"
DATADOG_APPID = "22222222-2222-2222-2222-222222222222"
OTHER_APPID = "99999999-9999-9999-9999-999999999999"
ISSUER_V1 = f"https://sts.windows.net/{TENANT_ID}/"
ISSUER_V2 = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def config():
    return SyntheticAuthConfig(
        enabled=True,
        tenant_id=TENANT_ID,
        audience=AUDIENCE,
        role_name=ROLE,
        appid_allowlist=frozenset({DATADOG_APPID}),
        endpoint_allowlist=(
            ("GET", __import__("re").compile(r"^/api/v1/sessions$")),
            ("POST", __import__("re").compile(r"^/api/v1/messages$")),
        ),
        roles=("SyntheticMonitor",),
        issuers=(ISSUER_V1, ISSUER_V2),
        jwks_uri=f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys",
    )


@pytest.fixture(autouse=True)
def patched_jwks(monkeypatch, rsa_keypair):
    """Replace the live JWKS fetch with one that returns our test public key."""
    _, public_key = rsa_keypair

    @dataclass
    class _StubSigningKey:
        key: object

    class _StubJWKSClient:
        def get_signing_key_from_jwt(self, _token):
            return _StubSigningKey(key=public_key)

    monkeypatch.setattr(synthetic, "_get_jwks_client", lambda _uri: _StubJWKSClient())
    # Also clear any module-level cache so a previous test doesn't leak.
    monkeypatch.setattr(synthetic, "_jwks_clients", {})


def _encode(claims: dict, private_key, algorithm: str = "RS256") -> str:
    if algorithm == "none":
        return jwt.encode(claims, key="", algorithm="none")
    return jwt.encode(claims, key=private_key, algorithm=algorithm)


def _valid_claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "iss": ISSUER_V2,
        "aud": AUDIENCE,
        "tid": TENANT_ID,
        "appid": DATADOG_APPID,
        "azp": DATADOG_APPID,
        # appidacr "1" = client secret auth (the production case for Datadog).
        "appidacr": "1",
        "roles": [ROLE],
        "iat": now,
        "nbf": now,
        "exp": now + 300,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Discriminator: NotApplicable (caller falls through) vs Invalid (caller rejects)
# ---------------------------------------------------------------------------


def test_garbage_token_is_not_applicable(config):
    """Non-JWT input must not be treated as a failed synthetic — fall through."""
    with pytest.raises(SyntheticTokenNotApplicable):
        validate_synthetic_token("not-a-jwt", config)


def test_token_without_synthetic_markers_is_not_applicable(config, rsa_keypair):
    """A real-user IdP token without our role/appid must fall through to IdP path."""
    private_key, _ = rsa_keypair
    token = _encode(
        _valid_claims(appid=OTHER_APPID, azp=OTHER_APPID, roles=["User.Read"]),
        private_key,
    )
    with pytest.raises(SyntheticTokenNotApplicable):
        validate_synthetic_token(token, config)


def test_synthetic_shaped_token_with_bad_signature_is_invalid(config, rsa_keypair):
    """Tokens claiming to be synthetic but signed with the wrong key are hard-rejected."""
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _encode(_valid_claims(), wrong_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


# ---------------------------------------------------------------------------
# Validation rejections (security-critical paths)
# ---------------------------------------------------------------------------


def test_alg_none_is_rejected(config, rsa_keypair):
    """Algorithm-none attack — PyJWT must refuse because RS256 is the only allowed alg."""
    token = _encode(_valid_claims(), private_key=None, algorithm="none")
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_wrong_audience_is_rejected(config, rsa_keypair):
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(aud="api://wrong-app"), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_wrong_issuer_is_rejected(config, rsa_keypair):
    private_key, _ = rsa_keypair
    token = _encode(
        _valid_claims(iss="https://login.microsoftonline.com/other/v2.0"),
        private_key,
    )
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_wrong_tenant_is_rejected(config, rsa_keypair):
    """Cross-tenant attack — issuer matched but tid claim is from another tenant."""
    private_key, _ = rsa_keypair
    # Use the right issuer but a `tid` from a different tenant.
    token = _encode(_valid_claims(tid="00000000-0000-0000-0000-000000000000"), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_appid_not_in_allowlist_is_rejected(config, rsa_keypair):
    """Token with the right role but a different appid (e.g. another tenant app) — reject."""
    private_key, _ = rsa_keypair
    # roles still trips the "looks synthetic" peek so we get a hard reject, not fall-through.
    token = _encode(_valid_claims(appid=OTHER_APPID, azp=OTHER_APPID), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_extra_roles_is_rejected(config, rsa_keypair):
    """Strict equality on roles — no privilege creep via additional roles."""
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(roles=[ROLE, "Admin"]), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_missing_role_is_rejected(config, rsa_keypair):
    """A correct-appid token with no synthetic role must fail validation."""
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(roles=[]), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


@pytest.mark.parametrize("user_claim", ["preferred_username", "upn", "unique_name"])
def test_user_distinguishing_claim_present_is_rejected(config, rsa_keypair, user_claim):
    """User-distinguishing claims must reject — they only appear in user-context tokens.

    Note: `sub` and `oid` are NOT in this list. Entra includes them in every
    app-only token to identify the service principal — see
    test_sub_and_oid_are_accepted for the positive case.
    """
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(**{user_claim: "real.user@example.com"}), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_sub_and_oid_are_accepted(config, rsa_keypair):
    """`sub` and `oid` identify the service principal in app-only tokens; never reject."""
    private_key, _ = rsa_keypair
    sp_oid = "b6f8278f-0861-41c1-bc68-a933d5afdc00"
    token = _encode(_valid_claims(sub=sp_oid, oid=sp_oid), private_key)
    claims = validate_synthetic_token(token, config)
    assert claims["sub"] == sp_oid
    assert claims["oid"] == sp_oid


def test_v1_issuer_is_accepted(config, rsa_keypair):
    """Entra defaults to v1 (sts.windows.net) for client_credentials when the
    resource hasn't opted into v2 via accessTokenAcceptedVersion. Must accept it."""
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(iss=ISSUER_V1), private_key)
    claims = validate_synthetic_token(token, config)
    assert claims["iss"] == ISSUER_V1


def test_appidacr_zero_is_rejected(config, rsa_keypair):
    """Public-client tokens (no client secret/cert) must be hard-rejected."""
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(appidacr="0"), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_appidacr_missing_is_rejected(config, rsa_keypair):
    """Tokens without `appidacr` must reject — we cannot confirm the auth context."""
    private_key, _ = rsa_keypair
    claims = _valid_claims()
    del claims["appidacr"]
    token = _encode(claims, private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


def test_expired_token_is_rejected(config, rsa_keypair):
    private_key, _ = rsa_keypair
    now = int(time.time())
    # Beyond the 60s leeway.
    token = _encode(_valid_claims(exp=now - 600, iat=now - 1200, nbf=now - 1200), private_key)
    with pytest.raises(SyntheticTokenInvalid):
        validate_synthetic_token(token, config)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_token_returns_claims(config, rsa_keypair):
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(), private_key)
    claims = validate_synthetic_token(token, config)
    assert claims["appid"] == DATADOG_APPID
    assert claims["roles"] == [ROLE]
    assert claims["tid"] == TENANT_ID


# ---------------------------------------------------------------------------
# Config loading — fail closed
# ---------------------------------------------------------------------------


class _StubComponent:
    def __init__(self, **config):
        self._config = config

    def get_config(self, key, default=None):
        return self._config.get(key, default)


_FULL_CONFIG = {
    "synthetic_auth_enabled": True,
    "synthetic_auth_tenant_id": TENANT_ID,
    "synthetic_auth_audience": AUDIENCE,
    "synthetic_auth_role_name": ROLE,
    "synthetic_auth_appid_allowlist": [DATADOG_APPID],
    "synthetic_auth_endpoint_allowlist": [
        {"method": "GET", "path": r"^/api/v1/sessions$"},
        {"method": "POST", "path": r"^/api/v1/messages$"},
    ],
    "synthetic_auth_roles": ["SyntheticMonitor"],
}


def test_config_disabled_by_default():
    assert SyntheticAuthConfig.from_component(_StubComponent()) is None


def test_config_enabled_with_full_settings_loads():
    config = SyntheticAuthConfig.from_component(_StubComponent(**_FULL_CONFIG))
    assert config is not None
    assert config.role_name == ROLE
    assert DATADOG_APPID in config.appid_allowlist


@pytest.mark.parametrize(
    "missing",
    [
        "synthetic_auth_tenant_id",
        "synthetic_auth_audience",
        "synthetic_auth_role_name",
    ],
)
def test_config_missing_required_field_disables(missing):
    """Missing required field must fail closed — synthetic auth stays off."""
    cfg = {**_FULL_CONFIG, missing: ""}
    assert SyntheticAuthConfig.from_component(_StubComponent(**cfg)) is None


def test_config_empty_appid_allowlist_disables():
    """An empty allowlist would accept *any* tenant app with the role — must fail closed."""
    cfg = {**_FULL_CONFIG, "synthetic_auth_appid_allowlist": []}
    assert SyntheticAuthConfig.from_component(_StubComponent(**cfg)) is None


def test_config_empty_endpoint_allowlist_disables():
    """An empty endpoint allowlist would deny everything — pointless to enable."""
    cfg = {**_FULL_CONFIG, "synthetic_auth_endpoint_allowlist": []}
    assert SyntheticAuthConfig.from_component(_StubComponent(**cfg)) is None


def test_config_empty_roles_disables():
    """No roles means MS Graph fallback (which 404s on synthetic identity) — fail closed."""
    cfg = {**_FULL_CONFIG, "synthetic_auth_roles": []}
    assert SyntheticAuthConfig.from_component(_StubComponent(**cfg)) is None


def test_user_state_carries_configured_roles(config, rsa_keypair):
    """The synthetic principal must expose roles so AuthorizationService skips MS Graph."""
    from solace_agent_mesh.shared.auth.synthetic import build_synthetic_user_state
    private_key, _ = rsa_keypair
    token = _encode(_valid_claims(), private_key)
    claims = validate_synthetic_token(token, config)
    state = build_synthetic_user_state(claims, config.roles)
    assert state["roles"] == ["SyntheticMonitor"]
    assert state["is_synthetic"] is True
    assert state["id"] == "synthetic-monitor"


def test_config_default_issuers_target_entra_public_cloud():
    """By default, issuers/jwks point at the Entra public-cloud URLs."""
    config = SyntheticAuthConfig.from_component(_StubComponent(**_FULL_CONFIG))
    assert config is not None
    assert config.issuers == (
        f"https://sts.windows.net/{TENANT_ID}/",
        f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    )
    assert config.jwks_uri == (
        f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    )


def test_config_issuer_and_jwks_overrides_apply():
    """Sovereign clouds / non-public-cloud Entra: override issuers + JWKS URL."""
    cfg = {
        **_FULL_CONFIG,
        "synthetic_auth_issuers": [
            f"https://login.microsoftonline.us/{TENANT_ID}/v2.0",
        ],
        "synthetic_auth_jwks_uri": (
            f"https://login.microsoftonline.us/{TENANT_ID}/discovery/v2.0/keys"
        ),
    }
    config = SyntheticAuthConfig.from_component(_StubComponent(**cfg))
    assert config is not None
    assert config.issuers == (
        f"https://login.microsoftonline.us/{TENANT_ID}/v2.0",
    )
    assert config.jwks_uri == (
        f"https://login.microsoftonline.us/{TENANT_ID}/discovery/v2.0/keys"
    )


# ---------------------------------------------------------------------------
# Endpoint allowlist (default deny is the security boundary)
# ---------------------------------------------------------------------------


def test_endpoint_allowlist_allows_matching_method_and_path(config):
    assert is_endpoint_allowed("GET", "/api/v1/sessions", config) is True
    assert is_endpoint_allowed("POST", "/api/v1/messages", config) is True


def test_endpoint_allowlist_rejects_method_mismatch(config):
    """POST to a GET-only path must be denied even if the path regex matches."""
    assert is_endpoint_allowed("POST", "/api/v1/sessions", config) is False


def test_endpoint_allowlist_rejects_unmatched_path(config):
    assert is_endpoint_allowed("GET", "/api/v1/admin/users", config) is False


def test_endpoint_allowlist_rejects_path_extension(config):
    """Regex anchors prevent /api/v1/sessions/secret-thing from sneaking in."""
    assert is_endpoint_allowed("GET", "/api/v1/sessions/secret", config) is False


def test_endpoint_allowlist_method_is_case_insensitive(config):
    assert is_endpoint_allowed("get", "/api/v1/sessions", config) is True
