# Implementation Test Plan: Pydantic-Based Dynamic Tool Configuration

This document outlines the testing and validation steps required to successfully implement and release the Pydantic-based configuration feature for dynamic tools.

## 1. Core Logic & Unit Testing

- [ ] 1. **Base Class Modifications:**
    - [ ] 1.1. Verify that `DynamicTool` has a new class attribute `config_model: Optional[Type[BaseModel]] = None`.
    - [ ] 1.2. Verify that `DynamicToolProvider` has a new class attribute `config_model: Optional[Type[BaseModel]] = None`.
    - [ ] 1.3. Update type hints in `DynamicTool.__init__` and `DynamicToolProvider` methods to `Optional[Union[dict, BaseModel]]`.

- [ ] 2. **Tool Loading Logic (`load_adk_tools`):**
    - [ ] 2.1. **Success Case (DynamicTool):** Create a unit test where a `DynamicTool` subclass defines a `config_model`. Provide a valid `tool_config` dictionary. Assert that the tool is instantiated with a Pydantic model instance, not a dict.
    - [ ] 2.2. **Failure Case (DynamicTool):** Create a unit test for the same tool but provide an invalid `tool_config` (e.g., missing a required field, wrong type). Assert that `load_adk_tools` raises a `ValueError` and that the error message contains the Pydantic `ValidationError` details.
    - [ ] 2.3. **Backward Compatibility (DynamicTool):** Create a unit test for a `DynamicTool` subclass that does *not* define a `config_model`. Assert that it is instantiated with a raw dictionary as before.
    - [ ] 2.4. **Success Case (DynamicToolProvider):** Create a unit test where a `DynamicToolProvider` subclass defines a `config_model`. Provide a valid `tool_config`. Assert that the `create_tools` method is called with a Pydantic model instance.
    - [ ] 2.5. **Failure Case (DynamicToolProvider):** Create a unit test for the provider with an invalid `tool_config`. Assert that `load_adk_tools` raises a `ValueError`.
    - [ ] 2.6. **Backward Compatibility (DynamicToolProvider):** Create a unit test for a provider that does *not* define a `config_model`. Assert that `create_tools` is called with a raw dictionary.

## 2. Integration Testing

- [ ] 3. **Create a Test Tool with Pydantic Config:**
    - [ ] 3.1. In the integration test suite, create a new dynamic tool file (e.g., `tests/integration/tools/pydantic_tool.py`).
    - [ ] 3.2. Define a `ConfigModel(BaseModel)` with at least one required field and one optional field.
    - [ ] 3.3. Define a `PydanticDynamicTool(DynamicTool)` that sets `config_model = ConfigModel`.
    - [ ] 3.4. The tool's `_run_async_impl` should assert that `self.tool_config` is an instance of `ConfigModel` and return a value from the config to verify access.

- [ ] 4. **Create Test Agent Configurations:**
    - [ ] 4.1. Create a valid agent YAML configuration that uses the `PydanticDynamicTool` and provides a correct `tool_config`.
    - [ ] 4.2. Create an invalid agent YAML configuration that uses the tool but provides an incorrect `tool_config` (e.g., missing the required field).

- [ ] 5. **Write Integration Tests:**
    - [ ] 5.1. **Success Test:** Write an integration test that starts an agent with the *valid* YAML. The test should invoke the tool and assert that it returns the expected value from its configuration, proving the Pydantic model was passed and used correctly.
    - [ ] 5.2. **Failure Test:** Write an integration test that attempts to start an agent with the *invalid* YAML. Assert that the agent startup fails with a `ValueError` and that the exception message clearly indicates a Pydantic validation error.
    - [ ] 5.3. **Regression Test:** Ensure all existing integration tests still pass to confirm no regressions were introduced.

## 3. Documentation

- [ ] 6. **Update User Guide:**
    - [ ] 6.1. Edit `docs/docs/documentation/user-guide/creating-python-tools.md`.
    - [ ] 6.2. Add a new section or update the `DynamicTool` and `DynamicToolProvider` sections to describe the new Pydantic-based configuration pattern.
    - [ ] 6.3. Include a complete, clear code example showing how to define a `BaseModel`, link it via `config_model`, and use the typed config object within the tool.
    - [ ] 6.4. Explain the benefits of this approach (automatic validation, type safety, self-documentation).
    - [ ] 6.5. Review the entire document to ensure the flow is logical and all patterns are presented clearly.

## 4. Manual Verification & QA

- [ ] 7. **Run Existing Examples:**
    - [ ] 7.1. Manually run the `orchestrator_example.yaml` agent to ensure it starts and operates correctly without any changes.

- [ ] 8. **Test New Feature Manually:**
    - [ ] 8.1. Create a new example agent YAML that uses a test tool with the Pydantic model feature.
    - [ ] 8.2. Run the agent with a valid `tool_config` and confirm it starts.
    - [ ] 8.3. Modify the YAML to have an invalid `tool_config` (e.g., comment out a required field).
    - [ ] 8.4. Run the agent again and verify that it fails to start and prints a clear, user-friendly error message pointing to the configuration issue.

- [ ] 9. **Final Review:**
    - [ ] 9.1. Review the updated documentation on the documentation server to ensure it renders correctly and is easy to understand.
    - [ ] 9.2. Review all code changes for clarity, comments, and adherence to project standards.
    - [ ] 9.3. Delete the implementation plan and test plan documents before merging the final PR.
