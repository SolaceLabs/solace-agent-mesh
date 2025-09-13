# Pydantic Configuration Migration Checklist

### Phase 1: Create Core Compatibility and Type Definition Files

1.  [x] Create the new file `src/solace_agent_mesh/agent/utils/pydantic_compat.py` to define the `BackwardCompatibleModel` class, which will provide dictionary-like access methods (`.get()`, `[]`, `in`) for Pydantic objects.

2.  [x] Create the new file `src/solace_agent_mesh/agent/tools/tool_config_types.py` to define all Pydantic models related to agent tool configurations (`BuiltinToolConfig`, `PythonToolConfig`, etc.) using a discriminated union. These models will inherit from `BackwardCompatibleModel`.

### Phase 2: Refactor Application Configuration Schemas

3.  [x] Refactor `src/solace_agent_mesh/agent/sac/app.py`:
    -   Define a new `SamAgentAppConfig(BackwardCompatibleModel)` class that fully models the existing `app_schema` dictionary, preserving all field descriptions using `pydantic.Field`.
    -   In the `SamAgentApp.__init__` method, add logic to validate the incoming `app_config` dictionary against the `SamAgentAppConfig` model.
    -   Replace the raw dictionary in `app_info["app_config"]` with the validated, backward-compatible Pydantic object.
    -   Remove the now-redundant `app_schema` dictionary.

4.  [x] Refactor `src/solace_agent_mesh/gateway/base/app.py`:
    -   Define a new `BaseGatewayAppConfig(BackwardCompatibleModel)` class to model the fields from `BASE_GATEWAY_APP_SCHEMA`. This will serve as a base for concrete gateway configurations.
    -   Remove the now-redundant `BASE_GATEWAY_APP_SCHEMA` dictionary.

5.  Refactor `src/solace_agent_mesh/gateway/http_sse/app.py`:
    -   Define a new `WebUIBackendAppConfig(BaseGatewayAppConfig)` class that inherits from the base gateway model and adds fields from `SPECIFIC_APP_SCHEMA_PARAMS`.
    -   In the `WebUIBackendApp.__init__` method, add logic to validate the `app_config` against the new `WebUIBackendAppConfig` model.

6.  Refactor `tests/sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/app.py`:
    -   Define a new `TestGatewayAppConfig(BaseGatewayAppConfig)` class.
    -   In the `TestGatewayApp.__init__` method, add logic to validate the `app_config` against the new `TestGatewayAppConfig` model.

### Phase 3: Verification

7.  Verify that no code changes are required in `src/solace_agent_mesh/agent/adk/setup.py` and `src/solace_agent_mesh/agent/sac/component.py`. The backward-compatible model should ensure that existing calls to `.get("key")` and `self.get_config("key")` continue to work seamlessly.

8.  Run all existing unit and integration tests to confirm that the refactoring has not introduced any breaking changes.

9.  Confirm that example configurations, such as `orchestrator_example.yaml`, load and run correctly.
