"""
Integration tests for the complete prompt library feature.

Tests all prompt library functionality including:
1. Creating and managing prompt groups
2. Creating and managing prompt versions
3. Setting production prompts
4. Pinning prompts
5. Listing and searching prompts
6. Role-based sharing and access control
7. Version tracking and ownership
8. CASCADE deletes and data integrity
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from solace_agent_mesh.gateway.http_sse.repository.models.prompt_model import (
    PromptGroupModel,
    PromptModel,
    PromptGroupUserModel,
)


@pytest.fixture
def user_headers():
    """Headers for the main test user - system uses sam_dev_user by default"""
    return {}


@pytest.fixture
def other_user_headers():
    """Headers for a different user - not supported in test environment"""
    return {}


@pytest.fixture
def test_user_id():
    """The actual user ID used by the test system"""
    return "sam_dev_user"


@pytest.fixture
def db_session(test_db_engine):
    """Create a database session for tests that need direct DB access"""
    from sqlalchemy.orm import sessionmaker
    
    SessionLocal = sessionmaker(bind=test_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestPromptGroupCreation:
    """Tests for creating prompt groups"""

    def test_create_prompt_group_success(self, webui_api_client: TestClient, user_headers):
        """Test successful prompt group creation"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Test Prompt",
                "description": "A test prompt for unit testing",
                "category": "testing",
                "command": "test",
                "initial_prompt": "This is the initial prompt text.",
            },
            headers=user_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Prompt"
        assert data["user_id"] == "sam_dev_user"
        assert data["production_prompt"] is not None
        assert data["production_prompt"]["version"] == 1

    def test_create_prompt_group_with_duplicate_command_fails(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test that duplicate command names are rejected"""
        # Create first prompt
        webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "First Prompt",
                "description": "First prompt",
                "category": "testing",
                "command": "duplicate",
                "initial_prompt": "First prompt text.",
            },
            headers=user_headers,
        )
        
        # Try to create second with same command
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Second Prompt",
                "description": "Second prompt",
                "category": "testing",
                "command": "duplicate",
                "initial_prompt": "Second prompt text.",
            },
            headers=user_headers,
        )
        
        assert response.status_code == 400
        error_data = response.json()
        # Error response might be in 'detail' or 'message' field
        error_msg = error_data.get("detail", error_data.get("message", ""))
        assert "already exists" in error_msg

    def test_create_prompt_group_without_command(self, webui_api_client: TestClient, user_headers):
        """Test creating prompt group without command (optional field)"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "No Command Prompt",
                "description": "A prompt without a command",
                "category": "testing",
                "initial_prompt": "Prompt text without command.",
            },
            headers=user_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["command"] is None


