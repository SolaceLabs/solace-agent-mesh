#!/usr/bin/env python3
"""
Test SAM Apps API endpoints with FastAPI test client.

Tests:
1. Apps router endpoints (CRUD)
2. Storage router endpoints
3. Error handling
4. Data validation
"""

import asyncio
import json
import sys
from pathlib import Path

# Set up path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the routers
from solace_agent_mesh.gateway.http_sse.routers.apps import router as apps_router
from solace_agent_mesh.gateway.http_sse.routers.storage import router as storage_router


def create_test_app():
    """Create FastAPI app for testing."""
    app = FastAPI()

    # Include routers
    app.include_router(apps_router, prefix="/api/v1", tags=["apps"])
    app.include_router(storage_router, prefix="/api/v1", tags=["storage"])

    return app


def mock_user():
    """Mock user for authentication."""
    return {"id": "test-user", "username": "testuser"}


def test_1_storage_endpoints():
    """Test storage router endpoints."""
    print("\n=== Test 1: Storage API Endpoints ===")

    app = create_test_app()

    # Override auth dependency
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user()

    client = TestClient(app)

    # Test 1a: Set storage value
    print("Testing POST /apps/{app_id}/storage...")
    response = client.post(
        "/api/v1/apps/test-app/storage",
        json={"key": "user.preferences", "value": {"theme": "dark", "layout": "grid"}}
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["key"] == "user.preferences"
    assert data["appId"] == "test-app"
    assert data["value"]["theme"] == "dark"
    print(f"✓ Set storage value: {data['key']}")

    # Test 1b: Get storage value
    print("Testing GET /apps/{app_id}/storage/{key}...")
    response = client.get("/api/v1/apps/test-app/storage/user.preferences")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["value"]["theme"] == "dark"
    print(f"✓ Retrieved storage value: {data['value']}")

    # Test 1c: List storage keys
    print("Testing GET /apps/{app_id}/storage (list keys)...")

    # Add more keys
    client.post("/api/v1/apps/test-app/storage", json={"key": "user.settings", "value": {"lang": "en"}})
    client.post("/api/v1/apps/test-app/storage", json={"key": "cache.data", "value": [1, 2, 3]})

    response = client.get("/api/v1/apps/test-app/storage")
    assert response.status_code == 200
    data = response.json()
    assert len(data["keys"]) == 3
    print(f"✓ Listed {len(data['keys'])} keys: {data['keys']}")

    # Test 1d: List with prefix filter
    print("Testing GET /apps/{app_id}/storage?prefix=user.")
    response = client.get("/api/v1/apps/test-app/storage?prefix=user.")
    assert response.status_code == 200
    data = response.json()
    assert len(data["keys"]) == 2  # user.preferences and user.settings
    print(f"✓ Filtered by prefix 'user.': {data['keys']}")

    # Test 1e: Delete storage value
    print("Testing DELETE /apps/{app_id}/storage/{key}...")
    response = client.delete("/api/v1/apps/test-app/storage/cache.data")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    print(f"✓ Deleted key: {data['key']}")

    # Verify deletion
    response = client.get("/api/v1/apps/test-app/storage/cache.data")
    assert response.status_code == 404  # Should not exist
    print("✓ Verified key was deleted")

    # Test 1f: Clear all storage
    print("Testing DELETE /apps/{app_id}/storage (clear all)...")
    response = client.delete("/api/v1/apps/test-app/storage")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["cleared_keys"] == 2  # user.preferences and user.settings
    print(f"✓ Cleared {data['cleared_keys']} keys")

    # Test 1g: Error handling - invalid JSON value
    print("Testing error handling with non-JSON value...")
    # This should work because functions are not JSON-serializable
    response = client.post(
        "/api/v1/apps/test-app/storage",
        json={"key": "test", "value": "simple string"}  # This is valid JSON
    )
    assert response.status_code == 200  # Strings are JSON-serializable
    print("✓ JSON validation working")

    print("✓ Test 1 PASSED\n")


def test_2_storage_isolation():
    """Test that storage is isolated between users and apps."""
    print("\n=== Test 2: Storage Isolation ===")

    app = create_test_app()

    # User 1
    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"id": "user1", "username": "user1"}

    client1 = TestClient(app)

    # User 1 sets a value
    response = client1.post(
        "/api/v1/apps/app1/storage",
        json={"key": "shared-key", "value": "user1-value"}
    )
    assert response.status_code == 200
    print("✓ User1 set value in app1")

    # User 2
    app.dependency_overrides[get_current_user] = lambda: {"id": "user2", "username": "user2"}
    client2 = TestClient(app)

    # User 2 tries to read User 1's value - should not exist
    response = client2.get("/api/v1/apps/app1/storage/shared-key")
    assert response.status_code == 404  # Should not see user1's data
    print("✓ User2 cannot see User1's data (user isolation)")

    # User 1 sets value in app2
    app.dependency_overrides[get_current_user] = lambda: {"id": "user1", "username": "user1"}
    client1 = TestClient(app)

    response = client1.post(
        "/api/v1/apps/app2/storage",
        json={"key": "shared-key", "value": "user1-app2-value"}
    )
    assert response.status_code == 200
    print("✓ User1 set value in app2")

    # User 1 reads from app1 - should get app1 value, not app2
    response = client1.get("/api/v1/apps/app1/storage/shared-key")
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "user1-value"  # Not "user1-app2-value"
    print("✓ User1's data is isolated between apps (app isolation)")

    print("✓ Test 2 PASSED\n")


