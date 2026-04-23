"""
Unit tests for the local AAD JWT validator.

Strategy:
- Generate an RSA keypair in-test.
- Sign test tokens with the private key (PyJWT RS256).
- Stub `PyJWKClient.get_signing_key_from_jwt` to return the matching
  public-key wrapper so we never touch the network.

These tests exercise the validator's classification rules in isolation;
middleware integration is covered in test_middleware_aad.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from solace_agent_mesh.shared.auth.jwt_validator import (
    AadTokenValidator,
    AadValidatorConfig,
    Outcome,
)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
APP_ID_URI = "api://22222222-2222-2222-2222-222222222222"
APP_GUID = "22222222-2222-2222-2222-222222222222"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"


@dataclass
class _SigningKeyStub:
    """Mimics the return of PyJWKClient.get_signing_key_from_jwt."""

    key: object


class _JwksStub:
    """Drop-in stub for PyJWKClient.

    `raise_error` forces get_signing_key_from_jwt to raise PyJWKClientError
    (simulating kid-not-found / JWKS-fetch-failed).
    """

    def __init__(self, public_key, raise_error: bool = False):
        self._public_key = public_key
        self._raise = raise_error

    def get_signing_key_from_jwt(self, token: str) -> _SigningKeyStub:
        if self._raise:
            raise jwt.exceptions.PyJWKClientError("kid not found in JWKS")
        return _SigningKeyStub(key=self._public_key)


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, public_key, private_pem


def _encode(
    payload: dict,
    private_pem: bytes,
    algorithm: str = "RS256",
    headers: dict | None = None,
) -> str:
    return jwt.encode(
        payload,
        private_pem,
        algorithm=algorithm,
        headers=headers or {"kid": "test-kid"},
    )


def _default_config() -> AadValidatorConfig:
    return AadValidatorConfig(tenant_id=TENANT_ID, audience=APP_ID_URI)


def _valid_user_payload(now: int | None = None) -> dict:
    now = now or int(time.time())
    return {
        "iss": ISSUER,
        "aud": APP_ID_URI,
        "sub": "user-sub-123",
        "oid": "user-oid-456",
        "tid": TENANT_ID,
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "email": "alice@contoso.com",
        "name": "Alice Example",
        "preferred_username": "alice@contoso.com",
        "ver": "2.0",
        "idtyp": "user",
    }


def _valid_app_only_payload(now: int | None = None) -> dict:
    now = now or int(time.time())
    return {
        "iss": ISSUER,
        "aud": APP_ID_URI,
        "oid": "sp-oid-789",
        "appid": APP_GUID,
        "azp": APP_GUID,
        "tid": TENANT_ID,
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "idtyp": "app",
        "ver": "2.0",
    }


# --- positive cases -------------------------------------------------------


@pytest.mark.unit
def test_valid_user_token(rsa_keys):
    _, public_key, private_pem = rsa_keys
    token = _encode(_valid_user_payload(), private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.VALID
    assert result.claims.sub == "user-sub-123"
    assert result.claims.is_service_principal is False
    assert result.claims.email == "alice@contoso.com"


@pytest.mark.unit
def test_valid_app_only_token(rsa_keys):
    _, public_key, private_pem = rsa_keys
    token = _encode(_valid_app_only_payload(), private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.VALID
    assert result.claims.appid == APP_GUID
    assert result.claims.is_service_principal is True
    assert result.claims.sub is None


@pytest.mark.unit
def test_leeway_absorbs_small_skew(rsa_keys):
    _, public_key, private_pem = rsa_keys
    now = int(time.time())
    payload = _valid_user_payload(now)
    payload["exp"] = now - 30  # 30s in the past, within 60s leeway
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.VALID


# --- audience normalisation ----------------------------------------------


@pytest.mark.unit
def test_audience_accepts_guid_form_when_configured_as_api_uri(rsa_keys):
    """CI minted token with bare-GUID aud; config uses api://<guid>. Accept."""
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload["aud"] = APP_GUID  # bare GUID
    token = _encode(payload, private_pem)
    cfg = AadValidatorConfig(tenant_id=TENANT_ID, audience=APP_ID_URI)
    v = AadTokenValidator(cfg, _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.VALID


@pytest.mark.unit
def test_audience_accepts_api_uri_form_when_configured_as_guid(rsa_keys):
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload["aud"] = APP_ID_URI
    token = _encode(payload, private_pem)
    cfg = AadValidatorConfig(tenant_id=TENANT_ID, audience=APP_GUID)
    v = AadTokenValidator(cfg, _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.VALID


# --- INVALID cases (hard 401, no fall-through) ---------------------------


@pytest.mark.unit
def test_expired_token(rsa_keys):
    _, public_key, private_pem = rsa_keys
    now = int(time.time())
    payload = _valid_user_payload(now)
    payload["exp"] = now - 3600  # well past any leeway
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_not_yet_valid(rsa_keys):
    _, public_key, private_pem = rsa_keys
    now = int(time.time())
    payload = _valid_user_payload(now)
    payload["nbf"] = now + 3600  # future nbf, past leeway
    payload["iat"] = now + 3600
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_bad_signature(rsa_keys):
    _, public_key, private_pem = rsa_keys
    # Sign with a DIFFERENT private key; JWKS returns our real public key.
    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = _encode(_valid_user_payload(), other_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_alg_none_is_invalid(rsa_keys):
    _, public_key, _ = rsa_keys
    # Build an unsigned token manually — jwt.encode allows alg=none.
    token = jwt.encode(
        _valid_user_payload(), key="", algorithm="none", headers={"kid": "test-kid"}
    )
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_hs256_key_confusion_is_invalid(rsa_keys):
    """
    Classic alg-confusion: attacker flips header alg to HS256 and signs
    with the JWKS-published public key material as the HMAC secret. Our
    RS256 whitelist must reject this.

    PyJWT refuses to sign with an asymmetric-shaped key (library-level
    defense), so we construct the token manually to simulate the attacker.
    """
    import base64
    import hashlib
    import hmac
    import json

    _, public_key, _ = rsa_keys
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(
        json.dumps({"alg": "HS256", "typ": "JWT", "kid": "test-kid"}).encode()
    )
    payload = _b64(json.dumps(_valid_user_payload()).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    token = f"{header}.{payload}.{_b64(signature)}"

    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_wrong_audience_is_invalid(rsa_keys):
    """
    Kid resolved in our JWKS — token *claims* to be for us. Audience
    mismatch must be a hard 401, not a fall-through (confused-deputy).
    """
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload["aud"] = "api://some-other-app"
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_wrong_tenant_tid_is_invalid(rsa_keys):
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload["tid"] = "99999999-9999-9999-9999-999999999999"
    # Issuer must match the configured issuer (we verify iss before tid),
    # so keep iss consistent with TENANT_ID; tid itself is the mismatch.
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


@pytest.mark.unit
def test_missing_tid_claim_is_invalid(rsa_keys):
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload.pop("tid")
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.INVALID


# --- NOT_AAD cases (fall through to next auth branch) --------------------


@pytest.mark.unit
def test_kid_not_in_jwks_is_not_aad(rsa_keys):
    _, public_key, private_pem = rsa_keys
    token = _encode(_valid_user_payload(), private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key, raise_error=True))

    result = v.validate(token)

    assert result.outcome is Outcome.NOT_AAD


@pytest.mark.unit
def test_non_jwt_shape_is_not_aad(rsa_keys):
    _, public_key, _ = rsa_keys
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate("this-is-not-a-jwt")

    assert result.outcome is Outcome.NOT_AAD


@pytest.mark.unit
def test_empty_token_is_not_aad(rsa_keys):
    _, public_key, _ = rsa_keys
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate("")

    assert result.outcome is Outcome.NOT_AAD


@pytest.mark.unit
def test_wrong_issuer_is_not_aad(rsa_keys):
    """
    AAD-signed token (kid resolves), but issuer is a different tenant /
    product (v1 sts.windows.net, different tenant). Fall through — might
    be legitimate for a different auth branch.
    """
    _, public_key, private_pem = rsa_keys
    payload = _valid_user_payload()
    payload["iss"] = "https://sts.windows.net/99999999-9999-9999-9999-999999999999/"
    token = _encode(payload, private_pem)
    v = AadTokenValidator(_default_config(), _JwksStub(public_key))

    result = v.validate(token)

    assert result.outcome is Outcome.NOT_AAD


# --- config helpers ------------------------------------------------------


@pytest.mark.unit
def test_accepted_audiences_expands_api_uri():
    cfg = AadValidatorConfig(tenant_id=TENANT_ID, audience=APP_ID_URI)
    assert cfg.accepted_audiences() == (APP_ID_URI, APP_GUID)


@pytest.mark.unit
def test_accepted_audiences_expands_bare_guid():
    cfg = AadValidatorConfig(tenant_id=TENANT_ID, audience=APP_GUID)
    assert cfg.accepted_audiences() == (APP_GUID, APP_ID_URI)


@pytest.mark.unit
def test_issuer_override_wins():
    cfg = AadValidatorConfig(
        tenant_id=TENANT_ID,
        audience=APP_ID_URI,
        issuer_override="https://sts.windows.net/tenant/",
    )
    assert cfg.resolved_issuer() == "https://sts.windows.net/tenant/"
