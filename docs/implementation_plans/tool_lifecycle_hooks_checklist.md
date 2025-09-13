# Implementation Checklist: Tool Lifecycle Hooks

1.  **Define Configuration Models** (`src/solace_agent_mesh/agent/tools/tool_config_types.py`) - DONE
    1.  Create `ToolLifecycleHookConfig` Pydantic model.
    2.  Add `init_function: Optional[ToolLifecycleHookConfig]` to `BaseToolConfig`.
    3.  Add `cleanup_function: Optional[ToolLifecycleHookConfig]` to `BaseToolConfig`.

2.  **Extend Dynamic Tool Interface** (`src/solace_agent_mesh/agent/tools/dynamic_tool.py`) - DONE
    1.  Add `async def init(self, component, tool_config)` method to `DynamicTool` with a `pass` implementation.
    2.  Add `async def cleanup(self, component, tool_config)` method to `DynamicTool` with a `pass` implementation.

3.  **Implement Initialization and Cleanup Collection** (`src/solace_agent_mesh/agent/adk/setup.py`) - DONE
    1.  Update `load_adk_tools` return signature to include a list of cleanup hooks: `Tuple[List, List, List[Callable]]`.
    2.  Inside `load_adk_tools`, for each tool, implement the initialization logic:
        -   Execute the YAML-configured `init_function` if it exists.
        -   Execute the `tool.init()` method if the tool is a `DynamicTool`.
    3.  Inside `load_adk_tools`, for each tool, collect cleanup hooks in LIFO order:
        -   Add the `tool.cleanup()` method (for `DynamicTool` instances).
        -   Add the YAML-configured `cleanup_function`.
    4.  Return the collected list of cleanup hooks.

4.  **Manage and Execute Cleanup Hooks** (`src/solace_agent_mesh/agent/sac/component.py`) - DONE
    1.  In `SamAgentComponent.__init__`, add `self._tool_cleanup_hooks: List[Callable] = []`.
    2.  In `_perform_async_init`, capture the cleanup hooks from `load_adk_tools` and store them in `self._tool_cleanup_hooks`.
    3.  In the `cleanup` method, schedule and execute all functions in `self._tool_cleanup_hooks` on the component's event loop, logging any errors.
