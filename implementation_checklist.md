# Dynamic Tools Implementation Checklist

1.  ~~Create the new file `src/solace_agent_mesh/agent/tools/dynamic_tool.py`.~~
2.  ~~In `dynamic_tool.py`, define the `DynamicTool` abstract base class.~~
3.  ~~In `dynamic_tool.py`, define the internal `_FunctionAsDynamicTool` adapter class, including a helper to generate an ADK schema from a function signature.~~
4.  ~~In `dynamic_tool.py`, define the `DynamicToolProvider` abstract base class, including the `@register_tool` decorator and the `_create_tools_from_decorators` helper method.~~
5.  Update `src/solace_agent_mesh/agent/tools/__init__.py` to import the new `dynamic_tool` module.
6.  In `src/solace_agent_mesh/agent/adk/setup.py`, add imports for `DynamicTool` and `DynamicToolProvider`.
7.  In `src/solace_agent_mesh/agent/adk/setup.py`, add the `_find_dynamic_tool_class` helper function.
8.  In `src/solace_agent_mesh/agent/adk/setup.py`, add the `_find_dynamic_tool_provider_class` helper function.
9.  In `src/solace_agent_mesh/agent/adk/setup.py`, add the `elif tool_type == "dynamic":` block inside the `load_adk_tools` function.
10. In the new `elif` block, implement the loading logic that first checks for a `DynamicToolProvider` and falls back to a single `DynamicTool`.
11. In the new `elif` block, add the final loop to process all generated tools, validate their declarations, and add them to the `loaded_tools` list.
