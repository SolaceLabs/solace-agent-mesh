# Implementation Plan: Declarative Tests for Dynamic Tools

This document outlines the detailed plan to create declarative integration tests for the dynamic tools feature.

### Part 1: Create Python Modules for Testing

We will create a new directory and three Python files containing different dynamic tool patterns. These will serve as the `component_module` for our tests.

1.  **Create New Directory**:
    *   `tests/integration/test_support/dynamic_tools/`

2.  **Create `single_tool.py`**:
    *   **Path**: `tests/integration/test_support/dynamic_tools/single_tool.py`
    *   **Purpose**: To test auto-discovery of a single `DynamicTool` class.
    *   **Contents**: A class `MySingleDynamicTool` inheriting from `DynamicTool`. It should have a unique name (e.g., `single_dynamic_tool_test`) and return a simple, verifiable dictionary.

3.  **Create `provider_tool.py`**:
    *   **Path**: `tests/integration/test_support/dynamic_tools/provider_tool.py`
    *   **Purpose**: To test the `DynamicToolProvider` pattern.
    *   **Contents**: A class `MyToolProvider` inheriting from `DynamicToolProvider`. Its `create_tools` method will return a list containing two distinct `DynamicTool` instances (`ProviderToolOne` and `ProviderToolTwo`), each with unique names and outputs.

4.  **Create `hybrid_tools.py`**:
    *   **Path**: `tests/integration/test_support/dynamic_tools/hybrid_tools.py`
    *   **Purpose**: To test explicit loading from a module containing multiple tool types.
    *   **Contents**:
        *   A class `SelectableDynamicTool` (inherits from `DynamicTool`).
        *   A class `SelectableToolProvider` (inherits from `DynamicToolProvider`).
        *   An `async` function `selectable_function_tool`.

### Part 2: Enhance Test Infrastructure

To run tests against specific agent configurations, we need to enhance the test harness to dynamically manage agent lifecycles.

1.  **Modify `SolaceAiConnector`**:
    *   **File**: `solace_ai_connector/solace_ai_connector.py`
    *   **Goal**: Add methods to dynamically add and remove agent applications at runtime.
    *   **Actions**:
        *   Implement `add_app(self, app_config: dict)`: This method will take a standard app configuration dictionary, instantiate the app class, run its initialization, and add it to the connector's list of running apps.
        *   Implement `remove_app(self, app_name: str)`: This method will find the app by name, call its cleanup/stop methods, and remove it from the connector.

2.  **Create `dynamic_agent_harness` Fixture**:
    *   **File**: `tests/integration/conftest.py`
    *   **Goal**: Create a function-scoped pytest fixture that provides a clean, temporary agent for a single test.
    *   **Actions**:
        *   Define a new fixture named `dynamic_agent_harness`.
        *   The fixture will be a factory that takes an `agent_config` dictionary as input.
        *   Inside the factory function:
            *   It will call `shared_solace_connector.add_app(agent_config)`.
            *   It will poll the `AgentRegistry` until the new agent's card is discovered, with a reasonable timeout.
            *   It will `yield` the new agent's name to the test function.
            *   In a `finally` block, it will call `shared_solace_connector.remove_app(agent_name)` to ensure cleanup.

### Part 3: Write Declarative YAML Tests

We will create a new directory and a series of YAML test files that use the new harness.

1.  **Create New Directory**:
    *   `tests/integration/scenarios_declarative/test_data/dynamic_tools/`

2.  **Create `test_single_tool_auto_discovery.yaml`**:
    *   **Harness**: Use `dynamic_agent_harness` to create an agent.
    *   **Agent Config**: `tool_type: python`, `component_module: tests.integration.test_support.dynamic_tools.single_tool`. No `class_name` specified.
    *   **Test Flow**: Send a prompt that invokes the `single_dynamic_tool_test` tool and verify its output.

3.  **Create `test_provider_auto_discovery.yaml`**:
    *   **Harness**: Use `dynamic_agent_harness`.
    *   **Agent Config**: `tool_type: python`, `component_module: tests.integration.test_support.dynamic_tools.provider_tool`.
    *   **Test Flow**: Send two separate prompts to invoke `ProviderToolOne` and `ProviderToolTwo` and verify their distinct outputs.

4.  **Create `test_explicit_class_loading.yaml`**:
    *   **Harness**: Use `dynamic_agent_harness`.
    *   **Agent Config**: `tool_type: python`, `component_module: tests.integration.test_support.dynamic_tools.hybrid_tools`, `class_name: "SelectableDynamicTool"`.
    *   **Test Flow**: Invoke the `SelectableDynamicTool` and verify its output. Also assert that the tools from the provider and the standalone function in the same module were *not* loaded.

5.  **Create `test_explicit_provider_loading.yaml`**:
    *   **Harness**: Use `dynamic_agent_harness`.
    *   **Agent Config**: `tool_type: python`, `component_module: tests.integration.test_support.dynamic_tools.hybrid_tools`, `class_name: "SelectableToolProvider"`.
    *   **Test Flow**: Invoke the tools generated by the provider and verify their outputs.
