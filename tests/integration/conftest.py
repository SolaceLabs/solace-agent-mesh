from typing import Any, Dict, Generator, List, Optional, TYPE_CHECKING
import inspect
import socket
import pytest
import time
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import sqlalchemy as sa
from a2a.types import (
    AgentCard,
    AgentSkill,
    PushNotificationConfig,
    Task,
    TaskPushNotificationConfig,
    TaskState,
    TaskStatusUpdateEvent,
)
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator
from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from sam_test_infrastructure.gateway_interface.app import TestGatewayApp
from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
from sam_test_infrastructure.llm_server.server import TestLLMServer
from sam_test_infrastructure.a2a_agent_server.server import TestA2AAgentServer
from sam_test_infrastructure.static_file_server.server import TestStaticFileServer
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from sqlalchemy import create_engine, text

from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper
from solace_agent_mesh.agent.tools.registry import tool_registry
from solace_agent_mesh.common import a2a
from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

from tests.integration.test_support.a2a_agent.executor import (
    DeclarativeAgentExecutor,
)

if TYPE_CHECKING:
    from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent


@pytest.fixture(scope="session")
def test_db_engine():
    """
    Creates a temporary SQLite database for the test session, runs migrations,
    and yields the SQLAlchemy engine.
    """
    import os

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_integration.db"
        database_url = f"sqlite:///{db_path}"
        print(f"\n[SessionFixture] Creating test database at: {database_url}")

        engine = create_engine(database_url)

        # Enable foreign keys for SQLite (database-agnostic approach)
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            if database_url.startswith("sqlite"):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        # Run Alembic migrations
        alembic_cfg = AlembicConfig()
        # The script location is relative to the project root
        script_location = "src/solace_agent_mesh/gateway/http_sse/alembic"
        alembic_cfg.set_main_option("script_location", script_location)
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        alembic_command.upgrade(alembic_cfg, "head")
        print("[SessionFixture] Database migrations applied.")

        # Ensure the database file has write permissions
        # This prevents "readonly database" errors when new connections are created
        if db_path.exists():
            os.chmod(db_path, 0o666)  # Read/write for owner, group, and others
            print(f"[SessionFixture] Set write permissions on database file: {db_path}")

        yield engine

        engine.dispose()
        print("[SessionFixture] Test database engine disposed.")


@pytest.fixture(autouse=True)
def clean_db_fixture(test_db_engine):
    """
    Cleans all data from the test database before each test run.
    """
    with test_db_engine.connect() as connection:
        with connection.begin():
            inspector = sa.inspect(test_db_engine)
            existing_tables = inspector.get_table_names()

            # Delete in correct order to handle foreign key constraints
            tables_to_clean = [
                "feedback",
                "task_events",
                "chat_messages",
                "tasks",
                "sessions",
                "prompt_group_users",  
                "prompts",             
                "prompt_groups",      
                "project_users",      
                "projects",            
                "users",
            ]
            for table_name in tables_to_clean:
                if table_name in existing_tables:
                    connection.execute(text(f"DELETE FROM {table_name}"))
    yield


