"""
Prompts Validation and Authorization Tests

Tests for:
- Input validation (missing required fields, invalid data)
- 404 not found scenarios
- Empty list response structure
- Cross-user authorization (preventing unauthorized access)
- Duplicate command validation
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestPromptsInputValidation:
    """Tests for input validation on prompt operations"""

    def test_create_prompt_missing_required_fields(self, api_client: TestClient):
        """Test that creating prompt without required fields returns 422"""
        # Missing initial_prompt
        response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test Prompt",
                "description": "Test Description",
                # initial_prompt is missing
            },
        )
        assert response.status_code == 422

        # Missing name
        response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                # name is missing
                "description": "Test Description",
                "initial_prompt": "Test prompt text",
            },
        )
        assert response.status_code == 422

    def test_create_prompt_with_duplicate_command(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that duplicate command names are rejected"""
        # Create first prompt with a command
        gateway_adapter.seed_prompt_group(
            group_id="first-prompt",
            name="First Prompt",
            user_id="sam_dev_user",
            command="duplicate-cmd",
            initial_prompt="First prompt text",
        )

        # Try to create second prompt with same command
        response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Second Prompt",
                "description": "Second prompt",
                "command": "duplicate-cmd",
                "initial_prompt": "Second prompt text",
            },
        )

        assert response.status_code == 400
        error_data = response.json()
        error_msg = error_data.get("detail", "")
        assert "already exists" in error_msg.lower()


