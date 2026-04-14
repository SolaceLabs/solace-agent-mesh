"""
Behaviour tests for share utility functions.

These tests verify domain validation correctness, PII scrubbing in anonymization,
and URL construction — all of which have direct security implications.
"""

import pytest

from solace_agent_mesh.gateway.http_sse.utils.share_utils import (
    validate_domain,
    validate_domains_list,
    extract_email_domain,
    anonymize_chat_task,
    build_share_url,
    generate_share_id,
    format_allowed_domains,
    parse_allowed_domains,
)


# ---------------------------------------------------------------------------
# generate_share_id
# ---------------------------------------------------------------------------

class TestGenerateShareId:

    def test_generates_21_character_id(self):
        assert len(generate_share_id()) == 21

    def test_generates_unique_ids(self):
        ids = {generate_share_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_contains_only_url_safe_characters(self):
        import string
        alphabet = set(string.ascii_letters + string.digits)
        for _ in range(20):
            share_id = generate_share_id()
            assert all(c in alphabet for c in share_id), f"Non-URL-safe char in: {share_id}"


# ---------------------------------------------------------------------------
# validate_domain
# ---------------------------------------------------------------------------

class TestValidateDomain:

    @pytest.mark.parametrize("domain", [
        "company.com",
        "sub.company.com",
        "my-company.co.uk",
        "example.io",
        "a.b",
    ])
    def test_valid_domains_are_accepted(self, domain):
        assert validate_domain(domain) is True

    @pytest.mark.parametrize("domain", [
        "",
        "nodot",
        "@company.com",
        ".company.com",
        "company.com.",
        "a" * 254,                  # exceeds max domain length
        "a" * 64 + ".com",          # label too long
        "company..com",
        "-company.com",
        "company-.com",
    ])
    def test_invalid_domains_are_rejected(self, domain):
        assert validate_domain(domain) is False


# ---------------------------------------------------------------------------
# validate_domains_list
# ---------------------------------------------------------------------------

class TestValidateDomainsList:

    def test_empty_list_is_valid(self):
        is_valid, error = validate_domains_list([])
        assert is_valid is True
        assert error is None

    def test_valid_list_passes(self):
        is_valid, error = validate_domains_list(["company.com", "partner.org"])
        assert is_valid is True

    def test_more_than_10_domains_rejected(self):
        domains = [f"domain{i}.com" for i in range(11)]
        is_valid, error = validate_domains_list(domains)
        assert is_valid is False
        assert "10" in error

    def test_duplicate_domains_rejected(self):
        is_valid, error = validate_domains_list(["company.com", "COMPANY.COM"])
        assert is_valid is False
        assert "Duplicate" in error

    def test_single_bad_domain_fails_the_whole_list(self):
        is_valid, error = validate_domains_list(["good.com", "not_a_domain"])
        assert is_valid is False


# ---------------------------------------------------------------------------
# extract_email_domain
# ---------------------------------------------------------------------------

class TestExtractEmailDomain:

    def test_returns_lowercase_domain(self):
        assert extract_email_domain("User@COMPANY.COM") == "company.com"

    def test_returns_none_for_missing_at_sign(self):
        assert extract_email_domain("notanemail") is None

    def test_returns_none_for_multiple_at_signs(self):
        assert extract_email_domain("a@b@c.com") is None

    def test_returns_none_for_empty_string(self):
        assert extract_email_domain("") is None

    def test_returns_none_when_domain_part_is_invalid(self):
        assert extract_email_domain("user@nodot") is None


# ---------------------------------------------------------------------------
# anonymize_chat_task — PII scrubbing
# ---------------------------------------------------------------------------

class TestAnonymizeChatTask:
    """
    Verify that user-identifying fields are removed or replaced before
    a task is included in a public shared session view.
    """

    def _make_task(self, **overrides):
        base = {
            "id": "task-123",
            "session_id": "real-session-id",
            "user_id": "real-user-id-456",
            "message_bubbles": "[]",
            "task_metadata": None,
        }
        base.update(overrides)
        return base

    def test_user_id_is_replaced_with_anonymous(self):
        result = anonymize_chat_task(self._make_task())
        assert result["user_id"] == "anonymous"

    def test_original_user_id_is_not_present_in_output(self):
        task = self._make_task(user_id="sensitive-user-789")
        result = anonymize_chat_task(task)
        assert "sensitive-user-789" not in str(result)

    def test_session_id_is_replaced_with_hash(self):
        result = anonymize_chat_task(self._make_task(session_id="real-session-id"))
        assert result["session_id"] != "real-session-id"
        assert result["session_id"].startswith("session_")

    def test_session_id_anonymisation_is_deterministic(self):
        """Same session_id must always produce the same anonymized value (for UI consistency)."""
        task = self._make_task(session_id="real-session-id")
        result1 = anonymize_chat_task(task)
        result2 = anonymize_chat_task(task)
        assert result1["session_id"] == result2["session_id"]

    def test_two_different_sessions_get_different_anonymized_ids(self):
        r1 = anonymize_chat_task(self._make_task(session_id="session-AAA"))
        r2 = anonymize_chat_task(self._make_task(session_id="session-BBB"))
        assert r1["session_id"] != r2["session_id"]

    def test_message_content_is_preserved(self):
        """Anonymization must not strip message content — only metadata."""
        import json
        bubbles = [{"role": "user", "content": "Hello world", "metadata": {"userId": "u1"}}]
        task = self._make_task(message_bubbles=json.dumps(bubbles))
        result = anonymize_chat_task(task)
        result_bubbles = json.loads(result["message_bubbles"])
        assert result_bubbles[0]["content"] == "Hello world"

    def test_user_identifying_metadata_stripped_from_message_bubbles(self):
        """userId and sessionId must be removed from bubble metadata."""
        import json
        bubbles = [{"role": "user", "content": "Hi", "metadata": {"userId": "u1", "sessionId": "s1", "keep": "this"}}]
        task = self._make_task(message_bubbles=json.dumps(bubbles))
        result = anonymize_chat_task(task)
        result_bubbles = json.loads(result["message_bubbles"])
        meta = result_bubbles[0]["metadata"]
        assert "userId" not in meta
        assert "sessionId" not in meta
        assert meta.get("keep") == "this"

    def test_original_task_dict_is_not_mutated(self):
        task = self._make_task()
        original_user_id = task["user_id"]
        anonymize_chat_task(task)
        assert task["user_id"] == original_user_id


# ---------------------------------------------------------------------------
# build_share_url
# ---------------------------------------------------------------------------

class TestBuildShareUrl:

    def test_url_uses_hash_router_format(self):
        url = build_share_url("abc123", "https://app.example.com")
        assert "/#/share/abc123" in url

    def test_trailing_slash_on_base_url_is_stripped(self):
        url = build_share_url("abc123", "https://app.example.com/")
        assert "//share" not in url
        assert url == "https://app.example.com/#/share/abc123"

    def test_share_id_is_embedded_correctly(self):
        share_id = "XyZ987abcDEF123456789"
        url = build_share_url(share_id, "https://app.example.com")
        assert url.endswith(share_id)


# ---------------------------------------------------------------------------
# format_allowed_domains / parse_allowed_domains roundtrip
# ---------------------------------------------------------------------------

class TestDomainSerialisation:

    def test_roundtrip_preserves_domains(self):
        domains = ["company.com", "partner.org", "subsidiary.co.uk"]
        serialised = format_allowed_domains(domains)
        assert serialised is not None
        recovered = parse_allowed_domains(serialised)
        assert recovered == domains

    def test_empty_list_formats_to_none(self):
        assert format_allowed_domains([]) is None

    def test_none_parses_to_empty_list(self):
        assert parse_allowed_domains(None) == []

    def test_whitespace_around_domains_is_stripped_on_parse(self):
        result = parse_allowed_domains("  company.com , partner.org  ")
        assert result == ["company.com", "partner.org"]
