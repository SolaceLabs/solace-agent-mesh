"""
Local JWT validation via JWKS.

First supported issuer is Azure Active Directory (AAD). The module is named
generically so a future Okta/Auth0/etc. caller can reuse the shape without a
rename. The validator performs no network I/O on import — JWKS fetches happen
lazily on the first `validate()` call and are cached by the underlying
`PyJWKClient` (default lifespan 300s).

Three-outcome contract (no exceptions for control flow):

- VALID:    signature + iss/aud/tid/exp/nbf all pass.
- NOT_AAD:  kid unknown to our JWKS, non-JWT shape, or issuer mismatch.
            Caller should fall through to the next auth branch.
- INVALID:  kid resolved but bad signature, expired, missing required claim,
            alg=none/HS256 attempt, or aud/tid mismatch.
            Caller must reject the request (401) — do not fall through.

The aud/tid-mismatch-is-INVALID rule is deliberate: once we resolve a `kid`
from AAD's JWKS, the token is *claiming* to be for us. Any failure past that
point is a hard 401 rather than fall-through, which would otherwise open a
confused-deputy hole if a downstream IdP path is ever misconfigured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import jwt
from jwt import PyJWKClient

log = logging.getLogger(__name__)

_ALLOWED_ALGORITHMS: tuple[str, ...] = ("RS256",)


class Outcome(Enum):
    VALID = "valid"
    NOT_AAD = "not_aad"
    INVALID = "invalid"


@dataclass(frozen=True)
class AadValidatorConfig:
    """Configuration for AAD JWT local validation.

    `audience` tolerates either `api://<guid>` or bare `<guid>` — see
    `accepted_audiences()`. `issuer_override` is provided for sovereign clouds
    or to accept v1 tokens (https://sts.windows.net/{tenant}/).
    """

    tenant_id: str
    audience: str
    issuer: str | None = None
    issuer_override: str | None = None
    jwks_url: str | None = None
    leeway_seconds: int = 60

    def resolved_issuer(self) -> str:
        if self.issuer_override:
            return self.issuer_override
        if self.issuer:
            return self.issuer
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    def resolved_jwks_url(self) -> str:
        if self.jwks_url:
            return self.jwks_url
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"

    def accepted_audiences(self) -> tuple[str, ...]:
        """Normalise audience to tolerate GUID vs api://GUID shapes.

        AAD issues tokens with the exact audience that was requested. If CI
        requests `api://<guid>/.default` the `aud` claim is `api://<guid>`; if
        a client requests the bare GUID it's just `<guid>`. Accepting both
        removes a silent-401 misconfiguration footgun.
        """
        a = self.audience
        if a.startswith("api://"):
            return (a, a[len("api://") :])
        return (a, f"api://{a}")


@dataclass(frozen=True)
class AadClaims:
    sub: str | None
    oid: str | None
    appid: str | None
    tid: str
    aud: str
    iss: str
    email: str | None
    name: str | None
    preferred_username: str | None
    upn: str | None
    is_service_principal: bool
    raw: dict


@dataclass(frozen=True)
class AadValidationOutcome:
    outcome: Outcome
    claims: AadClaims | None = None
    reason: str | None = None


def build_validator(cfg: AadValidatorConfig) -> AadTokenValidator:
    """Build a validator with a fresh PyJWKClient.

    PyJWKClient construction is lightweight (no network I/O); the first
    `get_signing_key_from_jwt` call fetches JWKS and caches it.
    """
    jwks_client = PyJWKClient(cfg.resolved_jwks_url())
    return AadTokenValidator(cfg, jwks_client)


def _claims_from_payload(payload: dict) -> AadClaims:
    appid = payload.get("appid") or payload.get("azp")
    sub = payload.get("sub")
    oid = payload.get("oid")
    # App-only tokens (client-credentials): no `sub` tied to a human, only
    # `oid`/`appid`. A user token has a real `sub`. `idtyp == "app"` is the
    # most reliable signal when present; fall back to sub/oid heuristic.
    idtyp = payload.get("idtyp")
    if idtyp == "app":
        is_service_principal = True
    elif idtyp == "user":
        is_service_principal = False
    else:
        is_service_principal = sub is None or sub == oid

    return AadClaims(
        sub=sub,
        oid=oid,
        appid=appid,
        tid=payload.get("tid", ""),
        aud=payload.get("aud", ""),
        iss=payload.get("iss", ""),
        email=payload.get("email"),
        name=payload.get("name"),
        preferred_username=payload.get("preferred_username"),
        upn=payload.get("upn"),
        is_service_principal=is_service_principal,
        raw=payload,
    )


class AadTokenValidator:
    def __init__(self, cfg: AadValidatorConfig, jwks_client: PyJWKClient) -> None:
        self._cfg = cfg
        self._jwks_client = jwks_client

    def validate(self, token: str) -> AadValidationOutcome:
        if not token or not isinstance(token, str) or token.count(".") != 2:
            return AadValidationOutcome(
                outcome=Outcome.NOT_AAD, reason="not a jwt shape"
            )

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except jwt.exceptions.PyJWKClientError as e:
            # kid unknown to our JWKS (or JWKS fetch failed) → not our token.
            return AadValidationOutcome(
                outcome=Outcome.NOT_AAD, reason=f"kid not resolved: {e}"
            )
        except jwt.exceptions.DecodeError as e:
            return AadValidationOutcome(
                outcome=Outcome.NOT_AAD, reason=f"jwt decode error: {e}"
            )

        accepted_auds = list(self._cfg.accepted_audiences())
        issuer = self._cfg.resolved_issuer()

        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(_ALLOWED_ALGORITHMS),
                audience=accepted_auds,
                issuer=issuer,
                leeway=self._cfg.leeway_seconds,
                options={
                    "require": ["exp", "iat", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.exceptions.InvalidIssuerError as e:
            # Signed by AAD but not *our* issuer (e.g. v1 sts.windows.net,
            # sovereign cloud). Fall through — another branch may handle it.
            return AadValidationOutcome(
                outcome=Outcome.NOT_AAD, reason=f"issuer mismatch: {e}"
            )
        except jwt.exceptions.InvalidTokenError as e:
            # Sig failed, expired, aud mismatch, missing required claim,
            # alg whitelist violation. Token claimed to be for us (kid
            # resolved) but is broken — hard reject.
            return AadValidationOutcome(
                outcome=Outcome.INVALID, reason=str(e) or type(e).__name__
            )

        tid = payload.get("tid")
        if not tid:
            return AadValidationOutcome(
                outcome=Outcome.INVALID, reason="missing tid claim"
            )
        if tid != self._cfg.tenant_id:
            return AadValidationOutcome(
                outcome=Outcome.INVALID,
                reason=f"tid mismatch: got {tid}, expected {self._cfg.tenant_id}",
            )

        return AadValidationOutcome(
            outcome=Outcome.VALID, claims=_claims_from_payload(payload)
        )


__all__ = [
    "AadClaims",
    "AadTokenValidator",
    "AadValidationOutcome",
    "AadValidatorConfig",
    "Outcome",
    "build_validator",
]
