"""
Projects Pin/Star API Tests

Tests for the PATCH /api/v1/projects/{id}/pin endpoint that toggles
the is_pinned status of a project.
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


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
        """Test PATCH /api/v1/projects/{id}/pin returns 404 for another user's project"""
        # Setup: Create a project owned by a different user
        project_id = "pin-test-project-other-user"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Other User Project",
            user_id="other_user",
        )

        # Act: Try to pin as sam_dev_user (the default test user)
        response = api_client.patch(f"/api/v1/projects/{project_id}/pin")

        # Assert: Should return 404 (project not found for this user)
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
        from unittest.mock import patch
        from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService

        project_id = "pin-isolation-shared"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Shared Isolation Project",
            user_id="sam_dev_user",
        )

        # Simulate shared access: grant secondary_user view access to this project
        original_has_view_access = ProjectService._has_view_access

        def _patched_has_view_access(self, db, pid, uid):
            if pid == project_id and uid == "secondary_user":
                return True
            return original_has_view_access(self, db, pid, uid)

        with patch.object(ProjectService, "_has_view_access", _patched_has_view_access):
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
        from unittest.mock import patch
        from solace_agent_mesh.gateway.http_sse.services.project_service import ProjectService

        project_id = "pin-test-shared-collaborator"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Collaborator Pin Project",
            user_id="sam_dev_user",
        )

        # Simulate shared access for secondary_user
        original_has_view_access = ProjectService._has_view_access

        def _patched_has_view_access(self, db, pid, uid):
            if pid == project_id and uid == "secondary_user":
                return True
            return original_has_view_access(self, db, pid, uid)

        with patch.object(ProjectService, "_has_view_access", _patched_has_view_access):
            # Non-owner collaborator toggles pin — should succeed with 200
            response = secondary_api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert response.status_code == 200
            assert response.json()["id"] == project_id
            assert response.json()["isPinned"] is True

            # Toggle again to unpin
            response2 = secondary_api_client.patch(f"/api/v1/projects/{project_id}/pin")
            assert response2.status_code == 200
            assert response2.json()["isPinned"] is False
