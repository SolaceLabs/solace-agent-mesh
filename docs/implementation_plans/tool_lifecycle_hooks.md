# Implementation Plan: Tool Lifecycle Hooks

This document outlines the plan to implement initialization and cleanup lifecycle hooks for tools within the Solace Agent Mesh framework.

## 1. Feature Overview

This feature introduces `init` and `cleanup` lifecycle hooks for all tool types. These hooks will allow tools to manage resources (e.g., database connections, file handles, network sockets) reliably.

-   **Initialization**: Executed once per tool during agent startup.
-   **Cleanup**: Executed once per tool during agent shutdown.

Hooks can be defined in two ways:
1.  **YAML Configuration**: An `init_function` and `cleanup_function` can be specified in the agent's YAML configuration for any tool.
2.  **DynamicTool Methods**: Subclasses of `DynamicTool` can implement `init()` and `cleanup()` methods directly.

## 2. Detailed Implementation Plan

### Step 1: Update Configuration Models

**File**: `src/solace_agent_mesh/agent/tools/tool_config_types.py`

-   Define a new Pydantic model `ToolLifecycleHookConfig` to represent a configurable lifecycle function (`module`, `name`, `config`, etc.).
-   Add two optional fields, `init_function: Optional[ToolLifecycleHookConfig]` and `cleanup_function: Optional[ToolLifecycleHookConfig]`, to the `BaseToolConfig` model. This makes the hooks available to all tool types (`builtin`, `python`, `mcp`, etc.).

### Step 2: Extend the Dynamic Tool Interface

**File**: `src/solace_agent_mesh/agent/tools/dynamic_tool.py`

-   Add two new `async` methods to the `DynamicTool` abstract base class:
    -   `async def init(self, component: "SamAgentComponent", tool_config: "AnyToolConfig") -> None:`
    -   `async def cleanup(self, component: "SamAgentComponent", tool_config: "AnyToolConfig") -> None:`
-   Provide default `pass` implementations for these methods so that subclasses are not required to implement them.

### Step 3: Implement Initialization Logic

**File**: `src/solace_agent_mesh/agent/adk/setup.py`

-   Modify the `load_adk_tools` function to handle the new lifecycle hooks.
-   The function's return signature will be changed from `Tuple[List, List]` to `Tuple[List, List, List[Callable]]` to include a list of awaitable cleanup functions.
-   Inside the tool loading loop, for each tool:
    1.  **YAML Init**: If `tool_config.init_function` is defined, dynamically import and `await` its execution. The function will be called with the `SamAgentComponent` instance and the tool's full Pydantic configuration object.
    2.  **Dynamic Tool Init**: If the loaded tool is an instance of `DynamicTool`, `await` its `tool.init()` method, passing the same arguments.
    3.  **Collect Cleanup Hooks**:
        -   If the tool is a `DynamicTool`, create a `functools.partial` for its `cleanup()` method, binding the required arguments.
        -   If `tool_config.cleanup_function` is defined, create a `functools.partial` for it.
        -   Add these partials to a list that will be returned by `load_adk_tools`. The order will be `[tool.cleanup, yaml_cleanup]` to ensure LIFO execution.

### Step 4: Implement Cleanup Logic

**File**: `src/solace_agent_mesh/agent/sac/component.py`

-   In the `SamAgentComponent.__init__` method, add a new instance variable: `self._tool_cleanup_hooks: List[Callable] = []`.
-   In the `_perform_async_init` method, update the call to `load_adk_tools` to receive the list of cleanup hooks and store it in `self._tool_cleanup_hooks`.
-   In the `cleanup` method, before the `super().cleanup()` call:
    -   Schedule the execution of all awaitable functions in `self._tool_cleanup_hooks` on the component's dedicated asyncio event loop.
    -   Use `asyncio.gather` with `return_exceptions=True` to ensure all cleanup hooks are attempted, even if some fail.
    -   Log any exceptions that occur during cleanup but do not stop the shutdown process.

## 3. Design Decisions

### Execution Order (LIFO)

-   **Initialization**:
    1.  YAML `init_function`
    2.  `DynamicTool.init()` method
-   **Cleanup**:
    1.  `DynamicTool.cleanup()` method
    2.  YAML `cleanup_function`

### Function Signatures

All lifecycle hooks, whether from YAML or a `DynamicTool` method, will receive the same two arguments:
1.  `component: SamAgentComponent`: The hosting component instance.
2.  `tool_config: AnyToolConfig`: The full Pydantic model for the specific tool's configuration.

### Error Handling

-   **Initialization Failure**: Any exception raised during any `init` hook will be considered a fatal error, preventing the agent from starting.
-   **Cleanup Failure**: Any exception raised during a `cleanup` hook will be logged as an error, but the shutdown sequence will continue to allow other hooks to run.

### Asynchronous Hooks

All lifecycle hooks will be defined as `async def` to support non-blocking I/O operations.
