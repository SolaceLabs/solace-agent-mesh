"""
Stress test configuration and fixtures.

Integrates with existing SAM test infrastructure while providing
stress-test-specific configuration and metrics collection.
"""

import pytest
import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional, Generator, TYPE_CHECKING
import logging

# Use pytest_plugins to load all fixtures from the integration tests
# This is the recommended way to share fixtures across test directories
pytest_plugins = ["tests.integration.conftest"]

from tests.stress.metrics.collector import MetricsCollector
from tests.stress.metrics.reporter import MetricsReporter

if TYPE_CHECKING:
    from starlette.testclient import TestClient
    from sam_test_infrastructure.gateway_interface.component import TestGatewayComponent
    from sam_test_infrastructure.llm_server.server import TestLLMServer
    from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager

logger = logging.getLogger(__name__)


@dataclass
class SSEManagerMetrics:
    """Snapshot of SSEManager internal metrics for leak detection."""

    active_connections: int
    background_task_cache_size: int
    tasks_with_prior_connection: int
    connection_task_ids: list
    cached_task_ids: list
    prior_connection_task_ids: list

    @classmethod
    def from_sse_manager(cls, sse_manager: "SSEManager") -> "SSEManagerMetrics":
        """Create a metrics snapshot from an SSEManager instance."""
        return cls(
            active_connections=len(sse_manager._connections),
            background_task_cache_size=len(sse_manager._background_task_cache),
            tasks_with_prior_connection=len(sse_manager._tasks_with_prior_connection),
            connection_task_ids=list(sse_manager._connections.keys()),
            cached_task_ids=list(sse_manager._background_task_cache.keys()),
            prior_connection_task_ids=list(sse_manager._tasks_with_prior_connection),
        )


# Fixtures from integration conftest are loaded via pytest_plugins above


@dataclass
class StressTestConfig:
    """
    Configurable stress test parameters.

    These can be overridden via environment variables or pytest options.
    """

    # Connection parameters
    concurrent_sse_connections: int = 10
    concurrent_sessions: int = 5
    concurrent_http_requests: int = 20

    # Duration parameters
    test_duration_seconds: float = 30.0
    soak_duration_seconds: float = 300.0  # 5 minutes for soak tests
    warmup_seconds: float = 2.0

    # Load parameters
    events_per_second: int = 100
    requests_per_second: int = 50

    # Artifact parameters
    small_artifact_size_bytes: int = 1024  # 1KB
    medium_artifact_size_bytes: int = 1024 * 1024  # 1MB
    large_artifact_size_bytes: int = 10 * 1024 * 1024  # 10MB
    max_artifact_size_bytes: int = 50 * 1024 * 1024  # 50MB (default gateway limit)

    # Thresholds for assertions
    max_p99_latency_ms: float = 500.0
    max_error_rate_percent: float = 1.0
    memory_increase_threshold_mb: float = 50.0

    # SSE specific
    sse_queue_timeout_seconds: float = 0.1  # Match SSEManager's 0.1s timeout
    max_sse_queue_size: int = 200
    sse_event_timeout_seconds: float = 120.0

    # Retry/resilience
    max_retries: int = 3
    retry_delay_seconds: float = 0.5

    @classmethod
    def from_env(cls) -> "StressTestConfig":
        """Create config from environment variables."""
        config = cls()

        # Override from environment if present
        env_mappings = {
            "STRESS_CONCURRENT_SSE": "concurrent_sse_connections",
            "STRESS_CONCURRENT_SESSIONS": "concurrent_sessions",
            "STRESS_DURATION": "test_duration_seconds",
            "STRESS_SOAK_DURATION": "soak_duration_seconds",
            "STRESS_MAX_P99_LATENCY": "max_p99_latency_ms",
            "STRESS_MAX_ERROR_RATE": "max_error_rate_percent",
        }

        for env_var, attr in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                attr_type = type(getattr(config, attr))
                setattr(config, attr, attr_type(value))

        return config


# Predefined scale profiles
SCALE_PROFILES = {
    "smoke": StressTestConfig(
        concurrent_sse_connections=3,
        concurrent_sessions=2,
        test_duration_seconds=5.0,
        max_p99_latency_ms=1000.0,
    ),
    "small": StressTestConfig(
        concurrent_sse_connections=5,
        concurrent_sessions=3,
        test_duration_seconds=10.0,
    ),
    "medium": StressTestConfig(
        concurrent_sse_connections=25,
        concurrent_sessions=10,
        test_duration_seconds=30.0,
    ),
    "large": StressTestConfig(
        concurrent_sse_connections=100,
        concurrent_sessions=50,
        test_duration_seconds=60.0,
    ),
    "soak": StressTestConfig(
        concurrent_sse_connections=10,
        concurrent_sessions=5,
        test_duration_seconds=60.0,
        soak_duration_seconds=300.0,
    ),
}


