"""
Share user management tests using FastAPI HTTP endpoints.

Tests adding, listing, updating, and removing per-user share access
through the /share/{share_id}/users endpoints.
"""

from fastapi.testclient import TestClient

from ..infrastructure.gateway_adapter import GatewayAdapter


def _create_shared_session(gateway_adapter: GatewayAdapter, api_client: TestClient) -> tuple[str, str]:
    """Helper: create a session and share it. Returns (session_id, share_id)."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")
    resp = api_client.post(f"/api/v1/share/{session.id}", json={"require_authentication": True})
    assert resp.status_code == 200
    return session.id, resp.json()["share_id"]


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def test_get_share_users_empty(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """GET /share/{share_id}/users returns empty list initially."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    resp = api_client.get(f"/api/v1/share/{share_id}/users")
    assert resp.status_code == 200

    data = resp.json()
    assert data["share_id"] == share_id
    assert data["users"] == []


def test_add_share_users(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """POST /share/{share_id}/users adds users with correct access levels."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    resp = api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={
            "shares": [
                {"user_email": "alice@example.com", "access_level": "RESOURCE_VIEWER"},
                {"user_email": "bob@example.com", "access_level": "RESOURCE_VIEWER"},
            ]
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["added_count"] == 2
    emails = {u["user_email"] for u in data["users"]}
    assert emails == {"alice@example.com", "bob@example.com"}


def test_add_duplicate_user_is_idempotent(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Adding the same user twice with the same access level doesn't create duplicates."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)
    payload = {"shares": [{"user_email": "alice@example.com", "access_level": "RESOURCE_VIEWER"}]}

    api_client.post(f"/api/v1/share/{share_id}/users", json=payload)
    api_client.post(f"/api/v1/share/{share_id}/users", json=payload)

    users_resp = api_client.get(f"/api/v1/share/{share_id}/users")
    users = users_resp.json()["users"]
    alice_entries = [u for u in users if u["user_email"] == "alice@example.com"]
    assert len(alice_entries) == 1


def test_update_user_access_level(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Re-adding a user with different access_level updates in-place and preserves original."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    # Add as viewer
    api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "alice@example.com", "access_level": "RESOURCE_VIEWER"}]},
    )

    # Upgrade to editor
    resp = api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "alice@example.com", "access_level": "RESOURCE_EDITOR"}]},
    )
    assert resp.status_code == 200

    users_resp = api_client.get(f"/api/v1/share/{share_id}/users")
    alice = next(u for u in users_resp.json()["users"] if u["user_email"] == "alice@example.com")
    assert alice["access_level"] == "RESOURCE_EDITOR"
    assert alice["original_access_level"] == "RESOURCE_VIEWER"


def test_delete_share_users(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """DELETE /share/{share_id}/users removes specified users."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={
            "shares": [
                {"user_email": "alice@example.com"},
                {"user_email": "bob@example.com"},
            ]
        },
    )

    del_resp = api_client.request(
        "DELETE",
        f"/api/v1/share/{share_id}/users",
        json={"user_emails": ["alice@example.com"]},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_count"] == 1

    users_resp = api_client.get(f"/api/v1/share/{share_id}/users")
    users = users_resp.json()["users"]
    assert len(users) == 1
    assert users[0]["user_email"] == "bob@example.com"


def test_adding_users_changes_access_type_to_user_specific(
    api_client: TestClient, gateway_adapter: GatewayAdapter
):
    """Share access_type becomes 'user-specific' when users are added."""
    session_id, share_id = _create_shared_session(gateway_adapter, api_client)

    # Initially "authenticated"
    link_resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert link_resp.json()["access_type"] == "authenticated"

    # Add a user
    api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "alice@example.com"}]},
    )

    # Should now be "user-specific"
    link_resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert link_resp.json()["access_type"] == "user-specific"


def test_get_users_for_nonexistent_share_returns_error(api_client: TestClient):
    """GET /share/{share_id}/users returns error for unknown share."""
    resp = api_client.get("/api/v1/share/nonexistent_id/users")
    assert resp.status_code in (403, 404)


def test_email_case_insensitivity(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """User emails are treated case-insensitively."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "Alice@Example.COM"}]},
    )

    del_resp = api_client.request(
        "DELETE",
        f"/api/v1/share/{share_id}/users",
        json={"user_emails": ["alice@example.com"]},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_count"] == 1


# ---------------------------------------------------------------------------
# End-to-end user management workflow
# ---------------------------------------------------------------------------

def test_full_user_management_workflow(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Create share -> add users -> update access -> remove users -> verify clean."""
    _, share_id = _create_shared_session(gateway_adapter, api_client)

    # 1. Add viewers
    add_resp = api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={
            "shares": [
                {"user_email": "viewer1@co.com", "access_level": "RESOURCE_VIEWER"},
                {"user_email": "viewer2@co.com", "access_level": "RESOURCE_VIEWER"},
            ]
        },
    )
    assert add_resp.json()["added_count"] == 2

    # 2. Upgrade viewer1 to editor
    api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "viewer1@co.com", "access_level": "RESOURCE_EDITOR"}]},
    )

    # 3. Verify state
    users = {u["user_email"]: u for u in api_client.get(f"/api/v1/share/{share_id}/users").json()["users"]}
    assert users["viewer1@co.com"]["access_level"] == "RESOURCE_EDITOR"
    assert users["viewer2@co.com"]["access_level"] == "RESOURCE_VIEWER"

    # 4. Remove both
    api_client.request(
        "DELETE",
        f"/api/v1/share/{share_id}/users",
        json={"user_emails": ["viewer1@co.com", "viewer2@co.com"]},
    )

    # 5. Verify empty
    assert api_client.get(f"/api/v1/share/{share_id}/users").json()["users"] == []
