# Implementation Checklist: Artifact Scoping Refactor

This checklist outlines the steps to implement the `ScopedArtifactServiceWrapper` and refactor the codebase to use it, centralizing artifact scoping logic.

### Phase 1: Implement the Wrapper and Factory

1.  **Create `ScopedArtifactServiceWrapper` Class**
    -   [x] In `src/solace_agent_mesh/agent/adk/services.py`, define the new wrapper class.
    -   [x] Inherit from `google.adk.artifacts.BaseArtifactService`.
    -   [x] Implement `__init__` to accept and store the wrapped service instance, `scope_type`, and `scope_value`.
    -   [x] Implement a private `_get_scoped_app_name` method to resolve the `app_name` based on the scope.
    -   [x] Implement all abstract methods (`save_artifact`, `load_artifact`, `list_versions`, `list_artifact_keys`, `delete_artifact`) to call the corresponding method on the wrapped service with the scoped `app_name`.

2.  **Update `initialize_artifact_service` Factory**
    -   [x] In `src/solace_agent_mesh/agent/adk/services.py`, modify the factory function.
    -   [x] After creating the concrete service instance (e.g., `InMemoryArtifactService`), determine the `scope_type` and `scope_value` from the component's configuration.
    -   [x] Instantiate `ScopedArtifactServiceWrapper`, passing it the concrete service and scope configuration.
    -   [x] Return the wrapper instance instead of the concrete service.

### Phase 2: Refactor and Clean Up

3.  **Remove Global Scoping from `artifact_helpers.py`**
    -   [x] In `src/solace_agent_mesh/agent/utils/artifact_helpers.py`, delete the `_scope_config` global variable and its associated lock (`_scope_config_lock`).
    -   [x] Delete the `configure_artifact_scoping`, `reset_artifact_scoping_for_testing`, and `_get_scoped_app_name` functions.
    -   [x] Update any helper functions that used `_get_scoped_app_name` to simply pass the `app_name` through to the service methods.

4.  **Remove Scoping Configuration Calls from Components**
    -   [x] In `src/solace_agent_mesh/agent/sac/component.py`, remove the call to `configure_artifact_scoping()` from the `__init__` method.
    -   [x] In `src/solace_agent_mesh/gateway/base/component.py`, remove the call to `configure_artifact_scoping()` from the `__init__` method.

5.  **Update Test Infrastructure**
    -   [ ] In `tests/integration/conftest.py`, delete the `reset_artifact_scoping_fixture` fixture entirely.
    -   [ ] In `tests/integration/scenarios_declarative/test_declarative_runner.py`, remove any remaining calls or dependencies on `configure_artifact_scoping`.
    -   [ ] Verify that declarative tests that specify `artifact_scope` in their config overrides continue to function correctly.
