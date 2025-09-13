# Pydantic Configuration Migration Plan

## 1. Goal

The primary goal of this refactoring is to migrate the application configuration from a custom, dictionary-based schema (`app_schema`) to a robust, type-safe system using Pydantic models.

This will achieve:
-   **Strong Validation:** Automatically validate the entire `app_config` structure, including the complex `tools` list, catching errors early.
-   **Improved Developer Experience:** Provide IDE autocompletion and type-checking for configuration objects.
-   **Self-Documentation:** Pydantic models with `Field` descriptions serve as a single source of truth for configuration parameters.
-   **Maintainability:** Simplify the process of adding or modifying configuration options.

A critical requirement is to achieve this with **full backward compatibility**, ensuring that existing code which accesses configuration via dictionary methods (e.g., `config.get("key")`) continues to function without modification.

## 2. Core Strategy

The migration will be executed using the following strategy to ensure safety and compatibility:

1.  **Introduce a Backward-Compatible Base Model:** A new class, `BackwardCompatibleModel`, will be created. It will inherit from `pydantic.BaseModel` and implement dictionary-style access methods (`.get()`, `__getitem__`, `__contains__`). All new configuration models will inherit from this class.

2.  **Define Pydantic Models for Schemas:** For each `app.py` file, we will create a corresponding Pydantic model that mirrors its `app_schema` dictionary. Field descriptions will be preserved using `pydantic.Field(description=...)`.

3.  **Validate on Initialization:** In the `__init__` method of each `App` class, the raw `app_config` dictionary will be validated against its corresponding Pydantic model.

4.  **Replace with Validated Object:** After successful validation, the raw `app_config` dictionary in the main `app_info` object will be replaced with the newly created Pydantic model instance.

5.  **Seamless Integration:** Because the Pydantic object is backward-compatible, all downstream components (like `SamAgentComponent`) that access the configuration through methods like `self.get_config()` will continue to work without any changes.

## 3. Key New Files

Two new files will be created to support this migration.

### 3.1. `src/solace_agent_mesh/agent/utils/pydantic_compat.py`

-   **Purpose:** To house the `BackwardCompatibleModel` class. This centralizes the compatibility logic.

### 3.2. `src/solace_agent_mesh/agent/tools/tool_config_types.py`

-   **Purpose:** To define the Pydantic models for the `tools` configuration array. This will include a `BaseToolConfig` and specific models for each `tool_type` (`builtin`, `python`, `mcp`, etc.), combined into a discriminated union (`AnyToolConfig`).

## 4. Refactoring Plan for Existing Files

The following `app.py` files, which currently define a configuration schema, will be refactored.

### 4.1. `src/solace_agent_mesh/agent/sac/app.py` (Agent Host)

-   **Action:** Define a new `SamAgentAppConfig(BackwardCompatibleModel)` class within this file. This model will be a complete Pydantic representation of the `app_schema`, including the `tools: List[AnyToolConfig]` field.
-   **Logic:** In `SamAgentApp.__init__`, use `SamAgentAppConfig.model_validate()` to parse the `app_config` dictionary. Replace the dictionary in `app_info["app_config"]` with the validated Pydantic object.
-   **Outcome:** The agent configuration will be fully validated on startup. The existing `app_schema` dictionary can be removed or kept for documentation purposes.

### 4.2. `src/solace_agent_mesh/gateway/base/app.py` (Base Gateway)

-   **Action:** Define a `BaseGatewayAppConfig(BackwardCompatibleModel)` class for the fields in `BASE_GATEWAY_APP_SCHEMA`.
-   **Logic:** The validation logic will not be placed here. Instead, this base model will be inherited by the configuration models of concrete gateway implementations (`WebUIBackendApp`, `TestGatewayApp`). The `BaseGatewayApp.__init__` method will continue to work as-is because it will receive an `app_info` dictionary containing a backward-compatible object.

### 4.3. `src/solace_agent_mesh/gateway/http_sse/app.py` (Web UI Gateway)

-   **Action:** Define a `WebUIBackendAppConfig(BaseGatewayAppConfig)` class that inherits from the base gateway config model and adds the fields from `SPECIFIC_APP_SCHEMA_PARAMS`.
-   **Logic:** In `WebUIBackendApp.__init__`, validate the `app_config` dictionary against the complete `WebUIBackendAppConfig` model.
-   **Outcome:** The Web UI gateway configuration will be fully validated.

### 4.4. `tests/sam-test-infrastructure/src/sam_test_infrastructure/gateway_interface/app.py` (Test Gateway)

-   **Action:** Define a `TestGatewayAppConfig(BaseGatewayAppConfig)` class.
-   **Logic:** In `TestGatewayApp.__init__`, validate the `app_config` dictionary against the `TestGatewayAppConfig` model.
-   **Outcome:** The test gateway's configuration will be validated, ensuring test infrastructure remains aligned with the main application.

## 5. Verification

-   All existing unit and integration tests must pass without modification.
-   The `orchestrator_example.yaml` and other example configurations should load and run successfully.
-   (Optional) A new test can be added to specifically verify that an invalid tool configuration (e.g., a `python` tool missing `component_module`) correctly raises a `pydantic.ValidationError` on startup.
