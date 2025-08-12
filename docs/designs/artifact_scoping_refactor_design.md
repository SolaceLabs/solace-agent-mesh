# Design: Centralized Artifact Scoping

**Date:** 2025-08-12

## 1. Introduction

This document provides the detailed technical design for centralizing the artifact scoping logic. It outlines the specific changes to modules, classes, and functions required to implement the solution described in the corresponding proposal document.

## 2. Detailed Design

The implementation will be broken down into several key areas: introducing a centralized configuration mechanism, updating helper functions to use it, modifying components to provide the configuration, refactoring the `FilesystemArtifactService` to remove its custom logic, and ensuring test isolation.

### 2.1. Centralized Scoping in `artifact_helpers.py`

The `src/solace_agent_mesh/agent/utils/artifact_helpers.py` module will become the single source of truth for artifact scoping logic.

#### 2.1.1. Module-Level State

The following module-level variables will be added to manage the process-wide configuration:

-   `_scope_config: Optional[Dict[str, Any]] = None`: A dictionary to store the validated configuration. It will have keys like `scope_type` and `namespace_value`. It is initialized to `None`.
-   `_scope_config_lock = threading.Lock()`: A lock to ensure thread-safe initialization and prevent race conditions when multiple components initialize concurrently.

A new exception class will be defined for clear error handling:

-   `class ArtifactScopingError(Exception): pass`: A custom exception to be raised on configuration conflicts.

#### 2.1.2. Configuration Function

A new public function will be added to configure the scoping at startup:

-   `configure_artifact_scoping(scope_type: str, namespace_value: str, component_name: str) -> None`:
    -   This function will be called by components (`SamAgentComponent`, `BaseGatewayComponent`) during their initialization.
    -   It will acquire `_scope_config_lock`.
    -   **First-time call:** If `_scope_config` is `None`, it will populate it with the provided `scope_type` and `namespace_value`.
    -   **Subsequent calls:** If `_scope_config` is already set, it will compare the existing `scope_type` and `namespace_value` with the new ones.
    -   **Conflict Detection:** If the new configuration conflicts with the existing one, it will raise an `ArtifactScopingError` with a descriptive message indicating which component (`component_name`) attempted to set a conflicting value.
    -   This enforces the "one scope configuration per process" rule.

#### 2.1.3. Test Reset Function

To ensure test isolation, a function will be added to reset the state:

-   `reset_artifact_scoping_for_testing() -> None`:
    -   This function will acquire the lock and reset `_scope_config` to `None`.
    -   It will be called by a `pytest` fixture after each test run.

#### 2.1.4. Internal Scoped Name Resolver

A private helper function will be added to resolve the effective `app_name` for any artifact operation:

-   `_get_scoped_app_name(app_name: str) -> str`:
    -   This function reads the `_scope_config`.
    -   If `scope_type` is `"namespace"`, it returns the stored `namespace_value`, ignoring the passed `app_name`.
    -   If `scope_type` is `"app"`, it returns the passed `app_name` unmodified.
    -   If `_scope_config` is not set, it will default to returning the passed `app_name` to maintain behavior in contexts where the configuration might not be available (though this should be rare).

### 2.2. Updates to `artifact_helpers.py` Functions

All public functions in `artifact_helpers.py` that interact with the `BaseArtifactService` will be modified to use the new scoping logic.

-   **Affected Functions:**
    -   `save_artifact_with_metadata`
    -   `load_artifact_content_or_metadata`
    -   `get_latest_artifact_version`
    -   `get_artifact_info_list`
    -   `generate_artifact_metadata_summary`

-   **Change:**
    -   Inside each function, before calling a method on the `artifact_service` instance (e.g., `artifact_service.save_artifact(...)`), the `app_name` parameter will be passed through the `_get_scoped_app_name` helper.
    -   `scoped_app_name = _get_scoped_app_name(app_name)`
    -   The `scoped_app_name` will then be used in the call to the artifact service, ensuring the correct scope is used regardless of the underlying service implementation.

### 2.3. Component Initialization

#### 2.3.1. `SamAgentComponent`

The `__init__` method of `src/solace_agent_mesh/agent/sac/component.py::SamAgentComponent` will be updated:

1.  It will read the `artifact_service` dictionary from its configuration.
2.  It will determine the `scope_type` from `artifact_scope` (defaulting to `"namespace"`).
3.  It will determine the `namespace_value` from the top-level `namespace` configuration key.
4.  It will call `artifact_helpers.configure_artifact_scoping` with these values and its own `agent_name` for logging purposes.

#### 2.3.2. `BaseGatewayComponent`

The `__init__` method of `src/solace_agent_mesh/gateway/base/component.py::BaseGatewayComponent` will be updated similarly to `SamAgentComponent` to ensure gateways also configure the artifact scope correctly.

### 2.4. `FilesystemArtifactService` Refactoring

The `src/solace_agent_mesh/agent/adk/filesystem_artifact_service.py::FilesystemArtifactService` will be simplified to remove its custom scoping logic.

1.  **`__init__` Method:**
    -   The `scope_identifier` parameter will be removed. The constructor will only accept `base_path`.
    -   The `self.scope_identifier` and `self.scope_base_path` attributes will be removed. `self.base_path` will be the root for all artifacts.

2.  **`_get_artifact_dir` Method:**
    -   This method will be rewritten to use the `app_name` parameter it receives (which is now correctly scoped by `artifact_helpers`).
    -   The new directory structure will be: `{base_path}/{app_name}/{user_id}/{session_id_or_user_namespace}/{filename}`.
    -   This makes its behavior consistent with how `GcsArtifactService` and `InMemoryArtifactService` implicitly structure their data.

### 2.5. Service Factory Update

The `initialize_artifact_service` function in `src/solace_agent_mesh/agent/adk/services.py` will be updated.

-   When `type` is `filesystem`, it will no longer calculate a `scope_identifier` based on `artifact_scope` and `namespace`.
-   It will simply instantiate `FilesystemArtifactService` with the `base_path` from the configuration.

### 2.6. Test Infrastructure

1.  **Isolation Fixture:**
    -   A new `autouse=True` function-scoped fixture will be added to `tests/integration/conftest.py`.
    -   This fixture will have a `yield` and, in its teardown phase, will call `artifact_helpers.reset_artifact_scoping_for_testing()` to ensure each test runs with a clean slate.

2.  **Declarative Test Runner (`test_declarative_runner.py`):**
    -   The `_setup_scenario_environment` helper function will be updated. When setting up initial artifacts (`setup_artifacts`), it will determine the `app_name` to use based on the `artifact_scope` defined in the test's `test_runner_config_overrides`. If the scope is `namespace`, it will use the hardcoded `"test_namespace"`; otherwise, it will use the agent's name.
    -   The `_assert_generated_artifacts` and `_assert_summary_in_text` helpers will be similarly updated to use the correct `app_name` for artifact lookups based on the test's configured scope.
