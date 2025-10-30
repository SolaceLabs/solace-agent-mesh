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
    broker_input = MagicMock()
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