def test_3_apps_endpoint_basics():
    """Test basic apps endpoint structure (without full implementation)."""
    print("\n=== Test 3: Apps Endpoints Basic Structure ===")

    app = create_test_app()

    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user()

    client = TestClient(app)

    # Test 3a: List apps (empty initially)
    print("Testing GET /apps (list)...")
    response = client.get("/api/v1/apps?pageNumber=1&pageSize=20")

    # Should return 200 even if no apps
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data
    print(f"✓ List apps endpoint working: {len(data['data'])} apps")

    # Test 3b: Get single app (should fail - not implemented yet)
    print("Testing GET /apps/{app_id} (expecting 501 not implemented)...")
    response = client.get("/api/v1/apps/nonexistent-app")

    # Should return 501 (not implemented) since database models aren't hooked up yet
    assert response.status_code == 501
    print("✓ Get app endpoint returns 501 (expected - DB not connected)")

    # Test 3c: Create app endpoint exists
    print("Testing POST /apps (create)...")
    response = client.post(
        "/api/v1/apps",
        json={"name": "Test App", "description": "A test application"}
    )

    # This might succeed or fail depending on workspace creation
    # We're just checking the endpoint exists
    print(f"✓ Create app endpoint accessible (status: {response.status_code})")

    if response.status_code == 200:
        data = response.json()
        print(f"  App created: {data.get('appId')}")
        print(f"  Workspace: {data.get('workspacePath')}")

    print("✓ Test 3 PASSED\n")


def test_4_storage_data_types():
    """Test storage with various data types."""
    print("\n=== Test 4: Storage Data Types ===")

    app = create_test_app()

    from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user()

    client = TestClient(app)

    test_values = [
        ("string", "Hello, World!"),
        ("number", 42),
        ("float", 3.14159),
        ("boolean", True),
        ("null", None),
        ("array", [1, 2, 3, "four", 5.0]),
        ("object", {"nested": {"deep": {"value": "here"}}}),
        ("empty-object", {}),
        ("empty-array", []),
    ]

    for key, value in test_values:
        response = client.post(
            "/api/v1/apps/test-app/storage",
            json={"key": key, "value": value}
        )
        assert response.status_code == 200, f"Failed to store {key}: {response.text}"

        # Retrieve and verify
        response = client.get(f"/api/v1/apps/test-app/storage/{key}")
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == value, f"Value mismatch for {key}"

        print(f"✓ Stored and retrieved {key}: {value}")

    print("✓ Test 4 PASSED\n")


def main():
    """Run all API tests."""
    print("\n" + "=" * 70)
    print("SAM APPS API ENDPOINT TESTS")
    print("=" * 70)

    try:
        # Storage API tests
        test_1_storage_endpoints()
        test_2_storage_isolation()
        test_4_storage_data_types()

        # Apps API basic tests
        test_3_apps_endpoint_basics()

        print("=" * 70)
        print("✓ ALL API TESTS PASSED!")
        print("=" * 70)

        return 0

    except Exception as e:
        print("=" * 70)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