def pytest_addoption(parser):
    """Add stress test CLI options."""
    parser.addoption(
        "--stress-scale",
        action="store",
        default="small",
        choices=list(SCALE_PROFILES.keys()),
        help="Scale profile for stress tests",
    )
    parser.addoption(
        "--stress-report",
        action="store",
        default=None,
        help="Path to save JSON stress test report",
    )
    parser.addoption(
        "--stress-duration",
        action="store",
        type=float,
        default=None,
        help="Override test duration in seconds",
    )


@pytest.fixture(scope="session")
def stress_config(request) -> StressTestConfig:
    """
    Session-scoped stress test configuration.

    Uses scale profile from CLI or environment, with optional overrides.
    """
    scale = request.config.getoption("--stress-scale", "small")
    config = SCALE_PROFILES.get(scale, SCALE_PROFILES["small"])

    # Apply CLI overrides
    duration_override = request.config.getoption("--stress-duration")
    if duration_override:
        config.test_duration_seconds = duration_override

    # Apply environment overrides
    env_config = StressTestConfig.from_env()
    for attr in ["concurrent_sse_connections", "concurrent_sessions"]:
        env_val = getattr(env_config, attr)
        default_val = getattr(StressTestConfig(), attr)
        if env_val != default_val:
            setattr(config, attr, env_val)

    logger.info(f"Stress test config: scale={scale}, config={config}")
    return config


@pytest.fixture(scope="function")
def metrics_collector() -> Generator[MetricsCollector, None, None]:
    """
    Function-scoped metrics collector.

    Provides a fresh MetricsCollector for each test.
    """
    collector = MetricsCollector()
    yield collector
    # Optionally log summary after test
    if collector.get_duration_seconds() > 0:
        summary = collector.get_summary()
        logger.info(
            f"Test metrics: duration={summary['duration_seconds']:.1f}s, "
            f"errors={summary['total_errors']}, "
            f"operations={list(summary['operations'].keys())}"
        )


@pytest.fixture(scope="function")
def metrics_reporter(
    metrics_collector: MetricsCollector, request
) -> Generator[MetricsReporter, None, None]:
    """
    Function-scoped metrics reporter.

    Automatically prints summary after test and optionally saves JSON report.
    """
    test_name = request.node.name
    reporter = MetricsReporter(metrics_collector, test_name=test_name)

    yield reporter

    # Print summary after test
    if metrics_collector.get_duration_seconds() > 0:
        reporter.print_summary()

        # Save JSON report if requested
        report_path = request.config.getoption("--stress-report")
        if report_path:
            # Append test name to make unique
            base, ext = os.path.splitext(report_path)
            test_report_path = f"{base}_{test_name}{ext}"
            reporter.save_json(test_report_path)
            logger.info(f"Saved stress report to {test_report_path}")


@pytest.fixture(scope="function")
def sse_manager_for_metrics(shared_solace_connector):
    """
    Provides direct access to SSEManager for inspecting connection metrics.

    This allows leak detection tests to directly inspect internal data structures
    without modifying production code.

    Returns the SSEManager instance from the WebUIBackendApp.
    """
    from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
    from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

    app_instance = shared_solace_connector.get_app("WebUIBackendApp")
    assert isinstance(
        app_instance, WebUIBackendApp
    ), "Failed to retrieve WebUIBackendApp from shared connector."

    component_instance = app_instance.get_component()
    assert isinstance(
        component_instance, WebUIBackendComponent
    ), "Failed to retrieve WebUIBackendComponent from WebUIBackendApp."

    sse_manager = component_instance.get_sse_manager()
    assert sse_manager is not None, "SSEManager is not initialized."

    return sse_manager


def get_sse_manager_metrics(sse_manager) -> SSEManagerMetrics:
    """
    Helper function to get a snapshot of SSEManager metrics.

    Can be called multiple times during a test to compare state.
    """
    return SSEManagerMetrics.from_sse_manager(sse_manager)


@pytest.fixture(scope="function")
def webui_base_url(webui_api_client: "TestClient") -> str:
    """
    Get the base URL for the WebUI backend.

    For TestClient, this returns the test server URL.
    """
    # TestClient uses a special test URL
    return "http://testserver"


