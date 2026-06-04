"""
Tests for the OAuth-claim extraction helpers in shared.auth.middleware.

Exercises the real functions (not a local reimplementation) so a regression
in claim priority, sentinel filtering, or whitespace handling will trip CI.
"""

from __future__ import annotations

import pytest

from solace_agent_mesh.shared.auth.middleware import (
    _USER_IDENTIFIER_CLAIM_ORDER,
    _claim,
    _create_user_state,
    _extract_user_details,
    _extract_user_identifier,
)


class TestClaim:
    @pytest.mark.parametrize("sentinel", ["Unknown", "unknown", "Null", "None", ""])
    def test_sentinel_returns_none(self, sentinel):
        assert _claim({"x": sentinel}, "x") is None

    @pytest.mark.parametrize("padded", [" Unknown ", "\nnull", " "])
    def test_whitespace_padded_sentinel_returns_none(self, padded):
        assert _claim({"x": padded}, "x") is None

    def test_returns_stripped_value(self):
        assert _claim({"x": "  alice@example.com  "}, "x") == "alice@example.com"

    def test_non_string_returns_none(self):
        assert _claim({"x": 123}, "x") is None
        assert _claim({"x": None}, "x") is None
        assert _claim({"x": True}, "x") is None

    def test_missing_key_returns_none(self):
        assert _claim({}, "x") is None


class TestExtractUserIdentifier:
    def test_returns_first_valid_claim_in_priority_order(self):
        assert _extract_user_identifier({"sub": "sub-1", "email": "a@b"}) == "sub-1"

    def test_skips_sentinel_and_continues_walk(self):
        # `sub` is sentinel, must fall through to `email`.
        result = _extract_user_identifier({"sub": "Unknown", "email": "alice@example.com"})
        assert result == "alice@example.com"

    def test_username_claim_preferred_over_oid(self):
        # `username` is at position 3 in the priority order; it must beat `oid`.
        result = _extract_user_identifier({"username": "proxy-user", "oid": "object-id-123"})
        assert result == "proxy-user"

    def test_username_sentinel_falls_through_to_oid(self):
        result = _extract_user_identifier({"username": "Unknown", "oid": "object-id-123"})
        assert result == "object-id-123"

    def test_all_sentinels_falls_back_to_dev_user(self):
        user_info = {
            "sub": "Unknown",
            "email": "null",
            "name": "",
            "upn": "none",
        }
        assert _extract_user_identifier(user_info) == "sam_dev_user"

    def test_empty_user_info_falls_back_to_dev_user(self):
        assert _extract_user_identifier({}) == "sam_dev_user"

    def test_claim_order_is_stable(self):
        # Pin the priority list so accidental reorderings are caught.
        assert _USER_IDENTIFIER_CLAIM_ORDER == (
            "sub",
            "client_id",
            "username",
            "oid",
            "preferred_username",
            "upn",
            "unique_name",
            "email",
            "name",
            "azp",
            "user_id",
        )


class TestExtractUserDetails:
    def test_sentinel_email_yields_to_preferred_username(self):
        email, _ = _extract_user_details(
            {"email": "Unknown", "preferred_username": "alice@example.com"},
            "fallback-id",
        )
        assert email == "alice@example.com"

    def test_falls_back_to_user_identifier_when_no_claims(self):
        email, name = _extract_user_details({}, "alice-id")
        assert email == "alice-id"
        assert name == "alice-id"

    def test_given_and_family_combine_when_name_missing(self):
        _, name = _extract_user_details(
            {"given_name": "Alice", "family_name": "Liddell"}, "fallback"
        )
        assert name == "Alice Liddell"

    def test_empty_given_and_family_skip_to_preferred_username(self):
        # Previously the literal " " short-circuited past preferred_username.
        _, name = _extract_user_details(
            {"given_name": "", "family_name": "", "preferred_username": "alice"},
            "fallback",
        )
        assert name == "alice"


class TestCreateUserState:
    async def test_returns_expected_shape(self):
        state = await _create_user_state("alice", "alice@example.com", "Alice")
        assert state == {
            "id": "alice",
            "user_id": "alice",
            "email": "alice@example.com",
            "name": "Alice",
            "authenticated": True,
            "auth_method": "oidc",
        }

    async def test_falls_back_to_identifier_when_email_or_name_missing(self):
        state = await _create_user_state("alice", "", "")
        assert state["email"] == "alice"
        assert state["name"] == "alice"
