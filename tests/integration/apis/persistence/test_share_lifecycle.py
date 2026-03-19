"""
Share link lifecycle tests using FastAPI HTTP endpoints.

Tests the complete share link CRUD flow: create, read, update, delete
through actual HTTP API calls to /share endpoints.
"""

from fastapi.testclient import TestClient

from ..infrastructure.gateway_adapter import GatewayAdapter


def _create_shared_session(gateway_adapter: GatewayAdapter, api_client: TestClient) -> tuple[str, dict]:
    """Helper: create a session via gateway adapter and share it. Returns (session_id, share_response)."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")
    resp = api_client.post(
        f"/api/v1/share/{session.id}",
        json={"require_authentication": True},
    )
    assert resp.status_code == 200
    return session.id, resp.json()


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

def test_create_share_link(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Creating a share link returns a valid response with share_id and URL."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")

    resp = api_client.post(
        f"/api/v1/share/{session.id}",
        json={"require_authentication": True},
    )
    assert resp.status_code == 200

    share = resp.json()
    assert share["share_id"]
    assert share["session_id"] == session.id
    assert share["share_url"]
    assert share["require_authentication"] is True
    assert share["access_type"] == "authenticated"


def test_create_share_link_is_idempotent(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Creating a share link twice for the same session returns the same link."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")

    share1 = api_client.post(f"/api/v1/share/{session.id}", json={"require_authentication": True}).json()
    share2 = api_client.post(f"/api/v1/share/{session.id}", json={"require_authentication": True}).json()

    assert share1["share_id"] == share2["share_id"]


def test_get_share_link_for_session(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """GET /share/link/{session_id} returns the existing share link."""
    session_id, created = _create_shared_session(gateway_adapter, api_client)

    resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 200

    fetched = resp.json()
    assert fetched["share_id"] == created["share_id"]
    assert fetched["session_id"] == session_id


def test_get_share_link_not_found(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """GET /share/link/{session_id} returns 404 when no share exists."""
    session = gateway_adapter.create_session(user_id="sam_dev_user", agent_name="TestAgent")

    resp = api_client.get(f"/api/v1/share/link/{session.id}")
    assert resp.status_code == 404


def test_list_share_links_empty(api_client: TestClient):
    """GET /share/ returns empty paginated list when no shares exist."""
    resp = api_client.get("/api/v1/share/")
    assert resp.status_code == 200

    data = resp.json()
    assert data["data"] == []
    assert data["meta"]["pagination"]["count"] == 0


def test_list_share_links(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """GET /share/ returns all share links created by the user."""
    _create_shared_session(gateway_adapter, api_client)
    _create_shared_session(gateway_adapter, api_client)

    resp = api_client.get("/api/v1/share/")
    assert resp.status_code == 200

    data = resp.json()
    assert data["meta"]["pagination"]["count"] == 2
    assert len({item["share_id"] for item in data["data"]}) == 2


def test_update_share_link_domain_restriction(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """PATCH /share/{share_id} can add domain restrictions."""
    _, share = _create_shared_session(gateway_adapter, api_client)

    resp = api_client.patch(
        f"/api/v1/share/{share['share_id']}",
        json={"allowed_domains": ["company.com"]},
    )
    assert resp.status_code == 200

    updated = resp.json()
    assert updated["allowed_domains"] == ["company.com"]
    assert updated["access_type"] == "domain-restricted"


def test_delete_share_link(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """DELETE /share/{share_id} soft-deletes the link."""
    session_id, share = _create_shared_session(gateway_adapter, api_client)

    resp = api_client.delete(f"/api/v1/share/{share['share_id']}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # The share link should no longer be retrievable
    resp = api_client.get(f"/api/v1/share/link/{session_id}")
    assert resp.status_code == 404


def test_delete_nonexistent_share_returns_404(api_client: TestClient):
    """DELETE /share/{share_id} returns 404 for unknown share."""
    resp = api_client.delete("/api/v1/share/nonexistent_share_id")
    assert resp.status_code == 404


def test_create_share_for_nonexistent_session(api_client: TestClient):
    """POST /share/{session_id} returns error for non-existent session."""
    resp = api_client.post(
        "/api/v1/share/nonexistent_session",
        json={"require_authentication": True},
    )
    assert resp.status_code in (400, 404, 500)


# ---------------------------------------------------------------------------
# End-to-end workflow
# ---------------------------------------------------------------------------

def test_end_to_end_share_workflow(api_client: TestClient, gateway_adapter: GatewayAdapter):
    """Full lifecycle: create session -> share -> update -> list -> delete -> verify gone."""
    # 1. Create session
    session_id, share = _create_shared_session(gateway_adapter, api_client)
    share_id = share["share_id"]
    assert share["access_type"] == "authenticated"

    # 2. Add domain restriction
    resp = api_client.patch(
        f"/api/v1/share/{share_id}",
        json={"allowed_domains": ["example.com"]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_type"] == "domain-restricted"

    # 3. Verify it appears in listing
    list_resp = api_client.get("/api/v1/share/")
    assert list_resp.status_code == 200
    assert any(item["share_id"] == share_id for item in list_resp.json()["data"])

    # 4. Delete
    del_resp = api_client.delete(f"/api/v1/share/{share_id}")
    assert del_resp.status_code == 200

    # 5. Verify gone from listing
    list_resp = api_client.get("/api/v1/share/")
    assert list_resp.status_code == 200
    assert not any(item["share_id"] == share_id for item in list_resp.json()["data"])