@pytest.fixture(scope="function")
def stress_http_client(
    webui_api_client: "TestClient",
    metrics_collector: MetricsCollector,
):
    """
    HTTP client configured for stress testing.

    Uses the existing webui_api_client TestClient for making requests.
    Note: This uses synchronous TestClient which blocks the event loop.
    For true async HTTP, use async_stress_http_client instead.
    """
    from tests.stress.harness.http_client import StressHTTPClient

    # Create a wrapper that uses TestClient
    return TestClientHTTPAdapter(webui_api_client, metrics_collector)


@pytest.fixture(scope="function")
def async_stress_http_client(
    shared_solace_connector,
    metrics_collector: MetricsCollector,
):
    """
    Truly async HTTP client for stress testing.

    Uses httpx with ASGI transport for non-blocking HTTP requests.
    This enables genuine concurrent operations - multiple HTTP requests
    can be in flight simultaneously without blocking the event loop.

    Usage in tests:
        async with async_stress_http_client as client:
            await client.get_config()

    Or for concurrent requests:
        async with async_stress_http_client as client:
            tasks = [client.get_config() for _ in range(10)]
            results = await asyncio.gather(*tasks)  # True parallelism!
    """
    from solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
    from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent

    app_instance = shared_solace_connector.get_app("WebUIBackendApp")
    assert isinstance(
        app_instance, WebUIBackendApp
    ), "Failed to retrieve WebUIBackendApp from shared connector."

    component_instance = app_instance.get_component()
    assert isinstance(
        component_instance, WebUIBackendComponent
    ), "Failed to retrieve WebUIBackendComponent from WebUIBackendApp."

    fastapi_app = component_instance.fastapi_app
    if not fastapi_app:
        pytest.fail("WebUIBackendComponent's FastAPI app is not initialized.")

    return AsyncHTTPAdapter(fastapi_app, metrics_collector)


class TestClientHTTPAdapter:
    """
    Adapter that wraps Starlette's TestClient to work with our StressHTTPClient interface.

    This allows stress tests to use the synchronous TestClient while maintaining
    the async interface expected by the stress harness.
    """

    def __init__(
        self,
        test_client: "TestClient",
        metrics_collector: MetricsCollector,
    ):
        self.client = test_client
        self.metrics = metrics_collector

    async def request(
        self,
        method: str,
        path: str,
        operation_name: str,
        **kwargs,
    ):
        """Make HTTP request with metrics collection."""
        import time

        start = time.monotonic()
        try:
            response = self.client.request(method, path, **kwargs)
            latency_ms = (time.monotonic() - start) * 1000

            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.increment_counter(f"{operation_name}_total")

            if response.status_code >= 400:
                await self.metrics.increment_counter(f"{operation_name}_errors")

            return response

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.record_error(operation_name, e, {"path": path})
            raise

    async def get(self, path: str, operation_name: str, **kwargs):
        return await self.request("GET", path, operation_name, **kwargs)

    async def post(self, path: str, operation_name: str, **kwargs):
        return await self.request("POST", path, operation_name, **kwargs)

    async def put(self, path: str, operation_name: str, **kwargs):
        return await self.request("PUT", path, operation_name, **kwargs)

    async def delete(self, path: str, operation_name: str, **kwargs):
        return await self.request("DELETE", path, operation_name, **kwargs)

    async def upload_artifact(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ):
        """Upload artifact with metrics."""
        files = {"upload_file": (filename, content, mime_type)}
        data = {"sessionId": session_id, "filename": filename}

        return await self.post(
            "/api/v1/artifacts/upload",
            "artifact_upload",
            files=files,
            data=data,
        )

    async def download_artifact(self, session_id: str, filename: str):
        """Download artifact with metrics."""
        return await self.get(
            f"/api/v1/artifacts/{session_id}/{filename}",
            "artifact_download",
        )

    async def get_config(self):
        """Get server configuration."""
        return await self.get("/api/v1/config", "config_fetch")

    async def get_agent_cards(self):
        """Get agent cards."""
        return await self.get("/api/v1/agent-cards", "agent_cards_fetch")

    async def get_sessions(self):
        """Get sessions list."""
        return await self.get("/api/v1/sessions", "sessions_list")

    async def create_session(self, name: Optional[str] = None):
        """Create a new session."""
        json_body = {}
        if name:
            json_body["name"] = name
        return await self.post(
            "/api/v1/sessions",
            "session_create",
            json=json_body if json_body else None,
        )


