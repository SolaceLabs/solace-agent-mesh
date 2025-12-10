#!/usr/bin/env python3
"""
Test script to verify app creation and dev server functionality.
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000/api/v1"
USER_ID = "sam_dev_user"

def test_create_app():
    """Test creating an app and starting the dev server."""
    print("=" * 60)
    print("Testing App Creation and Dev Server")
    print("=" * 60)

    # Step 1: Create app
    print("\n1. Creating test app...")
    app_data = {
        "name": "TestApp",
        "description": "Test app for debugging"
    }

    # Get auth cookie (simulate logged-in user)
    session = requests.Session()

    # For development, we need to set the user session
    # The backend uses session middleware, so we need to simulate a login
    # For now, let's just try the request

    response = session.post(
        f"{BASE_URL}/apps",
        json=app_data,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 401:
        print("❌ Authentication required. Please ensure you're logged in or update the test script.")
        print(f"   Response: {response.text}")
        return False

    if response.status_code != 200:
        print(f"❌ Failed to create app: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    app_response = response.json()
    app_id = app_response.get("appId")
    print(f"✅ App created successfully! App ID: {app_id}")
    print(f"   Workspace: {app_response.get('workspacePath')}")

    # Step 2: Start dev server
    print(f"\n2. Starting dev server for {app_id}...")
    response = session.post(
        f"{BASE_URL}/apps/dev-server",
        params={"workspaceId": app_id}
    )

    if response.status_code != 200:
        print(f"❌ Failed to start dev server: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    dev_response = response.json()
    dev_url = dev_response.get("devServerUrl")
    print(f"✅ Dev server started!")
    print(f"   URL: {dev_url}")
    print(f"   Status: {dev_response.get('status')}")

    # Step 3: Wait a bit for Vite to start
    print("\n3. Waiting for Vite to initialize (5 seconds)...")
    time.sleep(5)

    # Step 4: Test preview endpoint
    print(f"\n4. Testing preview endpoint: {BASE_URL}{dev_url}")
    response = session.get(f"{BASE_URL}{dev_url}")

    if response.status_code != 200:
        print(f"❌ Preview endpoint failed: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return False

    print(f"✅ Preview endpoint working!")
    print(f"   Content-Type: {response.headers.get('content-type')}")
    print(f"   Response size: {len(response.content)} bytes")

    # Check if it's HTML
    if 'text/html' in response.headers.get('content-type', ''):
        print("   ✅ Returned HTML (Vite dev server is running)")
        # Print first 200 chars of HTML
        html_preview = response.text[:200]
        print(f"   HTML preview: {html_preview}...")
    else:
        print(f"   ⚠️  Expected HTML but got: {response.headers.get('content-type')}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_create_app()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
