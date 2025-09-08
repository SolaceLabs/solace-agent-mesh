# Implementation Plan for Dynamic Tools

This document outlines the step-by-step plan to implement the dynamic tools feature as described in `dynamic_tools_design_document.md`. The implementation will cover the `DynamicTool` base class, the `DynamicToolProvider` factory pattern, and the `@register_tool` decorator for function-based tools.

### Step 1: Create the Core `dynamic_tool.py` Module

This is a new file that will contain the primary classes for the dynamic tools feature.

-   **File Path**: `src/solace_agent_mesh/agent/tools/dynamic_tool.py`
-   **Contents**:
    1.  **`DynamicTool` ABC**: Define the `DynamicTool` abstract base class inheriting from `google.adk.tools.BaseTool`. It will have abstract properties for `tool_name`, `tool_description`, and `parameters_schema`, and concrete implementations for `__init__` and `_get_declaration`, plus an abstract `_run_async_impl` method.
    2.  **`_FunctionAsDynamicTool` Adapter Class**: Create an internal (private) adapter class that inherits from `DynamicTool`. This class will wrap a standard Python function and implement the `DynamicTool` interface via introspection of the function's signature and docstring. This is the key to making the decorator work. It will need a helper function, `_get_schema_from_signature`, to convert Python type hints to an ADK `Schema`. The logic for this can be adapted from the existing `ADKToolWrapper`.
    3.  **`DynamicToolProvider` ABC**: Define the `DynamicToolProvider` abstract base class. It will contain:
        -   The `@classmethod` decorator `register_tool`.
        -   The helper method `_create_tools_from_decorators`, which uses the `_FunctionAsDynamicTool` adapter.
        -   The abstract method `create_tools`.

### Step 2: Update `tools/__init__.py` for Package Cohesion

To ensure the new `dynamic_tool` module is part of the `tools` package and its classes are easily accessible, we will add an import statement.

-   **File Path**: `src/solace_agent_mesh/agent/tools/__init__.py`
-   **Change**: Add `from . import dynamic_tool` to the list of imports.

### Step 3: Enhance `setup.py` to Load Dynamic Tools

This is the most significant modification to existing code. The `load_adk_tools` function will be updated to recognize and process the `dynamic` tool type.

-   **File Path**: `src/solace_agent_mesh/agent/adk/setup.py`
-   **Changes**:
    1.  **Add Imports**: Import `DynamicTool` and `DynamicToolProvider` from `...agent.tools.dynamic_tool`.
    2.  **Create Helper Functions**:
        -   Define `_find_dynamic_tool_class(module) -> Optional[Type[DynamicTool]]`: This helper will inspect a module and return the first class it finds that is a subclass of `DynamicTool`. It will raise an error if more than one is found without a `class_name` being specified in the config.
        -   Define `_find_dynamic_tool_provider_class(module) -> Optional[Type[DynamicToolProvider]]`: This helper will do the same for `DynamicToolProvider`.
    3.  **Add New `elif` Block**: In `load_adk_tools`, add a new `elif tool_type == "dynamic":` block.
    4.  **Implement Loading Logic**: Inside the new block, implement the logic described in the design document:
        -   Import the specified `component_module`.
        -   First, try to find and use a `DynamicToolProvider` subclass. If found, instantiate it, call `create_tools()`, and collect the returned list of tool instances.
        -   If no provider is found, fall back to looking for a single `DynamicTool` subclass (either by `class_name` or by auto-discovery) and create a list containing that single instance.
        -   If neither is found, raise a `TypeError`.
    5.  **Process Generated Tools**: After getting the list of `dynamic_tools`, iterate through it. For each tool instance:
        -   Set its `origin` property to `"dynamic"`.
        -   Call `_get_declaration()` to generate its function declaration.
        -   Perform a name collision check using the existing `_check_and_register_tool_name` helper.
        -   Append the tool instance to the main `loaded_tools` list.
        -   Log the successful loading of the tool.

### Step 4: No Changes Required for Other Files

-   **`src/solace_agent_mesh/agent/tools/registry.py`**: The `tool_registry` is for `BuiltinTool` definitions, which are used to generate prompt instructions. Dynamic tools generate their own `FunctionDeclaration` at runtime, so they do not need to be registered here. The name collision check happens within `setup.py`'s local scope, which is correct.
-   **`src/solace_agent_mesh/agent/tools/tool_definition.py`**: This file defines the `BuiltinTool` model. Since dynamic tools are a parallel concept and have their own base class, no changes are needed here.
