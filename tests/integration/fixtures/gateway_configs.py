"""Gateway configuration fixtures for integration tests.

This module contains all gateway configuration dictionaries.
Extracted from the main integration conftest to improve maintainability.
"""

import pytest


@pytest.fixture(scope="session")
def minimal_gateway_config():
    """Minimal gateway configuration for basic testing."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "MinimalTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.MinimalAdapter",
        "adapter_config": {
            "default_user_id": "minimal-user@example.com",
            "default_target_agent": "TestAgent",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "default-user@example.com",
        "gateway_card_publishing": {"enabled": False},
    }


@pytest.fixture(scope="session")
def auth_gateway_config():
    """Auth gateway configuration for authentication testing."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "AuthTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.AuthTestAdapter",
        "adapter_config": {
            "require_token": False,
            "valid_token": "valid-test-token",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "fallback-user@example.com",
        "gateway_card_publishing": {"enabled": False},
    }


@pytest.fixture(scope="session")
def file_gateway_config():
    """File gateway configuration for file handling testing."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "FileTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.FileAdapter",
        "adapter_config": {
            "max_file_size": 1024 * 1024,
        },
        "artifact_service": {"type": "test_in_memory"},
        "gateway_card_publishing": {"enabled": False},
    }


@pytest.fixture(scope="session")
def dispatching_gateway_config():
    """Dispatching gateway configuration for dispatch testing."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "DispatchingTestGateway",
        "gateway_adapter": "tests.integration.gateway.generic.fixtures.mock_adapters.DispatchingAdapter",
        "adapter_config": {
            "default_user_id": "dispatch-user@example.com",
            "default_target_agent": "TestAgent",
        },
        "artifact_service": {"type": "test_in_memory"},
        "default_user_identity": "default-dispatch@example.com",
        "gateway_card_publishing": {"enabled": False},
    }


@pytest.fixture(scope="session")
def webui_gateway_config(test_db_engine):
    """WebUI gateway configuration for HTTP SSE testing."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "TestWebUIGateway_01",
        "session_secret_key": "a_secure_test_secret_key",
        "session_service": {
            "type": "sql",
            "database_url": str(test_db_engine.url),
        },
        "task_logging": {"enabled": True},
        "artifact_service": {"type": "test_in_memory"},
        "gateway_card_publishing": {"enabled": False},
    }


@pytest.fixture(scope="session")
def test_harness_gateway_config():
    """Test harness gateway configuration."""
    return {
        "namespace": "test_namespace",
        "gateway_id": "TestHarnessGateway_01",
        "artifact_service": {"type": "test_in_memory"},
        "task_logging": {"enabled": False},
        "system_purpose": "Test gateway system purpose for metadata validation",
        "response_format": "Test gateway response format for metadata validation",
        "gateway_card_publishing": {"enabled": False},
    }