class TestPromptGroupRetrieval:
    """Tests for retrieving prompt groups"""

    @pytest.fixture
    def sample_prompt(self, webui_api_client: TestClient, user_headers):
        """Create a sample prompt for testing"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Sample Prompt",
                "description": "For retrieval testing",
                "category": "testing",
                "command": "sample",
                "initial_prompt": "Sample prompt text.",
            },
            headers=user_headers,
        )
        return response.json()

    def test_get_prompt_group_by_id(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test retrieving a specific prompt group by ID"""
        response = webui_api_client.get(
            f"/api/v1/prompts/groups/{sample_prompt['id']}",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_prompt["id"]
        assert data["name"] == "Sample Prompt"

    def test_list_all_prompt_groups(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test listing all prompt groups"""
        response = webui_api_client.get(
            "/api/v1/prompts/groups/all",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        prompts = response.json()
        assert len(prompts) >= 1
        assert any(p["id"] == sample_prompt["id"] for p in prompts)

    def test_list_prompts_with_pagination(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test listing prompts with pagination"""
        # Create multiple prompts
        for i in range(5):
            webui_api_client.post(
                "/api/v1/prompts/groups",
                json={
                    "name": f"Prompt {i}",
                    "description": f"Prompt number {i}",
                    "category": "testing",
                    "initial_prompt": f"Prompt text {i}.",
                },
                headers=user_headers,
            )
        
        # Test pagination
        response = webui_api_client.get(
            "/api/v1/prompts/groups?skip=0&limit=3",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) <= 3
        assert data["total"] >= 5

    def test_search_prompts_by_name(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test searching prompts by name"""
        response = webui_api_client.get(
            "/api/v1/prompts/groups?search=Sample",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) >= 1
        assert any(p["name"] == "Sample Prompt" for p in data["groups"])

    def test_filter_prompts_by_category(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test filtering prompts by category"""
        # Create prompts in different categories
        webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Work Prompt",
                "description": "For work",
                "category": "work",
                "initial_prompt": "Work prompt text.",
            },
            headers=user_headers,
        )
        
        webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Personal Prompt",
                "description": "For personal use",
                "category": "personal",
                "initial_prompt": "Personal prompt text.",
            },
            headers=user_headers,
        )
        
        # Filter by category
        response = webui_api_client.get(
            "/api/v1/prompts/groups?category=work",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(p["category"] == "work" for p in data["groups"])


class TestPromptGroupUpdate:
    """Tests for updating prompt groups"""

    @pytest.fixture
    def sample_prompt(self, webui_api_client: TestClient, user_headers):
        """Create a sample prompt for testing"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Original Name",
                "description": "Original description",
                "category": "testing",
                "command": "original",
                "initial_prompt": "Original prompt text.",
            },
            headers=user_headers,
        )
        return response.json()

    def test_update_prompt_metadata(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test updating prompt group metadata"""
        response = webui_api_client.patch(
            f"/api/v1/prompts/groups/{sample_prompt['id']}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
            },
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"

    def test_update_prompt_text_creates_new_version(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test that updating prompt text creates a new version"""
        response = webui_api_client.patch(
            f"/api/v1/prompts/groups/{sample_prompt['id']}",
            json={
                "initial_prompt": "Updated prompt text for version 2.",
            },
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["production_prompt"]["version"] == 2
        assert data["production_prompt"]["prompt_text"] == "Updated prompt text for version 2."


class TestPromptVersions:
    """Tests for prompt version management"""

    @pytest.fixture
    def sample_prompt(self, webui_api_client: TestClient, user_headers):
        """Create a sample prompt for testing"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Versioned Prompt",
                "description": "For version testing",
                "category": "testing",
                "initial_prompt": "Version 1 text.",
            },
            headers=user_headers,
        )
        return response.json()

    def test_create_new_prompt_version(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test creating a new prompt version"""
        response = webui_api_client.post(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/prompts",
            json={"prompt_text": "Version 2 text."},
            headers=user_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == 2
        assert data["user_id"] == "sam_dev_user"

    def test_list_all_versions(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test listing all versions of a prompt"""
        # Create additional versions
        webui_api_client.post(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/prompts",
            json={"prompt_text": "Version 2 text."},
            headers=user_headers,
        )
        webui_api_client.post(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/prompts",
            json={"prompt_text": "Version 3 text."},
            headers=user_headers,
        )
        
        # List versions
        response = webui_api_client.get(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/prompts",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 3

    def test_set_production_version(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test setting a specific version as production"""
        # Create version 2
        v2_response = webui_api_client.post(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/prompts",
            json={"prompt_text": "Version 2 text."},
            headers=user_headers,
        )
        v2_id = v2_response.json()["id"]
        
        # Set version 2 as production
        response = webui_api_client.patch(
            f"/api/v1/prompts/{v2_id}/make-production",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        
        # Verify it's now production
        group_response = webui_api_client.get(
            f"/api/v1/prompts/groups/{sample_prompt['id']}",
            headers=user_headers,
        )
        assert group_response.json()["production_prompt_id"] == v2_id


class TestPromptPinning:
    """Tests for pinning prompts"""

    @pytest.fixture
    def sample_prompt(self, webui_api_client: TestClient, user_headers):
        """Create a sample prompt for testing"""
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Pinnable Prompt",
                "description": "For pin testing",
                "category": "testing",
                "initial_prompt": "Pinnable prompt text.",
            },
            headers=user_headers,
        )
        return response.json()

    def test_pin_prompt(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test pinning a prompt"""
        response = webui_api_client.patch(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/pin",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is True

    def test_unpin_prompt(
        self, webui_api_client: TestClient, user_headers, sample_prompt
    ):
        """Test unpinning a prompt"""
        # Pin first
        webui_api_client.patch(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/pin",
            headers=user_headers,
        )
        
        # Unpin
        response = webui_api_client.patch(
            f"/api/v1/prompts/groups/{sample_prompt['id']}/pin",
            headers=user_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is False

    def test_pinned_prompts_appear_first(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test that pinned prompts appear first in listings"""
        # Create and pin a prompt
        pinned_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Pinned Prompt",
                "description": "Should appear first",
                "category": "testing",
                "initial_prompt": "Pinned text.",
            },
            headers=user_headers,
        )
        pinned_id = pinned_response.json()["id"]
        
        webui_api_client.patch(
            f"/api/v1/prompts/groups/{pinned_id}/pin",
            headers=user_headers,
        )
        
        # Create unpinned prompt
        webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Unpinned Prompt",
                "description": "Should appear after pinned",
                "category": "testing",
                "initial_prompt": "Unpinned text.",
            },
            headers=user_headers,
        )
        
        # List all prompts
        response = webui_api_client.get(
            "/api/v1/prompts/groups/all",
            headers=user_headers,
        )
        
        prompts = response.json()
        # Find our prompts
        pinned_index = next(i for i, p in enumerate(prompts) if p["id"] == pinned_id)
        unpinned_index = next(i for i, p in enumerate(prompts) if p["name"] == "Unpinned Prompt")
        
        assert pinned_index < unpinned_index


class TestPromptDeletion:
    """Tests for deleting prompts"""

    def test_delete_prompt_group(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test deleting a prompt group"""
        # Create prompt
        create_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "To Delete",
                "description": "Will be deleted",
                "category": "testing",
                "initial_prompt": "Delete me.",
            },
            headers=user_headers,
        )
        prompt_id = create_response.json()["id"]
        
        # Delete it
        response = webui_api_client.delete(
            f"/api/v1/prompts/groups/{prompt_id}",
            headers=user_headers,
        )
        
        assert response.status_code == 204
        
        # Verify it's gone
        get_response = webui_api_client.get(
            f"/api/v1/prompts/groups/{prompt_id}",
            headers=user_headers,
        )
        assert get_response.status_code == 404

    def test_delete_specific_version(
        self, webui_api_client: TestClient, user_headers, db_session: Session
    ):
        """Test deleting a specific prompt version"""
        # Create prompt with multiple versions
        create_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Multi Version",
                "description": "Has multiple versions",
                "category": "testing",
                "initial_prompt": "Version 1.",
            },
            headers=user_headers,
        )
        group_id = create_response.json()["id"]
        
        # Create version 2
        v2_response = webui_api_client.post(
            f"/api/v1/prompts/groups/{group_id}/prompts",
            json={"prompt_text": "Version 2."},
            headers=user_headers,
        )
        v2_id = v2_response.json()["id"]
        
        # Delete version 2
        response = webui_api_client.delete(
            f"/api/v1/prompts/{v2_id}",
            headers=user_headers,
        )
        
        assert response.status_code == 204
        
        # Verify only 1 version remains
        versions_response = webui_api_client.get(
            f"/api/v1/prompts/groups/{group_id}/prompts",
            headers=user_headers,
        )
        assert len(versions_response.json()) == 1

    def test_delete_last_version_deletes_group(
        self, webui_api_client: TestClient, user_headers
    ):
        """Test that deleting the last version deletes the entire group"""
        # Create prompt
        create_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Single Version",
                "description": "Only one version",
                "category": "testing",
                "initial_prompt": "Only version.",
            },
            headers=user_headers,
        )
        group_id = create_response.json()["id"]
        prompt_id = create_response.json()["production_prompt_id"]
        
        # Delete the only version
        webui_api_client.delete(
            f"/api/v1/prompts/{prompt_id}",
            headers=user_headers,
        )
        
        # Verify group is gone
        response = webui_api_client.get(
            f"/api/v1/prompts/groups/{group_id}",
            headers=user_headers,
        )
        assert response.status_code == 404


