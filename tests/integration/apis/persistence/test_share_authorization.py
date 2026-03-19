"""
Share authorization and access control tests.

Tests cross-user access, ownership enforcement, and access control
for share link operations. Uses the built-in secondary_api_client
fixture for multi-user testing.
"""

from fastapi.testclient import TestClient

from ..infrastructure.gateway_adapter import GatewayAdapter


def _owner_create_shared_session(
    gateway_adapter: GatewayAdapter, api_client: TestClient
) -> tuple[str, str]:
    """Helper: owner creates a session and shares it. Returns (session_id, share_id)."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")
    resp = api_client.post(f"/api/v1/share/{session.id}", json={"require_authentication": True})
    assert resp.status_code == 200
    return session.id, resp.json()["share_id"]


# ---------------------------------------------------------------------------
# Ownership enforcement
# ---------------------------------------------------------------------------

def test_only_owner_can_update_share(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Non-owners cannot update share link settings."""
    _, share_id = _owner_create_shared_session(gateway_adapter, api_client)

    # Owner can update
    resp = api_client.patch(
        f"/api/v1/share/{share_id}",
        json={"allowed_domains": ["company.com"]},
    )
    assert resp.status_code == 200

    # Non-owner gets error
    resp = secondary_api_client.patch(
        f"/api/v1/share/{share_id}",
        json={"allowed_domains": ["evil.com"]},
    )
    assert resp.status_code in (403, 404)


def test_only_owner_can_delete_share(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Non-owners cannot delete a share link."""
    session_id, share_id = _owner_create_shared_session(gateway_adapter, api_client)

    resp = secondary_api_client.delete(f"/api/v1/share/{share_id}")
    assert resp.status_code in (403, 404)

    # Verify share still exists for owner
    resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 200


def test_only_owner_can_manage_users(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Non-owners cannot add, list, or remove users from a share."""
    _, share_id = _owner_create_shared_session(gateway_adapter, api_client)

    # Non-owner cannot list users
    resp = secondary_api_client.get(f"/api/v1/share/{share_id}/users")
    assert resp.status_code in (403, 404)

    # Non-owner cannot add users
    resp = secondary_api_client.post(
        f"/api/v1/share/{share_id}/users",
        json={"shares": [{"user_email": "hacker@evil.com"}]},
    )
    assert resp.status_code in (403, 404)

    # Non-owner cannot delete users
    resp = secondary_api_client.request(
        "DELETE",
        f"/api/v1/share/{share_id}/users",
        json={"user_emails": ["someone@company.com"]},
    )
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Share listing isolation
# ---------------------------------------------------------------------------

def test_share_listing_isolation(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """Users only see their own shares in the listing."""
    # Owner (sam_dev_user) creates two shares
    _owner_create_shared_session(gateway_adapter, api_client)
    _owner_create_shared_session(gateway_adapter, api_client)

    # Secondary user creates a share
    s3 = gateway_adapter.create_session(user_id="secondary_user", agent_name="TestAgent")
    resp = secondary_api_client.post(f"/api/v1/share/{s3.id}", json={"require_authentication": True})
    assert resp.status_code == 200

    # Owner sees only their 2 shares
    resp = api_client.get("/api/v1/share/")
    assert resp.status_code == 200
    assert resp.json()["meta"]["pagination"]["count"] == 2

    # Secondary sees only their 1 share
    resp = secondary_api_client.get("/api/v1/share/")
    assert resp.status_code == 200
    assert resp.json()["meta"]["pagination"]["count"] == 1


# ---------------------------------------------------------------------------
# get_share_link_for_session ownership scoping
# ---------------------------------------------------------------------------

def test_get_share_link_for_session_requires_ownership(
    api_client: TestClient,
    secondary_api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """GET /share/link/{session_id} only works for the session owner."""
    session_id, _ = _owner_create_shared_session(gateway_adapter, api_client)

    # Owner can get it
    resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 200

    # Non-owner gets 404
    resp = secondary_api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Deleted share is inaccessible
# ---------------------------------------------------------------------------

def test_deleted_share_inaccessible(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
):
    """A deleted share cannot be retrieved, updated, or have users managed."""
    session_id, share_id = _owner_create_shared_session(gateway_adapter, api_client)

    # Delete
    resp = api_client.delete(f"/api/v1/share/{share_id}")
    assert resp.status_code == 200

    # Cannot get it by session
    resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 404

    # Cannot update it
    resp = api_client.patch(f"/api/v1/share/{share_id}", json={"allowed_domains": ["x.com"]})
    assert resp.status_code in (403, 404)

    # Cannot get users
    resp = api_client.get(f"/api/v1/share/{share_id}/users")
    assert resp.status_code in (403, 404)
