"""
Projects Pin/Star API Tests

Tests for the PATCH /api/v1/projects/{id}/pin endpoint that toggles
the is_pinned status of a project.
"""

import pytest
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


def _make_patched_has_view_access(project_id, user_id, original):
    """Factory that returns a patched _has_view_access granting *user_id* view access to *project_id*."""
    def _patched(self, db, pid, uid):
        if pid == project_id and uid == user_id:
            return True
        return original(self, db, pid, uid)
    return _patched


class TestProjectsPin:
    """Test pin/star toggle functionality for projects"""

    def test_toggle_pin_unpinned_project_pins_it(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/projects/{id}/pin toggles unpinned project to pinned"""
        # Setup: Create an unpinned project
        project_id = "pin-test-project-001"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Pin Test Project",
            user_id="sam_dev_user",
            description="A project to test pinning",
        )

        # Verify project starts unpinned
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200
        assert get_response.json()["isPinned"] is False

        # Act: Toggle pin
        response = api_client.patch(f"/api/v1/projects/{project_id}/pin")

        # Assert: Project is now pinned
        assert response.status_code == 200
        project_data = response.json()
        assert project_data["id"] == project_id
        assert project_data["isPinned"] is True

    def test_toggle_pin_twice_returns_to_unpinned(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/projects/{id}/pin toggles back to unpinned on second call"""
        # Setup: Create a project
        project_id = "pin-test-project-002"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Double Toggle Project",
            user_id="sam_dev_user",
        )

        # First toggle: pin it
        response1 = api_client.patch(f"/api/v1/projects/{project_id}/pin")
        assert response1.status_code == 200
        assert response1.json()["isPinned"] is True

        # Second toggle: unpin it
        response2 = api_client.patch(f"/api/v1/projects/{project_id}/pin")
        assert response2.status_code == 200
        assert response2.json()["isPinned"] is False

    def test_toggle_pin_persists_to_database(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that pin status persists after toggling (verified via GET)"""
        # Setup: Create a project
        project_id = "pin-test-project-003"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Persistence Test Project",
            user_id="sam_dev_user",
        )

        # Toggle pin
        api_client.patch(f"/api/v1/projects/{project_id}/pin")

        # Verify via GET that pin status persisted
        get_response = api_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200
        assert get_response.json()["isPinned"] is True

    def test_toggle_pin_returns_404_for_nonexistent_project(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/projects/{id}/pin returns 404 for non-existent project"""
        response = api_client.patch("/api/v1/projects/nonexistent-project-id/pin")
        assert response.status_code == 404

    def test_toggle_pin_returns_404_for_other_users_project(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/projects/{id}/pin returns 404 for a project the user cannot access (prevents ID enumeration)"""
        # Setup: Create a project owned by a different user (not shared with sam_dev_user)
        project_id = "pin-test-project-other-user"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Other User Project",
            user_id="other_user",
        )

        # Act: Try to pin as sam_dev_user (the default test user)
        response = api_client.patch(f"/api/v1/projects/{project_id}/pin")

        # Assert: Should return 404 (same as non-existent to prevent ID enumeration)
        assert response.status_code == 404

    def test_toggle_pin_response_includes_all_project_fields(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that pin toggle response includes all expected project fields"""
        # Setup: Create a project
        project_id = "pin-test-project-004"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Full Fields Project",
            user_id="sam_dev_user",
            description="Testing full response fields",
        )

        # Act: Toggle pin
        response = api_client.patch(f"/api/v1/projects/{project_id}/pin")

        # Assert: Response includes all expected fields
        assert response.status_code == 200
        project_data = response.json()
        assert "id" in project_data
        assert "name" in project_data
        assert "userId" in project_data
        assert "isPinned" in project_data
        assert "createdAt" in project_data
        assert project_data["id"] == project_id
        assert project_data["name"] == "Full Fields Project"
        assert project_data["userId"] == "sam_dev_user"

    def test_get_projects_list_includes_is_pinned_field(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that GET /api/v1/projects returns isPinned field for each project"""
        # Setup: Create a project
        project_id = "pin-test-project-005"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="List Pin Field Test",
            user_id="sam_dev_user",
        )

        # Act: Get all projects
        response = api_client.get("/api/v1/projects")

        # Assert: isPinned field is present in each project
        assert response.status_code == 200
        data = response.json()
        projects = data["projects"]
        assert len(projects) > 0

        # Find our seeded project
        our_project = next((p for p in projects if p["id"] == project_id), None)
        assert our_project is not None
        assert "isPinned" in our_project
        assert our_project["isPinned"] is False

    def test_get_projects_list_shows_per_user_pin_state(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that GET /api/v1/projects returns different isPinned for different users on a shared project."""
        from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService
        from solace_agent_mesh.common.services.default_resource_sharing_service import DefaultResourceSharingService
        from solace_agent_mesh.services.resource_sharing_service import ResourceType

        project_id = "pin-list-per-user"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="List Per-User Pin Project",
            user_id="sam_dev_user",
        )

        # Grant secondary_user view access via both _has_view_access and get_shared_resource_ids
        original_get_shared = DefaultResourceSharingService.get_shared_resource_ids

        def _patched_get_shared(self, session, user_email, resource_type):
            result = original_get_shared(self, session=session, user_email=user_email, resource_type=resource_type)
            if user_email == "secondary_user" and resource_type == ResourceType.PROJECT:
                result = list(result) + [project_id]
            return result

        patched_access = _make_patched_has_view_access(project_id, "secondary_user", ProjectService._has_view_access)
        with patch.object(ProjectService, "_has_view_access", patched_access), \
             patch.object(DefaultResourceSharingService, "get_shared_resource_ids", _patched_get_shared):
            # User A pins the project
            pin_resp = api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert pin_resp.status_code == 200
            assert pin_resp.json()["isPinned"] is True

            # User A list shows pinned
            list_a = api_client.get("/api/v1/projects")
            assert list_a.status_code == 200
            proj_a = next(
                (p for p in list_a.json()["projects"] if p["id"] == project_id), None
            )
            assert proj_a is not None
            assert proj_a["isPinned"] is True

            # User B list shows unpinned for the same project
            list_b = secondary_api_client.get("/api/v1/projects")
            assert list_b.status_code == 200
            proj_b = next(
                (p for p in list_b.json()["projects"] if p["id"] == project_id), None
            )
            assert proj_b is not None
            assert proj_b["isPinned"] is False

    def test_per_user_pin_isolation_on_shared_project(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test per-user pin isolation on a single shared project.

        User A owns the project and shares it with User B.
        User A pins it — User B should still see it unpinned.
        """
        from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService

        project_id = "pin-isolation-shared"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Shared Isolation Project",
            user_id="sam_dev_user",
        )

        # Simulate shared access: grant secondary_user view access to this project
        patched_access = _make_patched_has_view_access(project_id, "secondary_user", ProjectService._has_view_access)

        with patch.object(ProjectService, "_has_view_access", patched_access):
            # Both users can see the project and it starts unpinned for both
            resp_a = api_client.get(f"/api/v1/projects/{project_id}")
            assert resp_a.status_code == 200
            assert resp_a.json()["isPinned"] is False

            resp_b = secondary_api_client.get(f"/api/v1/projects/{project_id}")
            assert resp_b.status_code == 200
            assert resp_b.json()["isPinned"] is False

            # User A pins the shared project
            pin_a = api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert pin_a.status_code == 200
            assert pin_a.json()["isPinned"] is True

            # User B still sees it unpinned — per-user isolation
            resp_b2 = secondary_api_client.get(f"/api/v1/projects/{project_id}")
            assert resp_b2.status_code == 200
            assert resp_b2.json()["isPinned"] is False

            # User B pins independently
            pin_b = secondary_api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert pin_b.status_code == 200
            assert pin_b.json()["isPinned"] is True

            # User A's pin state unchanged
            resp_a2 = api_client.get(f"/api/v1/projects/{project_id}")
            assert resp_a2.status_code == 200
            assert resp_a2.json()["isPinned"] is True

            # User A unpins — User B still pinned
            unpin_a = api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert unpin_a.status_code == 200
            assert unpin_a.json()["isPinned"] is False

            resp_b3 = secondary_api_client.get(f"/api/v1/projects/{project_id}")
            assert resp_b3.status_code == 200
            assert resp_b3.json()["isPinned"] is True

    def test_shared_collaborator_can_toggle_pin(
        self,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that a shared collaborator (non-owner) can toggle pin and gets 200."""
        from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService

        project_id = "pin-test-shared-collaborator"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Collaborator Pin Project",
            user_id="sam_dev_user",
        )

        # Simulate shared access for secondary_user
        patched_access = _make_patched_has_view_access(project_id, "secondary_user", ProjectService._has_view_access)

        with patch.object(ProjectService, "_has_view_access", patched_access):
            # Non-owner collaborator toggles pin — should succeed with 200
            response = secondary_api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert response.status_code == 200
            assert response.json()["id"] == project_id
            assert response.json()["isPinned"] is True

            # Toggle again to unpin
            response2 = secondary_api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert response2.status_code == 200
            assert response2.json()["isPinned"] is False

    def test_pin_cleanup_on_project_soft_delete(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that soft-deleting a project removes its pin records."""
        import sqlalchemy as sa

        project_id = "pin-cleanup-soft-delete"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Cleanup Test Project",
            user_id="sam_dev_user",
        )

        # Pin the project
        pin_resp = api_client.patch(f"/api/v1/projects/{project_id}/pin")
        assert pin_resp.status_code == 200
        assert pin_resp.json()["isPinned"] is True

        # Delete the project (soft delete via API)
        delete_resp = api_client.delete(f"/api/v1/projects/{project_id}")
        assert delete_resp.status_code == 204

        # Verify pin record is gone by checking the database directly
        with gateway_adapter.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            pins_table = metadata.tables["project_user_pins"]
            result = conn.execute(
                sa.select(pins_table).where(pins_table.c.project_id == project_id)
            ).fetchall()
            assert len(result) == 0, "Pin records should be removed after soft delete"

    def test_concurrent_pin_integrity_error_returns_pinned(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that toggle_user_pin returns True when IntegrityError occurs
        (simulating a concurrent insert race condition).

        Tested at the repository level with its own session to avoid autoflush
        interference from the service layer's subsequent queries.
        """
        from sqlalchemy.orm import sessionmaker
        from solace_agent_mesh.gateway.http_sse.repository.project_repository import ProjectRepository
        from solace_agent_mesh.gateway.http_sse.repository.models.project_user_pin_model import ProjectUserPinModel

        project_id = "pin-integrity-error-test"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Integrity Error Project",
            user_id="sam_dev_user",
        )

        engine = gateway_adapter.db_manager.provider.get_sync_gateway_engine()
        Session = sessionmaker(bind=engine, autoflush=False)
        db = Session()
        try:
            repo = ProjectRepository(db)

            # Patch flush to raise IntegrityError on the first call — this
            # simulates a concurrent insert winning the race inside the savepoint.
            # We disable autoflush on the session so that flush is only called
            # explicitly (inside the savepoint try block in toggle_user_pin).
            original_flush = db.flush
            flush_count = 0

            def flush_raising_once(*args, **kwargs):
                nonlocal flush_count
                flush_count += 1
                # flush #1 is from begin_nested() taking a snapshot — let it pass.
                # flush #2 is the explicit flush inside the savepoint try block
                # (after db.add) — this is where we simulate the race condition.
                if flush_count == 2:
                    raise IntegrityError("UNIQUE constraint", {}, None)
                return original_flush(*args, **kwargs)

            with patch.object(db, "flush", flush_raising_once):
                result = repo.toggle_user_pin(project_id, "sam_dev_user")

            # IntegrityError in savepoint means another transaction already pinned;
            # toggle_user_pin should catch it and return True
            assert result is True
        finally:
            db.close()

    def test_update_project_preserves_pin_state(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that editing a pinned project still returns is_pinned=True."""
        project_id = "pin-update-preserve"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Update Pin Preserve",
            user_id="sam_dev_user",
            description="Original description",
        )

        # Pin the project
        pin_resp = api_client.patch(f"/api/v1/projects/{project_id}/pin")
        assert pin_resp.status_code == 200
        assert pin_resp.json()["isPinned"] is True

        # Update the project name
        update_resp = api_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Pin Preserve"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["isPinned"] is True, (
            "Editing a pinned project should still return is_pinned=True"
        )
        assert update_resp.json()["name"] == "Updated Pin Preserve"
