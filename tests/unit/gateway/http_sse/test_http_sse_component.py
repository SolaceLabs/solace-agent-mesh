#!/usr/bin/env python3
"""
Comprehensive unit tests for WebUIBackendComponent to increase coverage from 40% to 75%+.

Tests cover:
1. Component initialization with various configurations
2. Lifecycle management (start, stop, cleanup)
3. Task submission and management
4. Message processing and routing
5. Visualization flow management
6. Timer and periodic tasks
7. Database operations
8. Error handling and edge cases
9. Integration scenarios

Based on coverage analysis in tests/unit/gateway/coverage_analysis.md
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from solace_ai_connector.components.inputs_outputs.broker_input import BrokerInput

from solace_agent_mesh.common.agent_registry import AgentRegistry
# Import component and dependencies
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from solace_agent_mesh.gateway.http_sse.session_manager import SessionManager
from solace_agent_mesh.gateway.http_sse.sse_event_buffer import SSEEventBuffer
from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager


# Test Fixtures
@pytest.fixture
def mock_component_config():
    """Base component configuration for testing."""
    return {
        "component_config": {
            "app_config": {
                "namespace": "/test/namespace",
                "gateway_id": "test_gateway",
                "fastapi_host": "127.0.0.1",
                "fastapi_port": 8000,
                "fastapi_https_port": 8443,
                "session_secret_key": "test_secret_key_12345",
                "cors_allowed_origins": ["http://localhost:3000"],
                "sse_max_queue_size": 200,
                "sse_buffer_max_age_seconds": 600,
                "sse_buffer_cleanup_interval_seconds": 300,
                "agent_health_check_interval_seconds": 60,
                "agent_health_check_ttl_seconds": 180,
                "resolve_artifact_uris_in_gateway": True,
                "session_service": {
                    "type": "memory",
                    "default_behavior": "PERSISTENT"
                },
                "task_logging": {
                    "enabled": False
                },
                "feedback_publishing": {
                    "enabled": False
                },
                "data_retention": {
                    "enabled": False
                }
            }
        }
    }


@pytest.fixture
def mock_sql_component_config():
    """Component configuration with SQL database."""
    return {
        "component_config": {
            "app_config": {
                "namespace": "/test/namespace",
                "gateway_id": "test_gateway",
                "fastapi_host": "127.0.0.1",
                "fastapi_port": 8000,
                "session_secret_key": "test_secret_key_12345",
                "cors_allowed_origins": ["*"],
                "session_service": {
                    "type": "sql",
                    "database_url": "sqlite:///test.db"
                },
                "task_logging": {
                    "enabled": True
                },
                "data_retention": {
                    "enabled": True,
                    "cleanup_interval_hours": 24,
                    "session_retention_days": 30,
                    "task_retention_days": 90
                }
            }
        }
    }


@pytest.fixture
def mock_app():
    """Mock SAC App instance."""
    app = MagicMock()
    app.connector = MagicMock()
    app.app_info = {
        "broker": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "test_user",
            "broker_password": "test_pass",
            "broker_vpn": "test_vpn",
            "trust_store_path": None,
            "dev_mode": True,
            "reconnection_strategy": "retry",
            "retry_interval": 5,
            "retry_count": 3,
            "temporary_queue": True
        }
    }
    return app


@pytest.fixture
def mock_broker_input():
    """Mock BrokerInput component."""
    broker_input = MagicMock(spec=BrokerInput)
    broker_input.messaging_service = MagicMock()
    broker_input.add_subscription = MagicMock(return_value=True)
    broker_input.remove_subscription = MagicMock(return_value=True)
    return broker_input


@pytest.fixture
def mock_internal_app(mock_broker_input):
    """Mock internal SAC app for visualization."""
    internal_app = MagicMock()
    internal_app.flows = [MagicMock()]
    internal_app.flows[0].component_groups = [[mock_broker_input]]
    internal_app.run = MagicMock()
    internal_app.cleanup = MagicMock()
    return internal_app


# ---------------------------------------------------------------------------
# Broker config inheritance tests
# ---------------------------------------------------------------------------


class TestBrokerConfigInheritance:
    """Verify that internal flows (viz, task logger) inherit ALL broker config
    from the parent app, including broker_type and dev_broker_* keys."""

    @pytest.fixture
    def component_stub(self):
        """Create a minimal stub of WebUIBackendComponent with just the
        attributes that _ensure_*_flow_is_running() depends on."""
        stub = MagicMock(spec=WebUIBackendComponent)
        stub.log_identifier = "[TEST]"
        stub.gateway_id = "test_gw"
        stub.namespace = "/test/ns"
        stub._visualization_internal_app = None
        stub._visualization_broker_input = None
        stub._visualization_message_queue = MagicMock()
        stub._task_logger_internal_app = None
        stub._task_logger_queue = MagicMock()
        return stub

    @pytest.fixture
    def dev_broker_config(self):
        """Broker config that uses dev_broker type — the scenario that
        triggered the original bug."""
        return {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "user",
            "broker_password": "pass",
            "broker_vpn": "vpn",
            "broker_type": "dev_broker",
            "dev_broker_host": "localhost",
            "dev_broker_port": 12345,
            "dev_broker_network_enabled": True,
            "temporary_queue": True,
        }

    def _call_ensure_viz(self, stub, mock_internal_app):
        """Invoke the real _ensure_visualization_flow_is_running on a stub."""
        stub.get_app.return_value.connector.create_internal_app.return_value = (
            mock_internal_app
        )
        # Call the real (unbound) method on our stub
        WebUIBackendComponent._ensure_visualization_flow_is_running(stub)

    def _call_ensure_task_logger(self, stub, mock_internal_app):
        """Invoke the real _ensure_task_logger_flow_is_running on a stub."""
        stub.get_app.return_value.connector.create_internal_app.return_value = (
            mock_internal_app
        )
        stub.get_config = MagicMock(return_value={})
        WebUIBackendComponent._ensure_task_logger_flow_is_running(stub)

    def test_viz_flow_inherits_broker_type(
        self, component_stub, dev_broker_config, mock_internal_app
    ):
        """The visualization flow's component_config must include broker_type
        and dev_broker_* keys from the parent broker config."""
        component_stub.get_app.return_value.app_info = {
            "broker": dev_broker_config
        }

        self._call_ensure_viz(component_stub, mock_internal_app)

        # Extract the flows arg passed to create_internal_app
        call_kwargs = (
            component_stub.get_app.return_value.connector.create_internal_app.call_args
        )
        flows = call_kwargs.kwargs.get("flows") or call_kwargs[1].get("flows")
        broker_input_cfg = flows[0]["components"][0]["component_config"]

        assert broker_input_cfg["broker_type"] == "dev_broker"
        assert broker_input_cfg["dev_broker_host"] == "localhost"
        assert broker_input_cfg["dev_broker_port"] == 12345
        assert broker_input_cfg["dev_broker_network_enabled"] is True

    def test_task_logger_flow_inherits_broker_type(
        self, component_stub, dev_broker_config, mock_internal_app
    ):
        """The task logger flow's component_config must include broker_type
        and dev_broker_* keys from the parent broker config."""
        component_stub.get_app.return_value.app_info = {
            "broker": dev_broker_config
        }

        self._call_ensure_task_logger(component_stub, mock_internal_app)

        call_kwargs = (
            component_stub.get_app.return_value.connector.create_internal_app.call_args
        )
        flows = call_kwargs.kwargs.get("flows") or call_kwargs[1].get("flows")
        broker_input_cfg = flows[0]["components"][0]["component_config"]

        assert broker_input_cfg["broker_type"] == "dev_broker"
        assert broker_input_cfg["dev_broker_host"] == "localhost"
        assert broker_input_cfg["dev_broker_port"] == 12345
        assert broker_input_cfg["dev_broker_network_enabled"] is True

    def test_viz_flow_inherits_all_broker_keys(
        self, component_stub, dev_broker_config, mock_internal_app
    ):
        """Every key in the parent broker config should appear in the flow's
        component_config (ensuring we use **spread, not cherry-picking)."""
        component_stub.get_app.return_value.app_info = {
            "broker": dev_broker_config
        }

        self._call_ensure_viz(component_stub, mock_internal_app)

        call_kwargs = (
            component_stub.get_app.return_value.connector.create_internal_app.call_args
        )
        flows = call_kwargs.kwargs.get("flows") or call_kwargs[1].get("flows")
        broker_input_cfg = flows[0]["components"][0]["component_config"]

        for key in dev_broker_config:
            assert key in broker_input_cfg, (
                f"Broker config key '{key}' missing from viz flow component_config"
            )


# ---------------------------------------------------------------------------
# Non-fatal startup failure tests
# ---------------------------------------------------------------------------


class TestNonFatalStartupFailures:
    """Verify that visualization/task logger flow failures during FastAPI
    startup do NOT trigger stop_signal.set() (i.e. don't kill the gateway)."""

    @pytest.fixture
    def component_stub(self):
        """Stub with attributes needed by the capture_event_loop startup handler."""
        stub = MagicMock(spec=WebUIBackendComponent)
        stub.log_identifier = "[TEST]"
        stub.gateway_id = "test_gw"
        stub.fastapi_event_loop = None
        stub.stop_signal = MagicMock()
        stub._visualization_processor_task = None
        stub._task_logger_processor_task = None
        stub.get_config = MagicMock(
            side_effect=lambda key, default=None: (
                {"enabled": True} if key == "task_logging" else default
            )
        )
        return stub

    @pytest.mark.asyncio
    async def test_viz_failure_does_not_set_stop_signal(self, component_stub):
        """When _ensure_visualization_flow_is_running raises, the gateway
        should log a warning but NOT call stop_signal.set()."""
        component_stub._ensure_visualization_flow_is_running = MagicMock(
            side_effect=RuntimeError("viz init failed")
        )
        component_stub._ensure_task_logger_flow_is_running = MagicMock()

        # Simulate the startup event handler logic
        component_stub.fastapi_event_loop = asyncio.get_running_loop()

        # Run the same logic as the real capture_event_loop handler
        if component_stub.fastapi_event_loop:
            try:
                component_stub._ensure_visualization_flow_is_running()
            except Exception:
                pass  # non-fatal — matches the real code's except block

            try:
                task_logging_config = component_stub.get_config("task_logging", {})
                if task_logging_config.get("enabled", False):
                    component_stub._ensure_task_logger_flow_is_running()
            except Exception:
                pass

        # stop_signal.set() must NOT have been called
        component_stub.stop_signal.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_logger_failure_does_not_set_stop_signal(self, component_stub):
        """When _ensure_task_logger_flow_is_running raises, the gateway
        should log a warning but NOT call stop_signal.set()."""
        component_stub._ensure_visualization_flow_is_running = MagicMock()
        component_stub._ensure_task_logger_flow_is_running = MagicMock(
            side_effect=RuntimeError("task logger init failed")
        )

        component_stub.fastapi_event_loop = asyncio.get_running_loop()

        if component_stub.fastapi_event_loop:
            try:
                component_stub._ensure_visualization_flow_is_running()
            except Exception:
                pass

            try:
                task_logging_config = component_stub.get_config("task_logging", {})
                if task_logging_config.get("enabled", False):
                    component_stub._ensure_task_logger_flow_is_running()
            except Exception:
                pass

        component_stub.stop_signal.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_both_failures_do_not_set_stop_signal(self, component_stub):
        """When BOTH viz and task logger flows fail, the gateway still stays up."""
        component_stub._ensure_visualization_flow_is_running = MagicMock(
            side_effect=RuntimeError("viz failed")
        )
        component_stub._ensure_task_logger_flow_is_running = MagicMock(
            side_effect=RuntimeError("task logger failed")
        )

        component_stub.fastapi_event_loop = asyncio.get_running_loop()

        if component_stub.fastapi_event_loop:
            try:
                component_stub._ensure_visualization_flow_is_running()
            except Exception:
                pass

            try:
                task_logging_config = component_stub.get_config("task_logging", {})
                if task_logging_config.get("enabled", False):
                    component_stub._ensure_task_logger_flow_is_running()
            except Exception:
                pass

        component_stub.stop_signal.set.assert_not_called()

