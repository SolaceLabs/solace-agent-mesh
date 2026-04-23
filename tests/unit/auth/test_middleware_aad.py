"""
Integration tests for the AAD JWT branch in the OAuth middleware.

These tests do NOT exercise the validator itself (covered in
test_jwt_validator.py). They monkey-patch `build_validator` with a stub that
returns canned outcomes, so we can assert the middleware's behavior for each
(outcome × soft/hard × config-state) combination.

Mirrors enterprise/tests/unit/auth/test_middleware_sam_access_token.py in
structure — same MockComponent/MockTrustManager patterns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request as FastAPIRequest

from solace_agent_mesh.shared.auth.jwt_validator import (
    AadClaims,
    AadValidationOutcome,
    Outcome,
)
from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

TENANT_ID = "11111111-1111-1111-1111-111111111111"
APP_ID_URI = "api://22222222-2222-2222-2222-222222222222"
APP_GUID = "22222222-2222-2222-2222-222222222222"


class MockComponent:
    """Mock component. AAD config keys default to empty (branch disabled)
    unless explicitly set."""

    def __init__(
        self,
        aad_tenant_id: str = "",
        aad_audience: str = "",
        aad_issuer_override: str = "",
        sam_access_token_enabled: bool = False,
    ):
        self.trust_manager = None
        self.authorization_service = None
        self.external_auth_service_url = "http://test-auth-service"
        self.external_auth_provider = "azure"
        self._config = {
            "frontend_use_authorization": True,
            "sam_access_token": {"enabled": sam_access_token_enabled},
            "aad_tenant_id": aad_tenant_id,
            "aad_audience": aad_audience,
            "aad_issuer_override": aad_issuer_override,
        }

    def get_config(self, key, default=None):
        return self._config.get(key, default)


class _StubValidator:
    """Returns pre-canned outcomes for each validate() call."""

    def __init__(self, outcome: AadValidationOutcome):
        self.outcome = outcome
        self.calls: list[str] = []

    def validate(self, token: str) -> AadValidationOutcome:
        self.calls.append(token)
        return self.outcome


def _user_claims() -> AadClaims:
    return AadClaims(
        sub="user-sub-123",
        oid="user-oid-456",
        appid=None,
        tid=TENANT_ID,
        aud=APP_ID_URI,
        iss=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        email="alice@contoso.com",
        name="Alice Example",
        preferred_username="alice@contoso.com",
        upn=None,
        is_service_principal=False,
        raw={},
    )


def _app_only_claims() -> AadClaims:
    return AadClaims(
        sub=None,
        oid="sp-oid-789",
        appid=APP_GUID,
        tid=TENANT_ID,
        aud=APP_ID_URI,
        iss=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        email=None,
        name=None,
        preferred_username=None,
        upn=None,
        is_service_principal=True,
        raw={},
    )


def _http_scope(path: str = "/api/v1/test", method: str = "GET") -> dict:
    return {
        "type": "http",
        "path": path,
        "method": method,
        "headers": [(b"authorization", b"Bearer test-token")],
        "query_string": b"",
    }


def _make_middleware_and_capture(component, patched_outcome):
    """Helper: build middleware with build_validator patched to return a stub
    yielding `patched_outcome`. Returns (middleware, mock_app, captured_dict,
    stub_validator)."""
    AuthMiddleware = create_oauth_middleware(component)

    stub = _StubValidator(patched_outcome)

    def _fake_build_validator(_cfg):
        return stub

    captured = {"state": None}
    sent_messages = []

    async def mock_app(scope, receive, send):
        request = FastAPIRequest(scope, receive)
        captured["state"] = getattr(request.state, "user", None)
        captured["auth_probe"] = getattr(request.state, "auth_probe", None)

    async def fake_send(message):
        sent_messages.append(message)

    middleware = AuthMiddleware(mock_app, component)

    return (
        middleware,
        mock_app,
        captured,
        stub,
        fake_send,
        sent_messages,
        _fake_build_validator,
    )


class TestAadMiddleware:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_aad_user_token_sets_user_state(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(outcome=Outcome.VALID, claims=_user_claims())
        mw, _, captured, stub, fake_send, _, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with patch(
            "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
            side_effect=fake_bv,
        ):
            await mw(_http_scope(), AsyncMock(), fake_send)

        assert stub.calls == ["test-token"]
        user = captured["state"]
        assert user is not None
        assert user["auth_method"] == "aad_jwt"
        assert user["id"] == "user-sub-123"
        assert user["email"] == "alice@contoso.com"
        assert user["is_service_principal"] is False
        assert user["service_principal_id"] is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_aad_app_only_token_uses_invalid_tld_sentinel(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(outcome=Outcome.VALID, claims=_app_only_claims())
        mw, _, captured, _, fake_send, _, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with patch(
            "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
            side_effect=fake_bv,
        ):
            await mw(_http_scope(), AsyncMock(), fake_send)

        user = captured["state"]
        assert user["auth_method"] == "aad_jwt"
        assert user["id"] == "sp-oid-789"  # sub None → oid
        assert user["is_service_principal"] is True
        assert user["service_principal_id"] == APP_GUID
        # .invalid TLD must be non-matchable in share ACL checks
        assert user["email"] == f"svc-principal+{APP_GUID}@aad-app-only.invalid"
        assert user["email"].endswith(".invalid")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_invalid_outcome_returns_401_no_idp_fallback(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(
            outcome=Outcome.INVALID, reason="audience mismatch"
        )
        mw, _, captured, _, fake_send, sent, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with (
            patch(
                "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
                side_effect=fake_bv,
            ),
            patch(
                "solace_agent_mesh.shared.auth.middleware._validate_token",
                new_callable=AsyncMock,
            ) as mock_validate,
            patch(
                "solace_agent_mesh.shared.auth.middleware._get_user_info",
                new_callable=AsyncMock,
            ) as mock_user_info,
        ):
            await mw(_http_scope(), AsyncMock(), fake_send)

            # Must not fall through to IdP
            mock_validate.assert_not_called()
            mock_user_info.assert_not_called()

        # 401 response was sent
        assert any(
            m.get("type") == "http.response.start" and m.get("status") == 401
            for m in sent
        )
        # request.state.user was never populated
        assert captured["state"] is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_invalid_soft_auth_continues_with_probe_flag(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(outcome=Outcome.INVALID, reason="bad sig")
        mw, _, captured, _, fake_send, sent, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        # Soft-auth path matches /api/v1/share/<21-char id>
        soft_path = "/api/v1/share/" + ("a" * 21)

        with patch(
            "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
            side_effect=fake_bv,
        ):
            await mw(_http_scope(path=soft_path), AsyncMock(), fake_send)

        # No 401 sent; probe flag raised for downstream
        assert not any(
            m.get("type") == "http.response.start" and m.get("status") == 401
            for m in sent
        )
        assert captured["auth_probe"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_not_aad_outcome_falls_through_to_idp(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(
            outcome=Outcome.NOT_AAD, reason="issuer mismatch"
        )
        mw, _, captured, _, fake_send, _, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with (
            patch(
                "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
                side_effect=fake_bv,
            ),
            patch(
                "solace_agent_mesh.shared.auth.middleware._validate_token",
                new_callable=AsyncMock,
            ) as mock_validate,
            patch(
                "solace_agent_mesh.shared.auth.middleware._get_user_info",
                new_callable=AsyncMock,
            ) as mock_user_info,
        ):
            mock_validate.return_value = True
            mock_user_info.return_value = {
                "sub": "idp-user@example.com",
                "email": "idp-user@example.com",
                "name": "IdP User",
            }
            await mw(_http_scope(), AsyncMock(), fake_send)

            mock_validate.assert_called_once()

        user = captured["state"]
        assert user is not None
        assert user["auth_method"] == "oidc"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_config_missing_skips_branch(self):
        """No AAD config → branch never runs → IdP handles the token."""
        component = MockComponent()  # no aad_* keys
        mw = create_oauth_middleware(component)(AsyncMock(), component)

        captured = {"state": None}
        sent = []

        async def fake_send(message):
            sent.append(message)

        async def mock_app(scope, receive, send):
            request = FastAPIRequest(scope, receive)
            captured["state"] = getattr(request.state, "user", None)

        mw.app = mock_app

        with (
            patch(
                "solace_agent_mesh.shared.auth.jwt_validator.build_validator"
            ) as mock_build,
            patch(
                "solace_agent_mesh.shared.auth.middleware._validate_token",
                new_callable=AsyncMock,
            ) as mock_validate,
            patch(
                "solace_agent_mesh.shared.auth.middleware._get_user_info",
                new_callable=AsyncMock,
            ) as mock_user_info,
        ):
            mock_validate.return_value = True
            mock_user_info.return_value = {
                "sub": "idp-user@example.com",
                "email": "idp-user@example.com",
                "name": "IdP User",
            }
            await mw(_http_scope(), AsyncMock(), fake_send)

            # Validator was never built
            mock_build.assert_not_called()
            # IdP path was used
            mock_validate.assert_called_once()

        assert captured["state"]["auth_method"] == "oidc"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_config_partial_disables_branch(self):
        """Only one of the pair set → branch disabled (fails noisy at mount)."""
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience="")
        mw = create_oauth_middleware(component)(AsyncMock(), component)

        captured = {"state": None}
        sent = []

        async def fake_send(message):
            sent.append(message)

        async def mock_app(scope, receive, send):
            request = FastAPIRequest(scope, receive)
            captured["state"] = getattr(request.state, "user", None)

        mw.app = mock_app

        with (
            patch(
                "solace_agent_mesh.shared.auth.jwt_validator.build_validator"
            ) as mock_build,
            patch(
                "solace_agent_mesh.shared.auth.middleware._validate_token",
                new_callable=AsyncMock,
            ) as mock_validate,
            patch(
                "solace_agent_mesh.shared.auth.middleware._get_user_info",
                new_callable=AsyncMock,
            ) as mock_user_info,
        ):
            mock_validate.return_value = True
            mock_user_info.return_value = {
                "sub": "idp-user@example.com",
                "email": "idp-user@example.com",
                "name": "IdP User",
            }
            await mw(_http_scope(), AsyncMock(), fake_send)

            mock_build.assert_not_called()

        assert captured["state"]["auth_method"] == "oidc"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_aad_branch_does_not_run_when_sam_token_succeeds(self):
        """Ordering contract: sam_access_token wins over AAD.

        `is_sam_token_enabled` is an enterprise-only check (stubbed to False
        in the community repo), so we patch it to True here to exercise the
        ordering contract.
        """
        component = MockComponent(
            aad_tenant_id=TENANT_ID,
            aad_audience=APP_ID_URI,
            sam_access_token_enabled=True,
        )

        class _SuccessTrustManager:
            def verify_user_claims_without_task_binding(self, token):
                return {
                    "sub": "sam-user@example.com",
                    "sam_user_id": "sam-user@example.com",
                    "email": "sam-user@example.com",
                    "name": "SAM User",
                }

        component.trust_manager = _SuccessTrustManager()

        outcome = AadValidationOutcome(outcome=Outcome.VALID, claims=_user_claims())
        mw, _, captured, _, fake_send, _, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with (
            patch(
                "solace_agent_mesh.shared.auth.middleware.is_sam_token_enabled",
                return_value=True,
            ),
            patch(
                "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
                side_effect=fake_bv,
            ) as mock_build,
        ):
            await mw(_http_scope(), AsyncMock(), fake_send)

            # sam_access_token won; AAD validator never built
            mock_build.assert_not_called()

        user = captured["state"]
        assert user["auth_method"] == "sam_access_token"
        assert user["id"] == "sam-user@example.com"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_validator_cache_reused_across_calls(self):
        component = MockComponent(aad_tenant_id=TENANT_ID, aad_audience=APP_ID_URI)
        outcome = AadValidationOutcome(outcome=Outcome.VALID, claims=_user_claims())
        mw, _, captured, stub, fake_send, _, fake_bv = _make_middleware_and_capture(
            component, outcome
        )

        with patch(
            "solace_agent_mesh.shared.auth.jwt_validator.build_validator",
            side_effect=fake_bv,
        ) as mock_build:
            await mw(_http_scope(), AsyncMock(), fake_send)
            await mw(_http_scope(), AsyncMock(), fake_send)

        # build_validator called exactly once across two requests
        assert mock_build.call_count == 1
        assert len(stub.calls) == 2
