import pytest
import time
from pathlib import Path
from typing import Dict, Any, Generator

from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from tests.integration.test_support.lifecycle_tracker import (
    get_tracked_lines,
    cleanup_tracker,
)


@pytest.fixture
def lifecycle_tracker_path(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides a unique path for a tracker file and ensures it's clean."""
    tracker_file = tmp_path / "lifecycle_events.log"
    cleanup_tracker(tracker_file)
    yield tracker_file
    cleanup_tracker(tracker_file)


@pytest.fixture
def lifecycle_agent_config(
    lifecycle_tracker_path: Path, test_llm_server
) -> Dict[str, Any]:
    """Provides the configuration for a SolaceAiConnector with a single agent for lifecycle testing."""
    agent_config = {
        "namespace": "test_namespace/lifecycle",
        "supports_streaming": True,
        "agent_name": "LifecycleAgent",
        "model": {
            "model": "openai/test-model-lifecycle",
            "api_base": f"{test_llm_server.url}/v1",
            "api_key": "fake_test_key_lifecycle",
        },
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "Lifecycle test agent"},
        "agent_card_publishing": {"interval_seconds": 0},  # Disable for this test
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.lifecycle_tool",
                "class_name": "LifecycleTestTool",
                "tool_config": {"tracker_file": str(lifecycle_tracker_path)},
            }
        ],
    }

    return {
        "apps": [
            {
                "name": "LifecycleAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


def test_dynamic_tool_method_hooks(
    lifecycle_agent_config: Dict[str, Any], lifecycle_tracker_path: Path
):
    """
    Tests that a DynamicTool's init() and cleanup() methods are called correctly.
    """
    # 1. Initialize and run the connector
    connector = SolaceAiConnector(config=lifecycle_agent_config)
    connector.run()

    # Allow time for the agent to fully initialize
    time.sleep(2)

    # 2. Assert init() was called
    tracked_lines_after_start = get_tracked_lines(lifecycle_tracker_path)
    assert tracked_lines_after_start == [
        "dynamic_init_called"
    ], "Expected init hook to be called on startup."

    # 3. Stop and cleanup the connector
    connector.stop()
    connector.cleanup()

    # 4. Assert cleanup() was called in the correct order
    tracked_lines_after_stop = get_tracked_lines(lifecycle_tracker_path)
    assert tracked_lines_after_stop == [
        "dynamic_init_called",
        "dynamic_cleanup_called",
    ], "Expected cleanup hook to be called after init hook on shutdown."
