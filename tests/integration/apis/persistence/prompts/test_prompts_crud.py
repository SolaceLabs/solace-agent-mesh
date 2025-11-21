"""
Prompts CRUD API Tests

Tests for prompt library lifecycle operations including:
- Creating prompt groups
- Reading prompts (list and individual)
- Updating prompts
- Deleting prompts
- Pagination and search
"""

import pytest
from fastapi.testclient import TestClient
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestPromptsCRUD:
    """Test basic CRUD operations for prompts"""

    def test_get_prompt_group_by_id(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test GET /api/v1/prompts/groups/{id} returns specific prompt group"""
        # Setup: Create a prompt group
        group_id = "test-prompt-123"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Specific Test Prompt",
            user_id="sam_dev_user",
            description="A specific prompt for testing",
            category="testing",
            command="test-cmd",
            initial_prompt="You are a test assistant",
        )

        # Act: Get the prompt group
        response = api_client.get(f"/api/v1/prompts/groups/{group_id}")

        # Assert
        assert response.status_code == 200
        prompt_data = response.json()
        assert prompt_data["id"] == group_id
        assert prompt_data["name"] == "Specific Test Prompt"
        assert prompt_data["userId"] == "sam_dev_user"
        assert prompt_data["description"] == "A specific prompt for testing"
        assert prompt_data["category"] == "testing"
        assert prompt_data["command"] == "test-cmd"
        assert prompt_data["productionPrompt"] is not None
        assert prompt_data["productionPrompt"]["promptText"] == "You are a test assistant"

    def test_get_all_prompts_with_data(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test GET /api/v1/prompts/groups/all returns seeded prompts correctly"""
        # Setup: Create multiple prompt groups
        gateway_adapter.seed_prompt_group(
            group_id="test-prompt-unique-001",
            name="Test Prompt 1",
            user_id="sam_dev_user",
            description="First test prompt",
            category="testing",
            command="test1",
            initial_prompt="You are a helpful assistant for prompt 1",
        )
        gateway_adapter.seed_prompt_group(
            group_id="test-prompt-unique-002",
            name="Test Prompt 2",
            user_id="sam_dev_user",
            description="Second test prompt",
            category="development",
            initial_prompt="You are a helpful assistant for prompt 2",
        )

        # Act: Get all prompts
        response = api_client.get("/api/v1/prompts/groups/all")

        # Assert
        assert response.status_code == 200
        prompts = response.json()
        assert isinstance(prompts, list)

        # Verify our seeded prompts exist
        prompt_ids = [p["id"] for p in prompts]
        assert "test-prompt-unique-001" in prompt_ids
        assert "test-prompt-unique-002" in prompt_ids

        # Verify prompt details
        prompt_1 = next(p for p in prompts if p["id"] == "test-prompt-unique-001")
        assert prompt_1["name"] == "Test Prompt 1"
        assert prompt_1["description"] == "First test prompt"
        assert prompt_1["category"] == "testing"

        prompt_2 = next(p for p in prompts if p["id"] == "test-prompt-unique-002")
        assert prompt_2["name"] == "Test Prompt 2"
        assert prompt_2["description"] == "Second test prompt"
        assert prompt_2["category"] == "development"

    def test_create_prompt_group(self, api_client: TestClient):
        """Test POST /api/v1/prompts/groups creates new prompt group"""
        # Act: Create a new prompt group
        response = api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "New Prompt",
                "description": "A newly created prompt",
                "category": "testing",
                "command": "new-cmd",
                "initial_prompt": "You are a new assistant",
            },
        )

        # Assert
        assert response.status_code == 201
        prompt_data = response.json()
        assert "id" in prompt_data
        assert prompt_data["name"] == "New Prompt"
        assert prompt_data["description"] == "A newly created prompt"
        assert prompt_data["category"] == "testing"
        assert prompt_data["command"] == "new-cmd"
        assert prompt_data["userId"] == "sam_dev_user"
        assert prompt_data["productionPrompt"] is not None
        assert prompt_data["productionPrompt"]["version"] == 1
        assert prompt_data["productionPrompt"]["promptText"] == "You are a new assistant"

    def test_update_prompt_metadata(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test PATCH /api/v1/prompts/groups/{id} updates metadata successfully"""
        # Setup: Create a prompt group
        group_id = "prompt-to-update"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Original Name",
            user_id="sam_dev_user",
            description="Original description",
            category="testing",
            command="original-cmd",
            initial_prompt="Original prompt text",
        )

        # Act: Update the prompt metadata
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
            "category": "development",
        }
        response = api_client.patch(f"/api/v1/prompts/groups/{group_id}", json=update_data)

        # Assert: Update response
        assert response.status_code == 200
        prompt_data = response.json()
        assert prompt_data["id"] == group_id
        assert prompt_data["name"] == "Updated Name"
        assert prompt_data["description"] == "Updated description"
        assert prompt_data["category"] == "development"
        assert prompt_data["command"] == "original-cmd"  # Command unchanged
        assert prompt_data["userId"] == "sam_dev_user"

        # Verify update persisted
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 200
        persisted_data = get_response.json()
        assert persisted_data["name"] == "Updated Name"
        assert persisted_data["description"] == "Updated description"
        assert persisted_data["category"] == "development"

    def test_delete_prompt_group(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test DELETE /api/v1/prompts/groups/{id} removes prompt group successfully"""
        # Setup: Create a prompt group
        group_id = "prompt-to-delete"
        gateway_adapter.seed_prompt_group(
            group_id=group_id,
            name="Prompt To Delete",
            user_id="sam_dev_user",
            description="This prompt will be deleted",
            initial_prompt="Delete me",
        )

        # Act: Delete the prompt group
        response = api_client.delete(f"/api/v1/prompts/groups/{group_id}")

        # Assert: Delete succeeds
        assert response.status_code == 204

        # Verify prompt group is deleted (should return 404)
        get_response = api_client.get(f"/api/v1/prompts/groups/{group_id}")
        assert get_response.status_code == 404


class TestPromptsPagination:
    """Test pagination and search functionality for prompts listing"""

    def test_pagination(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test pagination works correctly for GET /api/v1/prompts/groups"""
        # Setup: Create 5 prompt groups
        for i in range(1, 6):
            gateway_adapter.seed_prompt_group(
                group_id=f"pagination-prompt-{i}",
                name=f"Pagination Prompt {i}",
                user_id="sam_dev_user",
                category="testing",
                initial_prompt=f"Prompt text {i}",
            )

        # Test pagination
        response = api_client.get("/api/v1/prompts/groups?skip=0&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert "total" in data
        assert len(data["groups"]) <= 3
        assert data["total"] >= 5

    def test_search_prompts_by_name(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test searching prompts by name"""
        # Setup: Create prompts with distinct names
        gateway_adapter.seed_prompt_group(
            group_id="searchable-prompt-1",
            name="Searchable Test Prompt",
            user_id="sam_dev_user",
            description="For search testing",
            initial_prompt="Search me",
        )
        gateway_adapter.seed_prompt_group(
            group_id="other-prompt-1",
            name="Other Prompt",
            user_id="sam_dev_user",
            description="Not searchable",
            initial_prompt="Don't search me",
        )

        # Act: Search for "Searchable"
        response = api_client.get("/api/v1/prompts/groups?search=Searchable")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        # At least one result should match our searchable prompt
        searchable_found = any(p["name"] == "Searchable Test Prompt" for p in data["groups"])
        assert searchable_found, "Searchable Test Prompt should be in search results"

    def test_filter_prompts_by_category(
        self, api_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        """Test filtering prompts by category"""
        # Setup: Create prompts in different categories
        gateway_adapter.seed_prompt_group(
            group_id="work-prompt-1",
            name="Work Prompt",
            user_id="sam_dev_user",
            category="work",
            initial_prompt="Work prompt text",
        )
        gateway_adapter.seed_prompt_group(
            group_id="personal-prompt-1",
            name="Personal Prompt",
            user_id="sam_dev_user",
            category="personal",
            initial_prompt="Personal prompt text",
        )

        # Act: Filter by category
        response = api_client.get("/api/v1/prompts/groups?category=work")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(p["category"] == "work" for p in data["groups"])
        assert any(p["name"] == "Work Prompt" for p in data["groups"])
        assert not any(p["name"] == "Personal Prompt" for p in data["groups"])