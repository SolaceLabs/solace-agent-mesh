"""Data factories for creating test data with sensible defaults."""
from typing import Any, Dict


def session_data_factory(
    user_id: str = "sam_dev_user",
    agent_name: str = "TestAgent",
    name: str = "Test Session",
    **overrides
) -> Dict[str, Any]:
    """Create session data for API tests."""
    data = {"user_id": user_id, "agent_name": agent_name, "name": name}
    return {**data, **overrides}


def task_data_factory(
    session_id: str,
    user_message: str = "Test message",
    **overrides
) -> Dict[str, Any]:
    """Create task data for API tests."""
    data = {"session_id": session_id, "user_message": user_message}
    return {**data, **overrides}


def project_data_factory(
    name: str = "Test Project",
    description: str = "Test project description",
    **overrides
) -> Dict[str, Any]:
    """Create project data for API tests."""
    data = {"name": name, "description": description}
    return {**data, **overrides}


def agent_config_factory(
    agent_name: str = "TestAgent",
    namespace: str = "test_namespace",
    model: str = "openai/test-model",
    **overrides
) -> Dict[str, Any]:
    """Create minimal agent configuration for tests."""
    config = {
        "namespace": namespace,
        "agent_name": agent_name,
        "model": {"model": model, "api_key": "fake_test_key"},
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "test_in_memory"},
    }
    return {**config, **overrides}


def gateway_config_factory(
    gateway_id: str = "TestGateway",
    namespace: str = "test_namespace",
    **overrides
) -> Dict[str, Any]:
    """Create minimal gateway configuration for tests."""
    config = {
        "namespace": namespace,
        "gateway_id": gateway_id,
        "artifact_service": {"type": "test_in_memory"},
        "gateway_card_publishing": {"enabled": False},
    }
    return {**config, **overrides}

