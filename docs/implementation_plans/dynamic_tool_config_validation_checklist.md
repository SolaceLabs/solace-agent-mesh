# Implementation Checklist: Pydantic-Based Dynamic Tool Configuration

This checklist outlines the development tasks required to implement Pydantic-based configuration validation for dynamic tools, as detailed in the implementation plan.

## Phase 1: Core Framework Changes

1.  **Modify `src/solace_agent_mesh/agent/tools/dynamic_tool.py`:**
    - [x] 1.1. Import `BaseModel` from `pydantic` and `Type` from `typing`.
    - [x] 1.2. In the `DynamicTool` class, add the class attribute `config_model: Optional[Type[BaseModel]] = None`.
    - [x] 1.3. Update the `DynamicTool.__init__` method's type hint for `tool_config` to `Optional[Union[dict, BaseModel]]`.
    - [x] 1.4. In the `DynamicToolProvider` class, add the class attribute `config_model: Optional[Type[BaseModel]] = None`.
    - [x] 1.5. Update the `DynamicToolProvider.get_all_tools_for_framework` method signature to accept `tool_config: Optional[Union[dict, BaseModel]] = None`.
    - [x] 1.6. Update the `DynamicToolProvider.create_tools` method signature to accept `tool_config: Optional[Union[dict, BaseModel]] = None`.

2.  **Modify `src/solace_agent_mesh/agent/adk/setup.py`:**
    - [ ] 2.1. Import `BaseModel` and `ValidationError` from `pydantic`.
    - [ ] 2.2. In `load_adk_tools`, locate the logic block for `tool_type: "python"` where `DynamicTool` and `DynamicToolProvider` classes are handled.
    - [ ] 2.3. After the `tool_class` is determined, add logic to get the `config_model` using `getattr(tool_class, "config_model", None)`.
    - [ ] 2.4. If a `config_model` is found, validate the `specific_tool_config` dictionary against it using `config_model.model_validate(specific_tool_config)`.
    - [ ] 2.5. Wrap the validation logic in a `try...except ValidationError` block. On failure, log a clear error message and raise a `ValueError`.
    - [ ] 2.6. Store the result of the validation (either the new Pydantic model instance or the original dictionary) in a `validated_config` variable.
    - [ ] 2.7. Update the `DynamicToolProvider` instantiation logic to pass `tool_config=validated_config` to the `get_all_tools_for_framework` method.
    - [ ] 2.8. Update the `DynamicTool` instantiation logic to pass `tool_config=validated_config` to the class constructor.

## Phase 2: Documentation

3.  **Update `docs/docs/documentation/user-guide/creating-python-tools.md`:**
    - [ ] 3.1. Add a new section (e.g., "Pattern 4: Pydantic-Based Configuration") to introduce the feature.
    - [ ] 3.2. Explain the key benefits: automatic validation at startup, type safety in tool code, and self-documenting configuration.
    - [ ] 3.3. Provide a complete, copy-paste-friendly code example that includes:
        - A Pydantic `BaseModel` defining the configuration.
        - A `DynamicTool` or `DynamicToolProvider` subclass that links the model via the `config_model` attribute.
        - The tool's `__init__` or `create_tools` method demonstrating type-safe access to the configuration object.
    - [ ] 3.4. Show the corresponding valid YAML `tool_config` block.
    - [ ] 3.5. Clearly explain that the agent will fail to start with a precise error message if the YAML configuration does not match the Pydantic model.

## Phase 3: Finalization

4.  **Cleanup:**
    - [ ] 4.1. Delete `docs/implementation_plans/dynamic_tool_config_validation.md`.
    - [ ] 4.2. Delete `docs/implementation_plans/dynamic_tool_config_validation_checklist.md`.