class AsyncHTTPAdapter:
    """
    Truly async HTTP adapter using httpx with ASGI transport.

    Unlike TestClientHTTPAdapter which uses synchronous TestClient and blocks
    the event loop, this adapter provides true non-blocking async HTTP requests.
    This enables genuine concurrent HTTP operations in stress tests.
    """

    def __init__(
        self,
        app,
        metrics_collector: MetricsCollector,
    ):
        self.app = app
        self.metrics = metrics_collector
        self.client = None

    async def __aenter__(self):
        """Start the async HTTP client."""
        import httpx

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the async HTTP client."""
        if self.client:
            await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        operation_name: str,
        **kwargs,
    ):
        """Make HTTP request with metrics collection - truly async."""
        import time

        if not self.client:
            raise RuntimeError("AsyncHTTPAdapter must be used as async context manager")

        start = time.monotonic()
        try:
            response = await self.client.request(method, path, **kwargs)
            latency_ms = (time.monotonic() - start) * 1000

            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.increment_counter(f"{operation_name}_total")

            if response.status_code >= 400:
                await self.metrics.increment_counter(f"{operation_name}_errors")

            return response

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            await self.metrics.record_latency(operation_name, latency_ms)
            await self.metrics.record_error(operation_name, e, {"path": path})
            raise

    async def get(self, path: str, operation_name: str, **kwargs):
        return await self.request("GET", path, operation_name, **kwargs)

    async def post(self, path: str, operation_name: str, **kwargs):
        return await self.request("POST", path, operation_name, **kwargs)

    async def put(self, path: str, operation_name: str, **kwargs):
        return await self.request("PUT", path, operation_name, **kwargs)

    async def delete(self, path: str, operation_name: str, **kwargs):
        return await self.request("DELETE", path, operation_name, **kwargs)

    async def upload_artifact(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
    ):
        """Upload artifact with metrics."""
        files = {"upload_file": (filename, content, mime_type)}
        data = {"sessionId": session_id, "filename": filename}

        return await self.post(
            "/api/v1/artifacts/upload",
            "artifact_upload",
            files=files,
            data=data,
        )

    async def download_artifact(self, session_id: str, filename: str):
        """Download artifact with metrics."""
        return await self.get(
            f"/api/v1/artifacts/{session_id}/{filename}",
            "artifact_download",
        )

    async def get_config(self):
        """Get server configuration."""
        return await self.get("/api/v1/config", "config_fetch")

    async def get_agent_cards(self):
        """Get agent cards."""
        return await self.get("/api/v1/agent-cards", "agent_cards_fetch")

    async def get_sessions(self):
        """Get sessions list."""
        return await self.get("/api/v1/sessions", "sessions_list")

    async def create_session(self, name: Optional[str] = None):
        """Create a new session."""
        json_body = {}
        if name:
            json_body["name"] = name
        return await self.post(
            "/api/v1/sessions",
            "session_create",
            json=json_body if json_body else None,
        )


@pytest.fixture(scope="function")
def stress_sse_client_factory(
    webui_api_client: "TestClient",
    metrics_collector: MetricsCollector,
):
    """
    Factory for creating SSE clients for stress testing.

    Returns a factory function that creates SSE client instances.
    """
    from tests.stress.harness.sse_client import StressSSEClient

    def create_client(client_id: str) -> StressSSEClient:
        return StressSSEClient(
            base_url="http://testserver",
            client_id=client_id,
            metrics_collector=metrics_collector,
        )

    return create_client


# Memory monitoring fixture (optional - requires psutil, pympler, objgraph)
@pytest.fixture(scope="function")
def memory_monitor(stress_config: StressTestConfig):
    """
    Memory monitor for detecting leaks in soak tests.

    Only available if memory monitoring dependencies are installed.
    """
    try:
        from sam_test_infrastructure.memory_monitor.memory_monitor import MemoryMonitor

        # Create but don't start - let the test control when to start
        return MemoryMonitor
    except ImportError:
        pytest.skip("Memory monitoring requires psutil, pympler, and objgraph")


# Cleanup fixture
@pytest.fixture(autouse=True, scope="function")
def cleanup_after_stress_test(
    test_gateway_app_instance: "TestGatewayComponent",
):
    """
    Auto-cleanup fixture that runs after each stress test.

    Ensures test infrastructure is in clean state.
    """
    yield

    # Clear captured outputs
    test_gateway_app_instance.clear_captured_outputs()
    test_gateway_app_instance.clear_all_captured_cancel_calls()

    # Clear task context if available
    if test_gateway_app_instance.task_context_manager:
        test_gateway_app_instance.task_context_manager.clear_all_contexts_for_testing()


# Pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "stress: marks tests as stress tests (may be slow)"
    )
    config.addinivalue_line(
        "markers", "long_soak: marks tests as long-running soak tests"
    )
    config.addinivalue_line(
        "markers", "isolation: marks tests for WebUI/A2A isolation testing"
    )
    config.addinivalue_line(
        "markers", "artifacts: marks tests for artifact handling"
    )
    config.addinivalue_line(
        "markers", "scalability: marks tests for session scalability"
    )
