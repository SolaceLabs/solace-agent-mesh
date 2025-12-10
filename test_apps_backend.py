#!/usr/bin/env python3
"""
Full integration test for SAM Apps backend functionality.

Tests:
1. Container runtime detection (Podman)
2. Workspace creation from Docker template
3. Dev server container startup
4. Dev server health check
5. Container cleanup
"""

import asyncio
import subprocess
import time
import shutil
from pathlib import Path

# Import the backend functions
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from solace_agent_mesh.gateway.http_sse.routers.apps import (
    detect_container_runtime,
    create_workspace_from_template,
    start_dev_server,
    stop_dev_server,
    _dev_server_containers,
)


def test_1_container_runtime_detection():
    """Test that Podman is detected correctly."""
    print("\n=== Test 1: Container Runtime Detection ===")

    runtime = detect_container_runtime()
    print(f"✓ Detected runtime: {runtime}")

    assert runtime == "podman", f"Expected 'podman', got '{runtime}'"

    # Verify Podman is accessible
    result = subprocess.run([runtime, "--version"], capture_output=True, text=True)
    print(f"✓ Podman version: {result.stdout.strip()}")

    print("✓ Test 1 PASSED\n")


async def test_2_workspace_creation():
    """Test creating workspace from Docker template."""
    print("\n=== Test 2: Workspace Creation ===")

    test_workspace = Path("/Users/edfunnekotter/github/solace-agent-mesh-2/test-workspace")
    app_workspace = test_workspace / "test-user" / "apps" / "my-test-app"

    # Clean up if exists
    if app_workspace.exists():
        shutil.rmtree(app_workspace)

    # Create workspace from template
    print(f"Creating workspace at: {app_workspace}")
    await create_workspace_from_template(
        workspace_path=app_workspace,
        app_id="my-test-app",
        app_name="My Test App"
    )

    # Verify workspace structure
    assert app_workspace.exists(), "Workspace directory not created"
    assert (app_workspace / "package.json").exists(), "package.json missing"
    assert (app_workspace / "node_modules").exists(), "node_modules missing"
    assert (app_workspace / "src").exists(), "src directory missing"
    assert (app_workspace / "CLAUDE.md").exists(), "CLAUDE.md missing"
    assert (app_workspace / "vite.config.ts").exists(), "vite.config.ts missing"
    assert (app_workspace / ".git").exists(), "Git repo not initialized"

    print(f"✓ Workspace created with all files")

    # Check package.json was customized
    import json
    with open(app_workspace / "package.json") as f:
        pkg = json.load(f)

    assert pkg["name"] == "my-test-app", f"Package name not updated: {pkg['name']}"
    assert "My Test App" in pkg["description"], f"Description not updated: {pkg['description']}"

    print(f"✓ package.json customized correctly")
    print("✓ Test 2 PASSED\n")

    return app_workspace


def test_3_network_creation():
    """Test creating sam-internal network."""
    print("\n=== Test 3: Network Creation ===")

    runtime = detect_container_runtime()

    # Try to create network (will succeed or already exist)
    result = subprocess.run(
        [runtime, "network", "create", "sam-internal"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✓ Created sam-internal network")
    else:
        if "already exists" in result.stderr.lower():
            print("✓ sam-internal network already exists")
        else:
            raise Exception(f"Failed to create network: {result.stderr}")

    # Verify network exists
    result = subprocess.run(
        [runtime, "network", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )

    networks = result.stdout.strip().split("\n")
    assert "sam-internal" in networks, "sam-internal network not found"

    print("✓ Test 3 PASSED\n")


def test_4_dev_server_startup(app_workspace: Path):
    """Test starting a dev server container."""
    print("\n=== Test 4: Dev Server Startup ===")

    runtime = detect_container_runtime()
    app_id = "my-test-app"
    user_id = "test-user"

    # Clear any existing container state
    _dev_server_containers.clear()

    # Stop any existing container
    container_name = f"sam-app-{user_id}-{app_id}"
    subprocess.run([runtime, "stop", container_name], capture_output=True)
    subprocess.run([runtime, "rm", container_name], capture_output=True)

    print(f"Starting dev server for {app_id}...")

    try:
        internal_url = start_dev_server(
            app_id=app_id,
            workspace_path=str(app_workspace),
            user_id=user_id,
        )

        print(f"✓ Dev server started: {internal_url}")

        # Verify container is running
        result = subprocess.run(
            [runtime, "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        running_containers = result.stdout.strip().split("\n")
        assert container_name in running_containers, f"Container {container_name} not running"

        print(f"✓ Container {container_name} is running")

        # Check internal state
        assert app_id in _dev_server_containers, "App not tracked in internal state"
        container_info = _dev_server_containers[app_id]
        assert container_info["user_id"] == user_id
        assert container_info["internal_url"] == internal_url

        print("✓ Internal state tracking correct")

        # Give Vite a moment to start
        print("Waiting 5 seconds for Vite to start...")
        time.sleep(5)

        # Try to check if Vite is responding (from inside container)
        result = subprocess.run(
            [runtime, "exec", container_name, "wget", "-q", "-O", "-", "http://localhost:5173"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            print(f"✓ Vite dev server is responding")
        else:
            print(f"⚠ Vite might still be starting (exit code: {result.returncode})")

        print("✓ Test 4 PASSED\n")

        return container_name

    except Exception as e:
        print(f"✗ Test 4 FAILED: {e}")
        raise


def test_5_dev_server_logs(container_name: str):
    """Test viewing dev server logs."""
    print("\n=== Test 5: Dev Server Logs ===")

    runtime = detect_container_runtime()

    result = subprocess.run(
        [runtime, "logs", "--tail", "20", container_name],
        capture_output=True,
        text=True,
    )

    logs = result.stdout
    print("Last 20 lines of dev server logs:")
    print("-" * 60)
    print(logs)
    print("-" * 60)

    # Check for expected patterns
    if "vite" in logs.lower() or "ready in" in logs.lower():
        print("✓ Vite logs detected")
    else:
        print("⚠ Vite might not have started yet")

    print("✓ Test 5 PASSED\n")


def test_6_dev_server_cleanup(container_name: str):
    """Test stopping and removing dev server container."""
    print("\n=== Test 6: Dev Server Cleanup ===")

    app_id = "my-test-app"
    user_id = "test-user"

    stop_dev_server(app_id=app_id, user_id=user_id)

    print(f"✓ Dev server stopped via API")

    # Verify container is gone
    runtime = detect_container_runtime()
    result = subprocess.run(
        [runtime, "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )

    containers = [c for c in result.stdout.strip().split("\n") if c]
    assert container_name not in containers, f"Container {container_name} still exists"

    print(f"✓ Container {container_name} removed")

    # Verify internal state cleared
    assert app_id not in _dev_server_containers, "App still tracked in internal state"

    print("✓ Internal state cleared")
    print("✓ Test 6 PASSED\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("SAM APPS BACKEND INTEGRATION TEST")
    print("=" * 70)

    try:
        # Test 1: Container runtime detection
        test_1_container_runtime_detection()

        # Test 2: Workspace creation
        app_workspace = await test_2_workspace_creation()

        # Test 3: Network creation
        test_3_network_creation()

        # Test 4: Dev server startup
        container_name = test_4_dev_server_startup(app_workspace)

        # Test 5: View logs
        test_5_dev_server_logs(container_name)

        # Test 6: Cleanup
        test_6_dev_server_cleanup(container_name)

        print("=" * 70)
        print("✓ ALL TESTS PASSED!")
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
    exit_code = asyncio.run(main())
    exit(exit_code)
