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


@pytest.fixture
def yaml_lifecycle_agent_config(
    lifecycle_tracker_path: Path, test_llm_server
) -> Dict[str, Any]:
    """Provides agent config for testing YAML-defined lifecycle hooks on a simple function tool."""
    agent_config = {
        "namespace": "test_namespace/lifecycle_yaml",
        "agent_name": "YamlLifecycleAgent",
        "model": {
            "model": "openai/test-model-lifecycle-yaml",
            "api_base": f"{test_llm_server.url}/v1",
            "api_key": "fake_test_key_lifecycle_yaml",
        },
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "YAML Lifecycle test agent"},
        "agent_card_publishing": {"interval_seconds": 0},
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.tools",
                "function_name": "get_weather_tool",
                "tool_config": {"tracker_file": str(lifecycle_tracker_path)},
                "init_function": "yaml_init_hook",
                "cleanup_function": "yaml_cleanup_hook",
            }
        ],
    }

    return {
        "apps": [
            {
                "name": "YamlLifecycleAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


def test_yaml_configured_hooks(
    yaml_lifecycle_agent_config: Dict[str, Any], lifecycle_tracker_path: Path
):
    """
    Tests that YAML-configured init_function and cleanup_function are called correctly.
    """
    connector = SolaceAiConnector(config=yaml_lifecycle_agent_config)
    connector.run()
    time.sleep(2)

    tracked_lines_after_start = get_tracked_lines(lifecycle_tracker_path)
    assert tracked_lines_after_start == [
        "yaml_init_called"
    ], "Expected YAML init hook to be called on startup."

    connector.stop()
    connector.cleanup()

    tracked_lines_after_stop = get_tracked_lines(lifecycle_tracker_path)
    assert tracked_lines_after_stop == [
        "yaml_init_called",
        "yaml_cleanup_called",
    ], "Expected YAML cleanup hook to be called on shutdown."


@pytest.fixture
def mixed_lifecycle_agent_config(
    lifecycle_tracker_path: Path, test_llm_server
) -> Dict[str, Any]:
    """
    Provides agent config for testing mixed (YAML + DynamicTool method) hooks
    and LIFO cleanup order.
    """
    agent_config = {
        "namespace": "test_namespace/lifecycle_mixed",
        "agent_name": "MixedLifecycleAgent",
        "model": {
            "model": "openai/test-model-lifecycle-mixed",
            "api_base": f"{test_llm_server.url}/v1",
            "api_key": "fake_test_key_lifecycle_mixed",
        },
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "Mixed Lifecycle test agent"},
        "agent_card_publishing": {"interval_seconds": 0},
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.lifecycle_tool",
                "class_name": "LifecycleTestTool",
                "tool_config": {"tracker_file": str(lifecycle_tracker_path)},
                "init_function": "mixed_yaml_init",
                "cleanup_function": "mixed_yaml_cleanup",
            }
        ],
    }

    return {
        "apps": [
            {
                "name": "MixedLifecycleAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


@pytest.fixture
def fatal_init_agent_config(lifecycle_tracker_path: Path) -> Dict[str, Any]:
    """Provides agent config where the tool's init hook is designed to fail."""
    agent_config = {
        "namespace": "test_namespace/lifecycle_fatal",
        "agent_name": "FatalInitAgent",
        "model": {"model": "placeholder"},  # Model won't be reached
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "Fatal init test agent"},
        "agent_card_publishing": {"interval_seconds": 0},
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.tools",
                "function_name": "get_weather_tool",
                "tool_config": {"tracker_file": str(lifecycle_tracker_path)},
                "init_function": "failing_init_hook",
            }
        ],
    }
    return {
        "apps": [
            {
                "name": "FatalInitAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


@pytest.fixture
def non_fatal_cleanup_agent_config(
    lifecycle_tracker_path: Path, test_llm_server
) -> Dict[str, Any]:
    """
    Provides agent config where one cleanup hook fails, to test resilience.
    """
    agent_config = {
        "namespace": "test_namespace/lifecycle_cleanup_fail",
        "agent_name": "CleanupFailAgent",
        "model": {"model": "placeholder"},
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "Cleanup failure test agent"},
        "agent_card_publishing": {"interval_seconds": 0},
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.lifecycle_tool",
                "class_name": "LifecycleTestTool",
                "tool_config": {
                    "tracker_file": str(lifecycle_tracker_path),
                    "test_mode": "cleanup_failure",
                },
                "init_function": "mixed_yaml_init",  # Add a dummy init to match LIFO test
                "cleanup_function": "succeeding_cleanup_hook",  # This one should still run
            }
        ],
    }
    return {
        "apps": [
            {
                "name": "CleanupFailAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


def test_non_fatal_cleanup_failure(
    non_fatal_cleanup_agent_config: Dict[str, Any], lifecycle_tracker_path: Path
):
    """
    Tests that a failure in one cleanup hook does not prevent others from running.
    """
    connector = SolaceAiConnector(config=non_fatal_cleanup_agent_config)
    connector.run()
    time.sleep(2)

    # Stop the connector. This should trigger cleanup.
    # The test should not crash.
    connector.stop()
    connector.cleanup()

    # Assert that the succeeding hook was still called
    tracked_lines = get_tracked_lines(lifecycle_tracker_path)
    assert "step_2_dynamic_init" in tracked_lines
    assert "dynamic_cleanup_started_and_will_fail" in tracked_lines
    assert (
        "succeeding_cleanup_hook_called" in tracked_lines
    ), "The succeeding cleanup hook should have run despite the previous one failing."


@pytest.fixture
def arg_injection_agent_config(
    lifecycle_tracker_path: Path, test_llm_server
) -> Dict[str, Any]:
    """Provides agent config for testing argument injection into lifecycle hooks."""
    agent_config = {
        "namespace": "test_namespace/lifecycle_args",
        "agent_name": "ArgInjectionAgent",
        "model": {"model": "placeholder"},
        "session_service": {"type": "memory"},
        "artifact_service": {"type": "memory"},
        "agent_card": {"description": "Arg injection test agent"},
        "agent_card_publishing": {"interval_seconds": 0},
        "tools": [
            {
                "tool_type": "python",
                "component_module": "tests.integration.test_support.dynamic_tools.lifecycle_tool",
                "class_name": "LifecycleTestTool",
                "tool_config": {
                    "tracker_file": str(lifecycle_tracker_path),
                    "test_mode": "arg_injection",
                    "my_value": "hello_from_config",
                },
                "init_function": "arg_inspector_init_hook",
            }
        ],
    }
    return {
        "apps": [
            {
                "name": "ArgInjectionAgentApp",
                "app_config": agent_config,
                "broker": {"dev_mode": True},
                "app_module": "solace_agent_mesh.agent.sac.app",
            }
        ],
        "log": {"stdout_log_level": "INFO"},
    }


def test_argument_injection(
    arg_injection_agent_config: Dict[str, Any], lifecycle_tracker_path: Path
):
    """
    Tests that 'component' and 'tool_config' are correctly passed to hooks.
    """
    connector = SolaceAiConnector(config=arg_injection_agent_config)
    connector.run()
    time.sleep(2)

    tracked_lines = get_tracked_lines(lifecycle_tracker_path)

    # Assertions for YAML hook
    assert "yaml_init_agent_name:ArgInjectionAgent" in tracked_lines
    assert "yaml_init_my_value:hello_from_config" in tracked_lines

    # Assertions for DynamicTool hook
    assert "dynamic_init_agent_name:ArgInjectionAgent" in tracked_lines
    assert "dynamic_init_my_value:hello_from_config" in tracked_lines

    connector.stop()
    connector.cleanup()