def find_free_port() -> int:
    """Finds and returns an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mcp_server_harness() -> Generator[dict[str, Any], None, None]:
    """
    Pytest fixture to manage the lifecycle of the TestMCPServer.

    It starts the server in a separate process for HTTP and provides connection details
    for both 'stdio' and 'http' transports.

    Yields:
        A dictionary containing the `connection_params` for both stdio and http.
    """
    from sam_test_infrastructure.mcp_server.server import TestMCPServer as server_module

    process = None
    port = 0
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
        sse_url = f"{base_url}/sse"  # The default path for fastmcp sse transport
        command = [
            sys.executable,
            SERVER_PATH,
            "--transport",
            "sse",
            "--port",
            str(port),
        ]
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print(f"\nStarted TestMCPServer in sse mode (PID: {process.pid})...")

        # Start Streamable-http server
        port = find_free_port()
        base_url = f"http://127.0.0.1:{port}"
        http_url = f"{base_url}/mcp"
        health_url = f"{base_url}/health"

        command = [
            sys.executable,
            SERVER_PATH,
            "--transport",
            "http",
            "--port",
            str(port),
        ]
        process2 = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print(
            f"\nStarted TestMCPServer in streamable-http mode (PID: {process2.pid})..."
        )

        # Readiness check by polling the /health endpoint
        max_wait_seconds = 10
        start_time = time.time()
        is_ready = False
        while time.time() - start_time < max_wait_seconds:
            try:
                response = httpx.get(health_url, timeout=1)
                if response.status_code == 200:
                    print(f"TestMCPServer is ready on {base_url}.")
                    is_ready = True
                    break
            except httpx.RequestError:
                time.sleep(0.1)

        if not is_ready:
            pytest.fail(
                f"Test MCP Server (http) failed to start on port {port} within {max_wait_seconds} seconds."
            )

        http_params = {
            "type": "sse",  # 'sse' is the type used by the ADK's MCPToolset for http
            "url": sse_url,
        }

        streamable_params = {
            "type": "streamable-http",
            "url": http_url,
        }

        connection_params = {
            "stdio": stdio_params,
            "http": http_params,
            "streamable_http": streamable_params,
        }

        yield connection_params

    finally:
        if process:
            print(f"\nTerminating http TestMCPServer (PID: {process.pid})...")
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
                if stdout:
                    print(
                        f"\n--- TestMCPServer STDOUT ---\n{stdout.decode('utf-8', 'ignore')}"
                    )
                if stderr:
                    print(
                        f"\n--- TestMCPServer STDERR ---\n{stderr.decode('utf-8', 'ignore')}"
                    )
            except subprocess.TimeoutExpired:
                process.kill()
                print(
                    "\nHttp TestMCPServer process did not terminate gracefully, had to be killed."
                )
            print("TestMCPServer (http) terminated.")
        if process2:
            print(
                f"\nTerminating streamable-http TestMCPServer (PID: {process2.pid})..."
            )
            process2.terminate()
            try:
                stdout, stderr = process2.communicate(timeout=5)
                if stdout:
                    print(
                        f"\n--- TestMCPServer STDOUT ---\n{stdout.decode('utf-8', 'ignore')}"
                    )
                if stderr:
                    print(
                        f"\n--- TestMCPServer STDERR ---\n{stderr.decode('utf-8', 'ignore')}"
                    )
            except subprocess.TimeoutExpired:
                process2.kill()
                print(
                    "\nStreamable-http TestMCPServer process did not terminate gracefully, had to be killed."
                )
            print("TestMCPServer (streamable-http) terminated.")

        print(
            "\nNo external TestMCPServer process to terminate for stdio mode (ADK manages process)."
        )


@pytest.fixture
def mock_oauth_server():
    """
    Provides a mock OAuth 2.0 token endpoint using respx.
    Returns a helper object for configuring responses.
    """

    class MockOAuthServer:
        def __init__(self):
            import respx

            # Allow unmocked requests to pass through to support real HTTP calls
            # to TestA2AAgentServer while mocking OAuth token endpoints
            self.mock = respx.mock(assert_all_called=False, assert_all_mocked=False)
            # Pass through all localhost/127.0.0.1 requests to allow real test servers to work
            self.mock.route(host="127.0.0.1").pass_through()
            self.mock.route(host="localhost").pass_through()

            # Explicitly pass through both agent card endpoint paths (old and new A2A spec)
            # This ensures the A2A SDK's fallback logic works correctly
            self.mock.route(path="/.well-known/agent-card.json").pass_through()

            print(f"\n[MockOAuthServer] Initializing respx mock")
            print(
                f"[MockOAuthServer] Pass-through configured for: 127.0.0.1, localhost"
            )
            print(
                f"[MockOAuthServer] Pass-through configured for agent card path: /.well-known/agent-card.json"
            )

            self.mock.start()
            self._routes = {}
            self._call_log = []

            print(f"[MockOAuthServer] Mock started. ")

        def configure_token_endpoint(
            self,
            token_url: str,
            access_token: str = "test_token_12345",
            expires_in: int = 3600,
            error: Optional[Dict[str, Any]] = None,
            status_code: int = 200,
        ):
            """Configure a token endpoint to return specific responses."""
            print(f"\n[MockOAuthServer] Configuring token endpoint: {token_url}")

            if error:
                response = httpx.Response(status_code=status_code, json=error)
                print(f"[MockOAuthServer] Will return error with status {status_code}")
            else:
                response = httpx.Response(
                    status_code=200,
                    json={
                        "access_token": access_token,
                        "token_type": "Bearer",
                        "expires_in": expires_in,
                    },
                )
                print(
                    f"[MockOAuthServer] Will return access_token: {access_token[:20]}..."
                )

            route = self.mock.post(token_url).mock(return_value=response)
            self._routes[token_url] = route
            print(f"[MockOAuthServer] Route configured and stored")
            return route

        def configure_token_endpoint_sequence(
            self, token_url: str, responses: List[Dict[str, Any]]
        ):
            """Configure a token endpoint to return a sequence of responses."""
            http_responses = []
            for resp_config in responses:
                if "error" in resp_config:
                    http_responses.append(
                        httpx.Response(
                            status_code=resp_config.get("status_code", 400),
                            json=resp_config["error"],
                        )
                    )
                else:
                    http_responses.append(
                        httpx.Response(
                            status_code=200,
                            json={
                                "access_token": resp_config.get(
                                    "access_token", "test_token"
                                ),
                                "token_type": "Bearer",
                                "expires_in": resp_config.get("expires_in", 3600),
                            },
                        )
                    )

            route = self.mock.post(token_url).mock(side_effect=http_responses)
            self._routes[token_url] = route
            return route

        def get_route(self, token_url: str):
            """Get the respx route for a token URL."""
            return self._routes.get(token_url)

        def assert_token_requested(self, token_url: str, times: int = 1):
            """Assert that a token endpoint was called a specific number of times."""
            route = self._routes.get(token_url)
            assert route is not None, f"No route configured for {token_url}"
            assert (
                route.call_count == times
            ), f"Expected {times} calls to {token_url}, got {route.call_count}"

        def get_last_token_request(self, token_url: str) -> Optional[Any]:
            """Get the last request made to a token endpoint."""
            route = self._routes.get(token_url)
            if route and route.calls:
                return route.calls.last.request
            return None

        def stop(self):
            """Stop the mock."""
            print(f"\n[MockOAuthServer] Stopping respx mock")
            self.mock.stop()
            print(f"[MockOAuthServer] Mock stopped")

    server = MockOAuthServer()
    yield server
    server.stop()


@pytest.fixture
def mock_gemini_client(monkeypatch):
    """
    Mocks the google.genai.Client and PIL.Image.open to prevent real API calls
    and allow for deterministic testing.
    """

    class MockPILImage:
        def __init__(self):
            self.size = (1, 1)
            self.mode = "RGB"

        def split(self):
            return []

        def save(self, fp, format=None, quality=None):
            fp.write(b"mock_image_bytes")

    def mock_open(fp):
        return MockPILImage()

    try:
        from PIL import Image

        monkeypatch.setattr(Image, "open", mock_open)
    except ImportError:
        pass

    class MockPart:
        def __init__(self, text=None, inline_data=None):
            self.text = text
            self.inline_data = inline_data

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    class MockCandidate:
        def __init__(self, content):
            self.content = content

    class MockGenerateContentResponse:
        def __init__(self, candidates):
            self.candidates = candidates

    class MockGeminiClient:
        def __init__(self, api_key=None):
            self._api_key = api_key
            self.models = self

        def generate_content(self, model, contents, config):
            if self._api_key != "fake-gemini-api-key":
                raise Exception(
                    "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.'}}"
                )

            edited_image_bytes = b"edited_image_bytes"
            mock_response = MockGenerateContentResponse(
                candidates=[
                    MockCandidate(
                        content=MockContent(
                            parts=[
                                MockPart(text="Image edited successfully."),
                                MockPart(
                                    inline_data=type(
                                        "obj", (object,), {"data": edited_image_bytes}
                                    )()
                                ),
                            ]
                        )
                    )
                ]
            )
            return mock_response

    monkeypatch.setattr("google.genai.Client", MockGeminiClient)


@pytest.fixture(scope="session")
def test_llm_server():
    """
    Manages the lifecycle of the TestLLMServer for the test session.
    Yields the TestLLMServer instance.
    """
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
            print(
                f"TestLLMServer readiness check (attempt {i + 1}/{max_retries}) encountered an error: {e}"
            )

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
    """
    Manages the lifecycle of the TestStaticFileServer for the test session.
    Yields the TestStaticFileServer instance.
    """
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
            print(
                f"TestStaticFileServer not ready yet (attempt {i + 1}/{max_retries})..."
            )
        except Exception as e:
            print(
                f"TestStaticFileServer readiness check (attempt {i + 1}/{max_retries}) encountered an error: {e}"
            )

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
def test_a2a_agent_server_harness(
    mock_agent_card: AgentCard,
) -> Generator[TestA2AAgentServer, None, None]:
    """
    Manages the lifecycle of the TestA2AAgentServer for the test session.
    Yields the TestA2AAgentServer instance.
    """
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
            print(
                f"TestA2AAgentServer readiness check (attempt {i+1}/{max_retries}) encountered an error: {e}"
            )

    if not ready:
        try:
            server.stop()
        except Exception:
            pass
        pytest.fail(f"TestA2AAgentServer did not become ready in time on port {port}.")

    print(f"[TestA2AAgentServer] Server ready at {server.url}")
    print(
        f"[TestA2AAgentServer] Agent card endpoint: {server.url}/.well-known/agent-card.json"
    )
    yield server

    print("\n[TestA2AAgentServer] Stopping server...")
    server.stop()
    print("[TestA2AAgentServer] Server stopped.")


@pytest.fixture(autouse=True)
def clear_llm_server_configs(test_llm_server: TestLLMServer):
    """
    Automatically clears any primed responses and captured requests from the
    TestLLMServer before each test that uses it (if session-scoped and reused).
    Also clears the global static response.
    """
    test_llm_server.clear_all_configurations()


@pytest.fixture(autouse=True)
def clear_static_file_server_state(test_static_file_server: TestStaticFileServer):
    """
    Automatically clears configured responses and captured requests from the
    TestStaticFileServer before each test.
    """
    yield
    test_static_file_server.clear_configured_responses()
    test_static_file_server.clear_captured_requests()


@pytest.fixture()
def clear_tool_registry_fixture():
    """
    A pytest fixture that clears the tool_registry singleton.
    This is NOT autouse, and should be explicitly used by tests that need
    a clean registry.
    """
    tool_registry.clear()
    yield
    tool_registry.clear()


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


@pytest.fixture(autouse=True, scope="function")
async def clear_test_artifact_service_between_tests(
    test_artifact_service_instance: TestInMemoryArtifactService,
):
    """
    Clears all artifacts from the session-scoped TestInMemoryArtifactService after each test.
    """
    yield
    await test_artifact_service_instance.clear_all_artifacts()


@pytest.fixture(scope="session")
def session_monkeypatch():
    """A session-scoped monkeypatch object."""
    mp = pytest.MonkeyPatch()
    print("[SessionFixture] Session-scoped monkeypatch created.")
    yield mp
    print("[SessionFixture] Session-scoped monkeypatch undoing changes.")
    mp.undo()


@pytest.fixture(scope="session")
def shared_solace_connector(
    test_llm_server: TestLLMServer,
    test_artifact_service_instance: TestInMemoryArtifactService,
    session_monkeypatch,
    request,
    mcp_server_harness,
    test_db_engine,
    test_a2a_agent_server_harness: TestA2AAgentServer,
) -> SolaceAiConnector:
    """
    Creates and manages a single SolaceAiConnector instance with multiple agents
    for integration testing.
    """

    def create_agent_config(
        agent_name,
        description,
        allow_list,
        tools,
        model_suffix,
        session_behavior="RUN_BASED",
        inject_system_purpose=False,
        inject_response_format=False,
    ):
        config = {
            "namespace": "test_namespace",
            "supports_streaming": True,
            "agent_name": agent_name,
            "model": {
                "model": f"openai/test-model-{model_suffix}-{time.time_ns()}",
                "api_base": f"{test_llm_server.url}/v1",
                "api_key": f"fake_test_key_{model_suffix}",
            },
            "session_service": {"type": "memory", "default_behavior": session_behavior},
            "artifact_service": {"type": "test_in_memory"},
            "memory_service": {"type": "memory"},
            "agent_card": {
                "description": description,
                "defaultInputModes": ["text"],
                "defaultOutputModes": ["text"],
                "jsonrpc": "2.0",
                "id": "agent_card_pub",
            },
            "agent_card_publishing": {"interval_seconds": 1},
            "agent_discovery": {"enabled": True},
            "inter_agent_communication": {
                "allow_list": allow_list,
                "request_timeout_seconds": 5,
            },
            "tool_output_save_threshold_bytes": 50,
            "tool_output_llm_return_max_bytes": 200,
            "data_tools_config": {
                "max_result_preview_rows": 5,
                "max_result_preview_bytes": 2048,
            },
            "tools": tools,
        }

        if inject_system_purpose:
            config["inject_system_purpose"] = True
        if inject_response_format:
            config["inject_response_format"] = True

        return config

    test_agent_tools = [
        {
            "tool_type": "python",
            "component_module": "tests.integration.test_support.tools",
            "function_name": "get_weather_tool",
            "component_base_path": ".",
        },
        {"tool_type": "builtin", "tool_name": "convert_file_to_markdown"},
        {"tool_type": "builtin-group", "group_name": "artifact_management"},
        {"tool_type": "builtin-group", "group_name": "data_analysis"},
        {"tool_type": "builtin-group", "group_name": "test"},
        {
            "tool_type": "builtin",
            "tool_name": "web_request",
            "tool_config": {"allow_loopback": True},
        },
        {
            "tool_type": "python",
            "component_module": "solace_agent_mesh.agent.tools.web_tools",
            "function_name": "web_request",
            "tool_name": "web_request_strict",
            "component_base_path": ".",
            "tool_config": {"allow_loopback": False},
        },
        {"tool_type": "builtin", "tool_name": "mermaid_diagram_generator"},
        {
            "tool_type": "builtin",
            "tool_name": "create_image_from_description",
            "tool_config": {
                "model": "dall-e-3",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "describe_image",
            "tool_config": {
                "model": f"openai/test-model-sam-vision-{time.time_ns()}",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "describe_audio",
            "tool_config": {
                "model": "whisper-1",
                "api_key": "fake-api-key",
                "api_base": f"{test_llm_server.url}",
            },
        },
        {
            "tool_type": "builtin",
            "tool_name": "edit_image_with_gemini",
            "tool_config": {
                "model": "gemini-2.0-flash-preview-image-generation",
                "gemini_api_key": "fake-gemini-api-key",
            },
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_stdio",
            "connection_params": mcp_server_harness["stdio"],
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_http",
            "connection_params": mcp_server_harness["http"],
        },
        {
            "tool_type": "mcp",
            "tool_name": "get_data_streamable_http",
            "connection_params": mcp_server_harness["streamable_http"],
        },
    ]
    sam_agent_app_config = create_agent_config(
        agent_name="TestAgent",
        description="The main test agent (orchestrator)",
        allow_list=["TestPeerAgentA", "TestPeerAgentB", "TestAgent_Proxied", "TestAgent_Proxied_NoConvert"],
        tools=test_agent_tools,
        model_suffix="sam",
        inject_system_purpose=True,
        inject_response_format=True,
    )

    peer_agent_tools = [
        {"tool_type": "builtin-group", "group_name": "artifact_management"},
        {"tool_type": "builtin-group", "group_name": "data_analysis"},
    ]
    peer_a_config = create_agent_config(
        agent_name="TestPeerAgentA",
        description="Peer Agent A, accessible by TestAgent, can access D",
        allow_list=["TestPeerAgentD"],
        tools=peer_agent_tools,
        model_suffix="peerA",
    )
    peer_b_config = create_agent_config(
        agent_name="TestPeerAgentB",
        description="Peer Agent B, accessible by TestAgent, cannot delegate",
        allow_list=[],
        tools=peer_agent_tools,
        model_suffix="peerB",
    )
    peer_c_config = create_agent_config(
        agent_name="TestPeerAgentC",
        description="Peer Agent C, not accessible by TestAgent",
        allow_list=[],
        tools=peer_agent_tools,
        model_suffix="peerC",
        session_behavior="PERSISTENT",
    )
    peer_d_config = create_agent_config(
        agent_name="TestPeerAgentD",
        description="Peer Agent D, accessible by Peer A",
        allow_list=[],
        tools=peer_agent_tools,
        model_suffix="peerD",
    )

    combined_dynamic_agent_config = create_agent_config(
        agent_name="CombinedDynamicAgent",
        description="Agent for testing all dynamic tool features.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.single_tool",
                "tool_config": {"greeting_prefix": "Hi there"},
            },
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.provider_tool",
            },
        ],
        model_suffix="dynamic-combined",
    )

    empty_provider_agent_config = create_agent_config(
        agent_name="EmptyProviderAgent",
        description="Agent with an empty tool provider.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.error_cases",
                "class_name": "EmptyToolProvider",
            }
        ],
        model_suffix="empty-provider",
    )

    docstringless_agent_config = create_agent_config(
        agent_name="DocstringlessAgent",
        description="Agent with a tool that has no docstring.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.error_cases",
                "class_name": "ProviderWithDocstringlessTool",
            }
        ],
        model_suffix="docstringless",
    )

    mixed_discovery_agent_config = create_agent_config(
        agent_name="MixedDiscoveryAgent",
        description="Agent with a module containing both provider and standalone tool.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.mixed_discovery",
            }
        ],
        model_suffix="mixed-discovery",
    )

    complex_signatures_agent_config = create_agent_config(
        agent_name="ComplexSignaturesAgent",
        description="Agent for testing complex tool signatures.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.complex_signatures",
            }
        ],
        model_suffix="complex-signatures",
    )

    config_context_agent_config = create_agent_config(
        agent_name="ConfigContextAgent",
        description="Agent for testing tool config and context features.",
        allow_list=[],
        tools=[
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.config_and_context",
                "tool_config": {"provider_level": "value1", "tool_specific": "value2"},
            }
        ],
        model_suffix="config-context",
    )

    # Generic Gateway test apps
    minimal_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "MinimalTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.MinimalAdapter",
        "adapter_config": {
            "default_user_id": "minimal-user@example.com",
            "default_target_agent": "TestAgent",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "default-user@example.com",
    }

    auth_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "AuthTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.AuthTestAdapter",
        "adapter_config": {
            "require_token": False,
            "valid_token": "valid-test-token",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "fallback-user@example.com",
    }

    file_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "FileTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.FileAdapter",
        "adapter_config": {
            "max_file_size": 1024 * 1024,
        },
        "artifact_service": {"type": "test_in_memory"},
    }

    dispatching_gateway_config = {
        "namespace": "test_namespace",
        "gateway_id": "DispatchingTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.DispatchingAdapter",
        "adapter_config": {
            "default_user_id": "dispatch-user@example.com",
            "default_target_agent": "TestAgent",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "default-dispatch@example.com",
    }

    app_infos = [
        {
            "name": "WebUIBackendApp",
            "app_module": "solace_agent_mesh.gateway.http_sse.app",
            "broker": {"dev_mode": True},
            "app_config": {
                "namespace": "test_namespace",
                "gateway_id": "TestWebUIGateway_01",
                "session_secret_key": "a_secure_test_secret_key",
                "session_service": {
                    "type": "sql",
                    "database_url": str(test_db_engine.url),
                },
                "task_logging": {"enabled": True},
                "artifact_service": {"type": "test_in_memory"},
            },
        },
        {
            "name": "MinimalGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": minimal_gateway_config,
        },
        {
            "name": "AuthGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": auth_gateway_config,
        },
        {
            "name": "FileGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": file_gateway_config,
        },
        {
            "name": "DispatchingGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": dispatching_gateway_config,
        },
        {
            "name": "TestSamAgentApp",
            "app_config": sam_agent_app_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentA_App",
            "app_config": peer_a_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentB_App",
            "app_config": peer_b_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentC_App",
            "app_config": peer_c_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentD_App",
            "app_config": peer_d_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestHarnessGatewayApp",
            "app_config": {
                "namespace": "test_namespace",
                "gateway_id": "TestHarnessGateway_01",
                "artifact_service": {"type": "test_in_memory"},
                "task_logging": {"enabled": False},
                "system_purpose": "Test gateway system purpose for metadata validation",
                "response_format": "Test gateway response format for metadata validation",
            },
            "broker": {"dev_mode": True},
            "app_module": "sam_test_infrastructure.gateway_interface.app",
        },
        {
            "name": "CombinedDynamicAgent_App",
            "app_config": combined_dynamic_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "EmptyProviderAgent_App",
            "app_config": empty_provider_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "DocstringlessAgent_App",
            "app_config": docstringless_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "MixedDiscoveryAgent_App",
            "app_config": mixed_discovery_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "ComplexSignaturesAgent_App",
            "app_config": complex_signatures_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "ConfigContextAgent_App",
            "app_config": config_context_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestA2AProxyApp",
            "app_config": {
                "namespace": "test_namespace",
                "proxied_agents": [
                    {
                        "name": "TestAgent_Proxied",
                        "url": test_a2a_agent_server_harness.url,
                        "request_timeout_seconds": 3,
                        # convert_progress_updates defaults to true
                    },
                    {
                        "name": "TestAgent_Proxied_NoConvert",
                        "url": test_a2a_agent_server_harness.url,
                        "request_timeout_seconds": 3,
                        "convert_progress_updates": False,  # Disable text-to-data conversion
                    }
                ],
                "artifact_service": {"type": "test_in_memory"},
                "discovery_interval_seconds": 1,
            },
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.proxies.a2a.app",
        },
    ]

    session_monkeypatch.setattr(
        "solace_agent_mesh.agent.adk.services.TestInMemoryArtifactService",
        lambda: test_artifact_service_instance,
    )
    session_monkeypatch.setattr(
        "solace_agent_mesh.agent.proxies.base.component.initialize_artifact_service",
        lambda component: ScopedArtifactServiceWrapper(
            wrapped_service=test_artifact_service_instance, component=component
        ),
    )

    log_level_str = request.config.getoption("--log-cli-level") or "INFO"

    connector_config = {
        "apps": app_infos,
        "log": {
            "stdout_log_level": log_level_str.upper(),
            "log_file_level": "INFO",
            "enable_trace": False,
        },
    }
    print(
        f"\n[Conftest] Configuring SolaceAiConnector with stdout log level: {log_level_str.upper()}"
    )
    connector = SolaceAiConnector(config=connector_config)
    connector.run()
    print(
        f"shared_solace_connector fixture: Started SolaceAiConnector with apps: {[app['name'] for app in connector_config['apps']]}"
    )

    # Allow time for agent card discovery messages to be exchanged before any test runs
    print("shared_solace_connector fixture: Waiting for agent discovery...")
    time.sleep(5)
    print("shared_solace_connector fixture: Agent discovery wait complete.")

    yield connector

    print("shared_solace_connector fixture: Cleaning up SolaceAiConnector...")
    connector.stop()
    connector.cleanup()
    print("shared_solace_connector fixture: SolaceAiConnector cleaned up.")


@pytest.fixture(scope="session")
def sam_app_under_test(shared_solace_connector: SolaceAiConnector) -> SamAgentApp:
    """
    Retrieves the main SamAgentApp instance from the session-scoped SolaceAiConnector.
    """
    app_instance = shared_solace_connector.get_app("TestSamAgentApp")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve SamAgentApp from shared connector."
    print(
        f"sam_app_under_test fixture: Retrieved app {app_instance.name} from shared SolaceAiConnector."
    )
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_a_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the TestPeerAgentA_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentA_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve TestPeerAgentA_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_b_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the TestPeerAgentB_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentB_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve TestPeerAgentB_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_c_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the TestPeerAgentC_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentC_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve TestPeerAgentC_App."
    yield app_instance


@pytest.fixture(scope="session")
def peer_agent_d_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the TestPeerAgentD_App instance."""
    app_instance = shared_solace_connector.get_app("TestPeerAgentD_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve TestPeerAgentD_App."
    yield app_instance


@pytest.fixture(scope="session")
def combined_dynamic_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the CombinedDynamicAgent_App instance."""
    app_instance = shared_solace_connector.get_app("CombinedDynamicAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve CombinedDynamicAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def empty_provider_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the EmptyProviderAgent_App instance."""
    app_instance = shared_solace_connector.get_app("EmptyProviderAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve EmptyProviderAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def docstringless_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the DocstringlessAgent_App instance."""
    app_instance = shared_solace_connector.get_app("DocstringlessAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve DocstringlessAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def mixed_discovery_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the MixedDiscoveryAgent_App instance."""
    app_instance = shared_solace_connector.get_app("MixedDiscoveryAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve MixedDiscoveryAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def complex_signatures_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the ComplexSignaturesAgent_App instance."""
    app_instance = shared_solace_connector.get_app("ComplexSignaturesAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve ComplexSignaturesAgent_App."
    yield app_instance


@pytest.fixture(scope="session")
def config_context_agent_app_under_test(
    shared_solace_connector: SolaceAiConnector,
) -> SamAgentApp:
    """Retrieves the ConfigContextAgent_App instance."""
    app_instance = shared_solace_connector.get_app("ConfigContextAgent_App")
    assert isinstance(
        app_instance, SamAgentApp
    ), "Failed to retrieve ConfigContextAgent_App."
    yield app_instance


def get_component_from_app(app: SamAgentApp) -> SamAgentComponent:
    """Helper to get the component from an app."""
    if app.flows and app.flows[0].component_groups:
        for group in app.flows[0].component_groups:
            for component_wrapper in group:
                component = (
                    component_wrapper.component
                    if hasattr(component_wrapper, "component")
                    else component_wrapper
                )
                if isinstance(component, SamAgentComponent):
                    return component
    raise RuntimeError("SamAgentComponent not found in the application flow.")


@pytest.fixture(scope="session")
def main_agent_component(sam_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the main SamAgentComponent instance."""
    return get_component_from_app(sam_app_under_test)


@pytest.fixture(scope="session")
def peer_a_component(peer_agent_a_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentA component instance."""
    return get_component_from_app(peer_agent_a_app_under_test)


@pytest.fixture(scope="session")
def peer_b_component(peer_agent_b_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentB component instance."""
    return get_component_from_app(peer_agent_b_app_under_test)


@pytest.fixture(scope="session")
def peer_c_component(peer_agent_c_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentC component instance."""
    return get_component_from_app(peer_agent_c_app_under_test)


@pytest.fixture(scope="session")
def peer_d_component(peer_agent_d_app_under_test: SamAgentApp) -> SamAgentComponent:
    """Retrieves the TestPeerAgentD component instance."""
    return get_component_from_app(peer_agent_d_app_under_test)


@pytest.fixture(scope="session")
def combined_dynamic_agent_component(
    combined_dynamic_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the CombinedDynamicAgent component instance."""
    return get_component_from_app(combined_dynamic_agent_app_under_test)


@pytest.fixture(scope="session")
def empty_provider_agent_component(
    empty_provider_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the EmptyProviderAgent component instance."""
    return get_component_from_app(empty_provider_agent_app_under_test)


@pytest.fixture(scope="session")
def docstringless_agent_component(
    docstringless_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the DocstringlessAgent component instance."""
    return get_component_from_app(docstringless_agent_app_under_test)


@pytest.fixture(scope="session")
def mixed_discovery_agent_component(
    mixed_discovery_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the MixedDiscoveryAgent component instance."""
    return get_component_from_app(mixed_discovery_agent_app_under_test)


@pytest.fixture(scope="session")
def complex_signatures_agent_component(
    complex_signatures_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the ComplexSignaturesAgent component instance."""
    return get_component_from_app(complex_signatures_agent_app_under_test)


@pytest.fixture(scope="session")
def config_context_agent_component(
    config_context_agent_app_under_test: SamAgentApp,
) -> SamAgentComponent:
    """Retrieves the ConfigContextAgent component instance."""
    return get_component_from_app(config_context_agent_app_under_test)


@pytest.fixture(scope="function")
def webui_api_client(
    shared_solace_connector: SolaceAiConnector,
) -> Generator[TestClient, None, None]:
    """
    Provides a FastAPI TestClient for the running WebUIBackendApp.
    """
    app_instance = shared_solace_connector.get_app("WebUIBackendApp")
    assert isinstance(
        app_instance, WebUIBackendApp
    ), "Failed to retrieve WebUIBackendApp from shared connector."

    component_instance = app_instance.get_component()
    assert isinstance(
        component_instance, WebUIBackendComponent
    ), "Failed to retrieve WebUIBackendComponent from WebUIBackendApp."

    fastapi_app_instance = component_instance.fastapi_app
    if not fastapi_app_instance:
        pytest.fail("WebUIBackendComponent's FastAPI app is not initialized.")

    with TestClient(fastapi_app_instance) as client:
        print("[Fixture] TestClient for WebUIBackendApp created.")
        yield client


@pytest.fixture(scope="session")
def a2a_proxy_component(
    shared_solace_connector: SolaceAiConnector,
) -> "BaseProxyComponent":
    """Retrieves the A2AProxyComponent instance."""
    from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent

    app_instance = shared_solace_connector.get_app("TestA2AProxyApp")
    assert app_instance, "Could not find TestA2AProxyApp in the connector."

    if app_instance.flows and app_instance.flows[0].component_groups:
        for group in app_instance.flows[0].component_groups:
            for comp_wrapper in group:
                component = (
                    comp_wrapper.component
                    if hasattr(comp_wrapper, "component")
                    else comp_wrapper
                )
                if isinstance(component, BaseProxyComponent):
                    return component
    raise RuntimeError("A2AProxyComponent not found in the application flow.")


@pytest.fixture(scope="session")
def test_gateway_app_instance(
    shared_solace_connector: SolaceAiConnector,
) -> TestGatewayComponent:
    """
    Retrieves the TestGatewayApp instance from the session-scoped SolaceAiConnector
    and yields its TestGatewayComponent.
    """
    app_instance = shared_solace_connector.get_app("TestHarnessGatewayApp")
    assert isinstance(
        app_instance, TestGatewayApp
    ), "Failed to retrieve TestGatewayApp from shared connector."
    print(
        f"test_gateway_app_instance fixture: Retrieved app {app_instance.name} from shared SolaceAiConnector."
    )

    component_instance = None
    if app_instance.flows and app_instance.flows[0].component_groups:
        for group in app_instance.flows[0].component_groups:
            for comp_wrapper in group:
                actual_comp = (
                    comp_wrapper.component
                    if hasattr(comp_wrapper, "component")
                    else comp_wrapper
                )
                if isinstance(actual_comp, TestGatewayComponent):
                    component_instance = actual_comp
                    break
            if component_instance:
                break

    if not component_instance:
        if hasattr(app_instance, "get_component"):
            comp_from_method = app_instance.get_component()
            if isinstance(comp_from_method, TestGatewayComponent):
                component_instance = comp_from_method
            elif hasattr(comp_from_method, "component") and isinstance(
                comp_from_method.component, TestGatewayComponent
            ):
                component_instance = comp_from_method.component

    if not component_instance:
        pytest.fail(
            "TestGatewayApp did not initialize or TestGatewayComponent instance could not be retrieved via shared SolaceAiConnector."
        )

    print(
        f"[SessionFixture] TestGatewayComponent instance ({component_instance.name}) retrieved for session."
    )
    yield component_instance


@pytest.fixture(autouse=True, scope="function")
def clear_test_gateway_state_between_tests(
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Clears state from the session-scoped TestGatewayComponent after each test.
    """
    yield
    test_gateway_app_instance.clear_captured_outputs()
    test_gateway_app_instance.clear_all_captured_cancel_calls()
    if test_gateway_app_instance.task_context_manager:
        test_gateway_app_instance.task_context_manager.clear_all_contexts_for_testing()


def _clear_agent_component_state(agent_app: SamAgentApp):
    """Helper function to clear state from a SamAgentComponent."""
    component = get_component_from_app(agent_app)

    if component:
        # Clear the central task state dictionary, which now encapsulates all
        # in-flight task information (cancellation, buffers, etc.).
        with component.active_tasks_lock:
            component.active_tasks.clear()

        if (
            hasattr(component, "invocation_monitor")
            and component.invocation_monitor
            and hasattr(component.invocation_monitor, "_reset_session")
        ):
            component.invocation_monitor._reset_session()


@pytest.fixture(autouse=True, scope="function")
def clear_all_agent_states_between_tests(
    sam_app_under_test: SamAgentApp,
    peer_agent_a_app_under_test: SamAgentApp,
    peer_agent_b_app_under_test: SamAgentApp,
    peer_agent_c_app_under_test: SamAgentApp,
    peer_agent_d_app_under_test: SamAgentApp,
    combined_dynamic_agent_app_under_test: SamAgentApp,
    empty_provider_agent_app_under_test: SamAgentApp,
    docstringless_agent_app_under_test: SamAgentApp,
    mixed_discovery_agent_app_under_test: SamAgentApp,
    complex_signatures_agent_app_under_test: SamAgentApp,
    config_context_agent_app_under_test: SamAgentApp,
    a2a_proxy_component: "BaseProxyComponent",
    test_a2a_agent_server_harness: TestA2AAgentServer,
):
    """Clears state from all agent components after each test."""
    yield
    _clear_agent_component_state(sam_app_under_test)
    _clear_agent_component_state(peer_agent_a_app_under_test)
    _clear_agent_component_state(peer_agent_b_app_under_test)
    _clear_agent_component_state(peer_agent_c_app_under_test)
    _clear_agent_component_state(peer_agent_d_app_under_test)
    _clear_agent_component_state(combined_dynamic_agent_app_under_test)
    _clear_agent_component_state(empty_provider_agent_app_under_test)
    _clear_agent_component_state(docstringless_agent_app_under_test)
    _clear_agent_component_state(mixed_discovery_agent_app_under_test)
    _clear_agent_component_state(complex_signatures_agent_app_under_test)
    _clear_agent_component_state(config_context_agent_app_under_test)

    # Clear proxy client cache to ensure fresh clients with updated auth config
    a2a_proxy_component.clear_client_cache()

    # Clear captured auth headers from downstream agent server
    test_a2a_agent_server_harness.clear_captured_auth_headers()

    # Clear captured A2A requests from downstream agent server
    test_a2a_agent_server_harness.clear_captured_requests()

    # Clear auth validation state from downstream agent server
    test_a2a_agent_server_harness.clear_auth_state()


@pytest.fixture(scope="function")
def a2a_message_validator(
    sam_app_under_test: SamAgentApp,
    peer_agent_a_app_under_test: SamAgentApp,
    peer_agent_b_app_under_test: SamAgentApp,
    peer_agent_c_app_under_test: SamAgentApp,
    peer_agent_d_app_under_test: SamAgentApp,
    combined_dynamic_agent_app_under_test: SamAgentApp,
    test_gateway_app_instance: TestGatewayComponent,
) -> A2AMessageValidator:
    """
    Provides an instance of A2AMessageValidator, activated to monitor all
    agent components and the test gateway.
    """
    validator = A2AMessageValidator()

    # Correctly get SamAgentComponent from sam_app_under_test
    sam_agent_component_instance = None
    if sam_app_under_test.flows and sam_app_under_test.flows[0].component_groups:
        for group in sam_app_under_test.flows[0].component_groups:
            for comp_wrapper in group:
                actual_comp = getattr(comp_wrapper, "component", comp_wrapper)
                if isinstance(actual_comp, SamAgentComponent):
                    sam_agent_component_instance = actual_comp
                    break
            if sam_agent_component_instance:
                break

    def get_component_from_app(app: SamAgentApp):
        if app.flows and app.flows[0].component_groups:
            for group in app.flows[0].component_groups:
                for comp_wrapper in group:
                    actual_comp = (
                        comp_wrapper.component
                        if hasattr(comp_wrapper, "component")
                        else comp_wrapper
                    )
                    if isinstance(actual_comp, SamAgentComponent):
                        return actual_comp
        return None

    all_apps = [
        sam_app_under_test,
        peer_agent_a_app_under_test,
        peer_agent_b_app_under_test,
        peer_agent_c_app_under_test,
        peer_agent_d_app_under_test,
        combined_dynamic_agent_app_under_test,
    ]

    components_to_patch = [get_component_from_app(app) for app in all_apps]
    components_to_patch.append(test_gateway_app_instance)

    final_components_to_patch = [c for c in components_to_patch if c is not None]

    if not final_components_to_patch:
        pytest.skip("No suitable components found to patch for A2A validation.")

    print(
        f"A2A Validator activating on components: {[c.name for c in final_components_to_patch]}"
    )
    validator.activate(final_components_to_patch)
    yield validator
    validator.deactivate()


@pytest.fixture(scope="session")
def mock_agent_skills() -> AgentSkill:
    return AgentSkill(
        id="skill-1",
        name="Skill 1",
        description="Description for Skill 1",
        tags=["tag1", "tag2"],
        examples=["Example 1", "Example 2"],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )


@pytest.fixture(scope="session")
def mock_agent_card(mock_agent_skills: AgentSkill) -> AgentCard:
    from a2a.types import (
        AgentCapabilities,
        APIKeySecurityScheme,
        HTTPAuthSecurityScheme,
        In,
        SecurityScheme,
    )

    return AgentCard(
        name="test_agent",
        description="Test Agent Description",
        url="http://test.com/test_path/agent-card.json",
        version="1.0.0",
        protocol_version="0.3.0",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=True,
        ),
        skills=[mock_agent_skills],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        # Support both bearer and apikey authentication (OR relationship)
        security=[{"bearer": []}, {"apikey": []}],
        security_schemes={
            "bearer": SecurityScheme(
                root=HTTPAuthSecurityScheme(type="http", scheme="bearer")
            ),
            "apikey": SecurityScheme(
                root=APIKeySecurityScheme(
                    type="apiKey", name="X-API-Key", in_=In.header
                )
            ),
        },
    )


@pytest.fixture(scope="function")
def mock_task_response() -> Task:
    """
    Provides a mock A2A Task object, using the new helper layer.
    Represents a final, completed task.
    """
    final_status = a2a.create_task_status(
        state=TaskState.completed,
        message=a2a.create_agent_text_message(
            text="Task completed successfully", message_id="msg-agent-complete-1"
        ),
    )
    final_status.timestamp = "2024-01-01T00:00:00Z"  # for deterministic testing

    return a2a.create_final_task(
        task_id="task-123",
        context_id="session-456",
        final_status=final_status,
    )


@pytest.fixture(scope="function")
def mock_task_response_cancel() -> Task:
    """
    Provides a mock A2A Task object, using the new helper layer.
    Represents a final, canceled task.
    """
    final_status = a2a.create_task_status(
        state=TaskState.canceled,
        message=a2a.create_agent_text_message(
            text="Task canceled successfully", message_id="msg-agent-cancel-1"
        ),
    )
    final_status.timestamp = "2023-01-01T00:00:00Z"  # for deterministic testing

    return a2a.create_final_task(
        task_id="task-123",
        context_id="session-456",
        final_status=final_status,
    )


@pytest.fixture(scope="function")
def mock_sse_task_response() -> TaskStatusUpdateEvent:
    """
    Provides a mock A2A TaskStatusUpdateEvent, using the new helper layer.
    Represents an intermediate status update during a streaming response.
    """
    status_message = a2a.create_agent_text_message(
        text="Processing...", message_id="msg-agent-stream-1"
    )
    status_update = a2a.create_status_update(
        task_id="task-123",
        context_id="session-456",
        message=status_message,
        is_final=False,
    )
    status_update.status.timestamp = "2024-01-01T00:00:00Z"  # for deterministic testing
    return status_update


@pytest.fixture(scope="function")
def mock_task_callback_response() -> TaskPushNotificationConfig:
    """
    Provides a mock A2A TaskPushNotificationConfig object.
    """
    return TaskPushNotificationConfig(
        task_id="task-123",
        push_notification_config=PushNotificationConfig(
            id="config-1",
            url="http://test.com/notify",
            token="test-token",
        ),
    )


def test_a2a_sdk_import():
    """Verifies that the a2a-sdk can be imported."""
    try:
        from a2a.types import Task

        assert Task is not None
    except ImportError as e:
        pytest.fail(f"Failed to import from a2a-sdk: {e}")