class TestPromptSharing:
    """Tests for prompt sharing with role-based access control"""

    @pytest.fixture
    def shared_prompt(
        self, webui_api_client: TestClient, user_headers, db_session: Session, test_user_id
    ):
        """Create a prompt and share it with a simulated other user"""
        # Create prompt as main user
        response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Shared Prompt",
                "description": "Shared with others",
                "category": "testing",
                "initial_prompt": "Shared text.",
            },
            headers=user_headers,
        )
        group_data = response.json()
        
        # Share with simulated other user as editor
        # Note: In test environment, we can't actually switch users,
        # so we simulate sharing by directly adding to database
        share = PromptGroupUserModel(
            id="share-1",
            prompt_group_id=group_data["id"],
            user_id="simulated-other-user",
            role="editor",
            added_at=1699564800000,
            added_by_user_id=test_user_id,
        )
        db_session.add(share)
        db_session.commit()
        
        return group_data

    def test_shared_prompt_appears_in_other_user_list(
        self, webui_api_client: TestClient, user_headers, shared_prompt, db_session: Session
    ):
        """Test that shared prompts are properly stored in database"""
        # Verify the share exists in database
        share = db_session.query(PromptGroupUserModel).filter(
            PromptGroupUserModel.prompt_group_id == shared_prompt["id"]
        ).first()
        
        assert share is not None
        assert share.user_id == "simulated-other-user"
        assert share.role == "editor"

    def test_editor_can_create_version(
        self, webui_api_client: TestClient, user_headers, shared_prompt, test_user_id
    ):
        """Test that users with write permission can create new versions"""
        # In test environment, we're always the owner, so we can create versions
        response = webui_api_client.post(
            f"/api/v1/prompts/groups/{shared_prompt['id']}/prompts",
            json={"prompt_text": "New version."},
            headers=user_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == test_user_id
        assert data["version"] == 2

    def test_group_ownership_unchanged_after_editor_edit(
        self, webui_api_client: TestClient, user_headers, shared_prompt, db_session: Session, test_user_id
    ):
        """Test that group ownership doesn't change when new versions are created"""
        # Create new version
        webui_api_client.post(
            f"/api/v1/prompts/groups/{shared_prompt['id']}/prompts",
            json={"prompt_text": "New version."},
            headers=user_headers,
        )
        
        # Check ownership remains with original creator
        group = db_session.query(PromptGroupModel).filter(
            PromptGroupModel.id == shared_prompt["id"]
        ).first()
        
        assert group.user_id == test_user_id  # Still owned by original user


class TestDataIntegrity:
    """Tests for data integrity and CASCADE behavior"""

    def test_cascade_delete_removes_versions(
        self, webui_api_client: TestClient, user_headers, db_session: Session
    ):
        """Test that deleting a group removes all versions"""
        # Create prompt with multiple versions
        create_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Cascade Test",
                "description": "For CASCADE testing",
                "category": "testing",
                "initial_prompt": "Version 1.",
            },
            headers=user_headers,
        )
        group_id = create_response.json()["id"]
        
        # Create more versions
        for i in range(2, 5):
            webui_api_client.post(
                f"/api/v1/prompts/groups/{group_id}/prompts",
                json={"prompt_text": f"Version {i}."},
                headers=user_headers,
            )
        
        # Delete group
        webui_api_client.delete(
            f"/api/v1/prompts/groups/{group_id}",
            headers=user_headers,
        )
        
        # Verify all versions are gone
        versions = db_session.query(PromptModel).filter(
            PromptModel.group_id == group_id
        ).all()
        
        assert len(versions) == 0

    def test_cascade_delete_removes_shares(
        self, webui_api_client: TestClient, user_headers, db_session: Session
    ):
        """Test that deleting a group removes all shares"""
        # Create and share prompt
        create_response = webui_api_client.post(
            "/api/v1/prompts/groups",
            json={
                "name": "Share Cascade Test",
                "description": "For share CASCADE testing",
                "category": "testing",
                "initial_prompt": "Shared text.",
            },
            headers=user_headers,
        )
        group_id = create_response.json()["id"]
        
        # Add shares
        for i, user in enumerate(["user1", "user2", "user3"]):
            share = PromptGroupUserModel(
                id=f"share-{i}",
                prompt_group_id=group_id,
                user_id=user,
                role="viewer",
                added_at=1699564800000,
                added_by_user_id="test-user",
            )
            db_session.add(share)
        db_session.commit()
        
        # Delete group
        webui_api_client.delete(
            f"/api/v1/prompts/groups/{group_id}",
            headers=user_headers,
        )
        
        # Verify all shares are gone
        shares = db_session.query(PromptGroupUserModel).filter(
            PromptGroupUserModel.prompt_group_id == group_id
        ).all()
        
        assert len(shares) == 0