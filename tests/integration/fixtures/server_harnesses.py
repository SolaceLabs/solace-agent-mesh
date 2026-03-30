"""Server harness fixtures for integration tests.

This module manages the lifecycle of external test servers (MCP, LLM, A2A, static file).
Extracted from the main integration conftest to improve maintainability.
"""
import inspect
import socket
import subprocess
import sys
import time
from typing import Any, Dict, Generator

import httpx
import pytest
from a2a.types import AgentCard
from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.a2a_agent_server.server import TestA2AAgentServer
from sam_test_infrastructure.static_file_server.server import TestStaticFileServer
from solace_agent_mesh.agent.tools.registry import tool_registry

from tests.integration.test_support.a2a_agent.executor import DeclarativeAgentExecutor


def find_free_port() -> int:
    """Finds and returns an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mcp_server_harness() -> Generator[dict[str, Any], None, None]:
    """
    Manages the lifecycle of the TestMCPServer.
    Starts server in separate processes for HTTP/SSE and provides connection details.

    Yields:
        Dictionary containing connection_params for stdio, http (sse), and streamable_http.
    """
    from sam_test_infrastructure.mcp_server.server import TestMCPServer as server_module

    process = None
    process2 = None
    SERVER_PATH = inspect.getfile(server_module)

    try:
        # Prepare stdio config
        stdio_params = {
            "type": "stdio",
            "command": sys.executable,
            "args": [SERVER_PATH, "--transport", "stdio"],
        }
        print("\nConfigured TestMCPServer for stdio mode (ADK will start process).")

        # Start SSE HTTP server
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        sse_url = f"{base_url}/sse"
        command = [sys.executable, SERVER_PATH, "--transport", "sse", "--port", str(port)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"\nStarted TestMCPServer in sse mode (PID: {process.pid})...")

        # Start Streamable-http server
        port2 = find_free_port()
        base_url2 = f"http://127.0.0.1:{port2}"
        http_url = f"{base_url2}/mcp"
        health_url = f"{base_url2}/health"
        command2 = [sys.executable, SERVER_PATH, "--transport", "http", "--port", str(port2)]
        process2 = subprocess.Popen(command2, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"\nStarted TestMCPServer in streamable-http mode (PID: {process2.pid})...")

        # Readiness check
        max_wait_seconds = 10
        start_time = time.time()
        is_ready = False
        while time.time() - start_time < max_wait_seconds:
            try:
                response = httpx.get(health_url, timeout=1)
                if response.status_code == 200:
                    print(f"TestMCPServer is ready on {base_url2}.")
                    is_ready = True
                    break
            except httpx.RequestError:
                time.sleep(0.1)

        if not is_ready:
            pytest.fail(f"TestMCPServer (http) failed to start within {max_wait_seconds} seconds.")

        http_params = {"type": "sse", "url": sse_url}
        streamable_params = {"type": "streamable-http", "url": http_url}
        connection_params = {
            "stdio": stdio_params,
            "http": http_params,
            "streamable_http": streamable_params,
        }

        yield connection_params

    finally:
        if process:
            print(f"\nTerminating sse TestMCPServer (PID: {process.pid})...")
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            print("TestMCPServer (sse) terminated.")

        if process2:
            print(f"\nTerminating streamable-http TestMCPServer (PID: {process2.pid})...")
            process2.terminate()
            try:
                process2.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process2.kill()
            print("TestMCPServer (streamable-http) terminated.")


@pytest.fixture(scope="session")
def test_llm_server():
    """Manages the lifecycle of the TestLLMServer for the test session."""
    server = TestLLMServer(host="127.0.0.1", port=8088)
    server.start()

    max_retries = 20
    retry_delay = 0.25
    ready = False
    for i in range(max_retries):
        time.sleep(retry_delay)
        try:
            if server.started:
                print(f"TestLLMServer confirmed started after {i + 1} attempts.")
                ready = True
                break
            print(f"TestLLMServer not ready yet (attempt {i + 1}/{max_retries})...")
        except Exception as e:
            print(f"TestLLMServer readiness check (attempt {i + 1}/{max_retries}) encountered an error: {e}")

    if not ready:
        try:
            server.stop()
        except Exception:
            pass
        pytest.fail("TestLLMServer did not become ready in time.")

    print(f"TestLLMServer fixture: Server ready at {server.url}")
    yield server

    print("TestLLMServer fixture: Stopping server...")
    server.stop()
    print("TestLLMServer fixture: Server stopped.")


@pytest.fixture(scope="session")
def test_static_file_server():
    """Manages the lifecycle of the TestStaticFileServer for the test session."""
    server = TestStaticFileServer(host="127.0.0.1", port=8089)
    server.start()

    max_retries = 20
    retry_delay = 0.25
    ready = False
    for i in range(max_retries):
        time.sleep(retry_delay)
        try:
            if server.started:
                print(f"TestStaticFileServer confirmed started after {i + 1} attempts.")
                ready = True
                break
            print(f"TestStaticFileServer not ready yet (attempt {i + 1}/{max_retries})...")
        except Exception as e:
            print(f"TestStaticFileServer readiness check (attempt {i + 1}/{max_retries}) encountered an error: {e}")

    if not ready:
        try:
            server.stop()
        except Exception:
            pass
        pytest.fail("TestStaticFileServer did not become ready in time.")

    print(f"TestStaticFileServer fixture: Server ready at {server.url}")
    yield server

    print("TestStaticFileServer fixture: Stopping server...")
    server.stop()
    print("TestStaticFileServer fixture: Server stopped.")


@pytest.fixture(scope="session")
def test_a2a_agent_server_harness(mock_agent_card: AgentCard) -> Generator[TestA2AAgentServer, None, None]:
    """Manages the lifecycle of the TestA2AAgentServer for the test session."""
    port = find_free_port()
    print(f"\n[TestA2AAgentServer] Starting on port {port}")
    executor = DeclarativeAgentExecutor()
    server = TestA2AAgentServer(
        host="127.0.0.1",
        port=port,
        agent_card=mock_agent_card,
        agent_executor=executor,
    )
    executor.server = server
    print(f"[TestA2AAgentServer] Server URL will be: {server.url}")
    server.start()

    max_retries = 20
    retry_delay = 0.25
    ready = False
    for i in range(max_retries):
        time.sleep(retry_delay)
        try:
            if server.started:
                print(f"TestA2AAgentServer confirmed started after {i+1} attempts.")
                ready = True
                break
            print(f"TestA2AAgentServer not ready yet (attempt {i+1}/{max_retries})...")
        except Exception as e:
            print(f"TestA2AAgentServer readiness check (attempt {i+1}/{max_retries}) encountered an error: {e}")

    if not ready:
        try:
            server.stop()
        except Exception:
            pass
        pytest.fail(f"TestA2AAgentServer did not become ready in time on port {port}.")

    print(f"[TestA2AAgentServer] Server ready at {server.url}")
    print(f"[TestA2AAgentServer] Agent card endpoint: {server.url}/.well-known/agent-card.json")
    yield server

    print("\n[TestA2AAgentServer] Stopping server...")
    server.stop()
    print("[TestA2AAgentServer] Server stopped.")


@pytest.fixture(scope="session")
def test_artifact_service_instance() -> TestInMemoryArtifactService:
    """
    Provides a single instance of TestInMemoryArtifactService for the test session.
    Its state will be cleared by a separate function-scoped fixture.
    """
    service = TestInMemoryArtifactService()
    print("[SessionFixture] TestInMemoryArtifactService instance created for session.")
    yield service
    print("[SessionFixture] TestInMemoryArtifactService session ended.")


@pytest.fixture(autouse=True)
def clear_llm_server_configs(test_llm_server: TestLLMServer):
    """Automatically clears TestLLMServer before each test."""
    test_llm_server.clear_all_configurations()


@pytest.fixture(autouse=True)
def clear_static_file_server_state(test_static_file_server: TestStaticFileServer):
    """Automatically clears TestStaticFileServer state before each test."""
    yield
    test_static_file_server.clear_configured_responses()
    test_static_file_server.clear_captured_requests()


@pytest.fixture(autouse=True, scope="function")
async def clear_test_artifact_service_between_tests(
    test_artifact_service_instance: TestInMemoryArtifactService,
):
    """Clears all artifacts from the session-scoped TestInMemoryArtifactService after each test."""
    yield
    await test_artifact_service_instance.clear_all_artifacts()


@pytest.fixture()
def clear_tool_registry_fixture():
    """
    Clears the tool_registry singleton.
    This is NOT autouse, should be explicitly used by tests that need a clean registry.
    """
    tool_registry.clear()
    yield
    tool_registry.clear()


@pytest.fixture(scope="session")
def session_monkeypatch():
    """A session-scoped monkeypatch object."""
    mp = pytest.MonkeyPatch()
    print("[SessionFixture] Session-scoped monkeypatch created.")
    yield mp
    print("[SessionFixture] Session-scoped monkeypatch undoing changes.")
    mp.undo()