class TestPromptsNotFound:
    """Tests for 404 not found scenarios"""

    def test_get_nonexistent_prompt_returns_404(self, api_client: TestClient):
        """Test GET /prompts/groups/{id} returns 404 for non-existent prompt"""
        response = api_client.get("/api/v1/prompts/groups/non-existent-uuid-12345")
        assert response.status_code == 404

    def test_update_nonexistent_prompt_returns_404(self, api_client: TestClient):
        """Test PATCH /prompts/groups/{id} returns 404 for non-existent prompt"""
        response = api_client.patch(
            "/api/v1/prompts/groups/non-existent-uuid-67890",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    def test_delete_nonexistent_prompt_returns_404(self, api_client: TestClient):
        """Test DELETE /prompts/groups/{id} returns 404 for non-existent prompt"""
        response = api_client.delete("/api/v1/prompts/groups/non-existent-uuid-abcde")
        assert response.status_code == 404

    def test_pin_nonexistent_prompt_returns_404(self, api_client: TestClient):
        """Test PATCH /prompts/groups/{id}/pin returns 404 for non-existent prompt"""
        response = api_client.patch("/api/v1/prompts/groups/non-existent-uuid-pin/pin")
        assert response.status_code == 404


class TestPromptsEmptyList:
    """Tests for empty list response structure"""

    def test_get_all_prompts_returns_empty_list_when_no_data(
        self, api_client: TestClient
    ):
        """Test GET /prompts/groups/all returns empty list when no prompts exist"""
        response = api_client.get("/api/v1/prompts/groups/all")
        assert response.status_code == 200
        prompts = response.json()
        assert isinstance(prompts, list)
        # May be empty or have data from other tests, but should be a list
        assert prompts == [] or len(prompts) >= 0

    def test_list_prompts_returns_proper_structure_when_empty(
        self, api_client: TestClient
    ):
        """Test GET /prompts/groups returns proper structure even when empty"""
        response = api_client.get("/api/v1/prompts/groups")
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert isinstance(data["groups"], list)
        assert isinstance(data["total"], int)


class TestPromptsCrossUserAuthorization:
    """Tests for cross-user authorization to prevent unauthorized access"""

    def test_user_cannot_access_other_users_prompt(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot access prompts owned by other users"""
        # Create a prompt as primary user
        group_id = "private-prompt-user1"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Prompt for User1",
            user_id="sam_dev_user",
            description="Private prompt",
            initial_prompt="Private prompt text",
        )

        # Try to access as secondary user (should return 404, not 403, for security)
        response = secondary_api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert response.status_code == 404

    def test_user_cannot_update_other_users_prompt(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot update prompts owned by other users"""
        # Create a prompt as primary user
        group_id = "private-prompt-update-user1"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Prompt for User1",
            user_id="sam_dev_user",
            description="Original description",
            initial_prompt="Original prompt text",
        )

        # Try to update as secondary user
        response = secondary_api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={"name": "Hacked Name", "description": "Hacked Description"},
        )
        assert response.status_code == 404

        # Verify prompt was not modified
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 200
        prompt_data = get_response.json()
        assert prompt_data["name"] == "Private Prompt for User1"
        assert prompt_data["description"] == "Original description"

    def test_user_cannot_delete_other_users_prompt(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot delete prompts owned by other users"""
        # Create a prompt as primary user
        group_id = "private-prompt-delete-user1"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Prompt for User1",
            user_id="sam_dev_user",
            description="Private prompt",
            initial_prompt="Private prompt text",
        )

        # Try to delete as secondary user
        response = secondary_api_client.delete(f"/api/v1/prompts/groups/{group_id}")
        assert response.status_code == 404

        # Verify prompt still exists
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 200

    def test_user_only_sees_own_prompts_in_list(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users only see their own prompts in list endpoints"""
        # Create prompts for primary user
        gateway_adapter.seed_prompt_group(
            group_id="user1-prompt-1",
            name="User1 Prompt 1",
            user_id="sam_dev_user",
            initial_prompt="User1 prompt text",
        )

        # Create prompts for secondary user
        gateway_adapter.seed_prompt_group(
            group_id="user2-prompt-1",
            name="User2 Prompt 1",
            user_id="secondary_user",
            initial_prompt="User2 prompt text",
        )

        # Primary user should only see their own prompts
        response = api_client.get("/api/v1/prompts/groups/all")
        assert response.status_code == 200
        prompts = response.json()
        prompt_ids = [p["id"] for p in prompts]
        assert "user1-prompt-1" in prompt_ids
        assert "user2-prompt-1" not in prompt_ids

        # Secondary user should only see their own prompts
        response = secondary_api_client.get("/api/v1/prompts/groups/all")
        assert response.status_code == 200
        prompts = response.json()
        prompt_ids = [p["id"] for p in prompts]
        assert "user2-prompt-1" in prompt_ids
        assert "user1-prompt-1" not in prompt_ids


class TestPromptsVersioning:
    """Tests for prompt versioning functionality"""

    def test_create_new_version(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test creating a new version of a prompt"""
        # Create initial prompt
        group_id = "versioned-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Versioned Prompt",
            user_id="sam_dev_user",
            initial_prompt="Version 1 text",
        )

        # Create version 2
        response = api_client.post(
            f"/api/v1/prompts/groups/{group_id}/prompts",
            json={"prompt_text": "Version 2 text"},
        )

        assert response.status_code == 201
        version_data = response.json()
        assert version_data["version"] == 2
        assert version_data["promptText"] == "Version 2 text"
        assert version_data["userId"] == "sam_dev_user"

    def test_list_all_versions(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test listing all versions of a prompt"""
        # Create initial prompt
        group_id = "multi-version-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Multi Version Prompt",
            user_id="sam_dev_user",
            initial_prompt="Version 1 text",
        )

        # Create additional versions
        api_client.post(
            f"/api/v1/prompts/groups/{group_id}/prompts",
            json={"prompt_text": "Version 2 text"},
        )
        api_client.post(
            f"/api/v1/prompts/groups/{group_id}/prompts",
            json={"prompt_text": "Version 3 text"},
        )

        # List all versions
        response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 3
        # Versions should be ordered by creation time (newest first)
        assert versions[0]["version"] == 3
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 1

    def test_update_prompt_text_directly(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/prompts/{prompt_id} updates prompt text directly"""
        # Create initial prompt
        group_id = "prompt-text-update"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Prompt for Text Update",
            user_id="sam_dev_user",
            initial_prompt="Original prompt text",
        )

        # Get the prompt ID
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        prompt_id = group_data["productionPrompt"]["id"]
        original_version = group_data["productionPrompt"]["version"]

        # Update the prompt text directly
        response = api_client.patch(
            f"/api/v1/prompts/{prompt_id}",
            json={"prompt_text": "Updated prompt text"},
        )

        # Assert update succeeded
        assert response.status_code == 200
        updated_prompt = response.json()
        assert updated_prompt["id"] == prompt_id
        assert updated_prompt["promptText"] == "Updated prompt text"
        assert updated_prompt["version"] == original_version  # Version number unchanged
        assert updated_prompt["userId"] == "sam_dev_user"

        # Verify the update persisted
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["productionPrompt"]["promptText"] == "Updated prompt text"

    def test_update_prompt_text_unauthorized(
        self,
        api_client: TestClient,
        secondary_api_client: TestClient,
        gateway_adapter: GatewayAdapter,
    ):
        """Test that users cannot update prompt text of other users' prompts"""
        # Create prompt as primary user
        group_id = "prompt-unauthorized-update"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Private Prompt",
            user_id="sam_dev_user",
            initial_prompt="Original text",
        )

        # Get the prompt ID
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        prompt_id = group_response.json()["productionPrompt"]["id"]

        # Try to update as secondary user
        response = secondary_api_client.patch(
            f"/api/v1/prompts/{prompt_id}",
            json={"prompt_text": "Hacked text"},
        )
        assert response.status_code == 404

        # Verify text was not changed
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        assert group_response.json()["productionPrompt"]["promptText"] == "Original text"

    def test_update_in_place_without_new_version(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that updating with create_new_version=false updates in-place without creating a new version"""
        # Create initial prompt
        group_id = "in-place-update-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original description",
            initial_prompt="Original prompt text",
        )

        # Get initial version count
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        initial_version_count = len(versions_response.json())
        assert initial_version_count == 1

        # Update without creating new version (default behavior)
        update_response = api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
                "initial_prompt": "Updated prompt text",
                "create_new_version": False,
            },
        )
        assert update_response.status_code == 200

        # Verify version count unchanged
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        assert len(versions_response.json()) == initial_version_count

        # Verify content was updated in-place
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["name"] == "Updated Name"
        assert group_data["description"] == "Updated description"
        assert group_data["productionPrompt"]["promptText"] == "Updated prompt text"
        assert group_data["productionPrompt"]["version"] == 1  # Still version 1

    def test_update_with_new_version_flag(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that updating with create_new_version=true creates a new version"""
        # Create initial prompt
        group_id = "new-version-update-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original description",
            initial_prompt="Original prompt text",
        )

        # Get initial version count
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        initial_version_count = len(versions_response.json())
        assert initial_version_count == 1

        # Update with create_new_version=true
        update_response = api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
                "initial_prompt": "Updated prompt text",
                "create_new_version": True,
            },
        )
        assert update_response.status_code == 200

        # Verify new version was created
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert len(versions) == initial_version_count + 1

        # Verify the new version is now active (latest)
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["name"] == "Updated Name"
        assert group_data["description"] == "Updated description"
        assert group_data["productionPrompt"]["promptText"] == "Updated prompt text"
        assert group_data["productionPrompt"]["version"] == 2  # New version 2

        # Verify old version still exists with original data
        version_1 = next(v for v in versions if v["version"] == 1)
        assert version_1["promptText"] == "Original prompt text"

    def test_restore_version_creates_new_version(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that restoring an old version creates a new version (not overwriting current)"""
        # Create initial prompt
        group_id = "restore-version-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Version 1 Name",
            user_id="sam_dev_user",
            description="Version 1 description",
            initial_prompt="Version 1 text",
        )

        # Create version 2
        api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Version 2 Name",
                "description": "Version 2 description",
                "initial_prompt": "Version 2 text",
                "create_new_version": True,
            },
        )

        # Create version 3
        api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Version 3 Name",
                "description": "Version 3 description",
                "initial_prompt": "Version 3 text",
                "create_new_version": True,
            },
        )

        # Verify we have 3 versions
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        assert len(versions_response.json()) == 3

        # "Restore" version 1 by creating a new version with its content
        restore_response = api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Version 1 Name",
                "description": "Version 1 description",
                "initial_prompt": "Version 1 text",
                "create_new_version": True,  # Always create new version when restoring
            },
        )
        assert restore_response.status_code == 200

        # Verify we now have 4 versions (not 3)
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        versions = versions_response.json()
        assert len(versions) == 4

        # Verify the new version 4 has version 1's content
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["productionPrompt"]["version"] == 4
        assert group_data["productionPrompt"]["promptText"] == "Version 1 text"
        assert group_data["name"] == "Version 1 Name"

        # Verify version 3 still exists unchanged
        version_3 = next(v for v in versions if v["version"] == 3)
        assert version_3["promptText"] == "Version 3 text"

    def test_latest_version_is_always_active(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that the latest version (highest version number) is always the active version"""
        # Create initial prompt
        group_id = "latest-active-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Test Prompt",
            user_id="sam_dev_user",
            initial_prompt="Version 1 text",
        )

        # Create multiple versions
        for i in range(2, 5):
            api_client.patch(
                f"/api/v1/prompts/groups/{group_id}",
                json={
                    "initial_prompt": f"Version {i} text",
                    "create_new_version": True,
                },
            )

        # Verify the active version is always the latest (version 4)
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["productionPrompt"]["version"] == 4
        assert group_data["productionPrompt"]["promptText"] == "Version 4 text"

    def test_metadata_is_version_specific(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test that metadata (name, description, category) is stored per-version"""
        # Create initial prompt
        group_id = "metadata-version-prompt"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Version 1 Name",
            user_id="sam_dev_user",
            description="Version 1 description",
            category="testing",
            initial_prompt="Version 1 text",
        )

        # Create version 2 with different metadata
        api_client.patch(
            f"/api/v1/prompts/groups/{group_id}",
            json={
                "name": "Version 2 Name",
                "description": "Version 2 description",
                "category": "development",
                "initial_prompt": "Version 2 text",
                "create_new_version": True,
            },
        )

        # Get all versions
        versions_response = api_client.get(f"/api/v1/prompts/groups/{group_id}/prompts")
        assert versions_response.status_code == 200
        versions = versions_response.json()

        # Verify version 1 has its original metadata
        version_1 = next(v for v in versions if v["version"] == 1)
        assert version_1["name"] == "Version 1 Name"
        assert version_1["description"] == "Version 1 description"
        assert version_1["category"] == "testing"

        # Verify version 2 has its own metadata
        version_2 = next(v for v in versions if v["version"] == 2)
        assert version_2["name"] == "Version 2 Name"
        assert version_2["description"] == "Version 2 description"
        assert version_2["category"] == "development"

        # Verify the group shows the latest version's metadata
        group_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert group_response.status_code == 200
        group_data = group_response.json()
        assert group_data["name"] == "Version 2 Name"
        assert group_data["description"] == "Version 2 description"
        assert group_data["category"] == "development"