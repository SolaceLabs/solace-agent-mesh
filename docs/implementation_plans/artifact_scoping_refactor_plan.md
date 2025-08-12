# Implementation Plan: Centralized Artifact Scoping

**Date:** 2025-08-12

This document outlines the step-by-step plan to implement the centralized artifact scoping feature as described in the corresponding design document.

---

### Phase 1: Core Logic Implementation

1.  **Implement Centralized Scoping in `artifact_helpers.py`**:
    *   In `src/solace_agent_mesh/agent/utils/artifact_helpers.py`, add the module-level `_scope_config` dictionary and `_scope_config_lock`.
    *   Define the `ArtifactScopingError` exception class.
    *   Implement the `configure_artifact_scoping(scope_type, namespace_value, component_name)` function, including logic for thread-safe initialization and conflict detection.
    *   Implement the `reset_artifact_scoping_for_testing()` function to clear the module-level state.
    *   Implement the internal `_get_scoped_app_name(app_name)` helper function to resolve the effective `app_name` based on the stored configuration.

2.  **Integrate Scoping Logic into `artifact_helpers.py` Functions**:
    *   Modify the following functions in `src/solace_agent_mesh/agent/utils/artifact_helpers.py` to use `_get_scoped_app_name` to determine the `app_name` before calling the artifact service:
        *   `save_artifact_with_metadata`
        *   `load_artifact_content_or_metadata`
        *   `get_latest_artifact_version`
        *   `get_artifact_info_list`
        *   `generate_artifact_metadata_summary`

### Phase 2: Refactor Existing Services and Components

3.  **Refactor `FilesystemArtifactService`**:
    *   In `src/solace_agent_mesh/agent/adk/filesystem_artifact_service.py`:
        *   Update the `__init__` method to remove the `scope_identifier` parameter and its associated logic.
        *   Rewrite the `_get_artifact_dir` method to construct its path using the `app_name` parameter it receives, following the pattern: `{base_path}/{app_name}/{user_id}/{session_id_or_user_namespace}/{filename}`.

4.  **Update `initialize_artifact_service` Factory**:
    *   In `src/solace_agent_mesh/agent/adk/services.py`:
        *   Modify the `initialize_artifact_service` function. For the `filesystem` type, remove the logic that calculates `scope_identifier` and simply instantiate `FilesystemArtifactService` with the `base_path`.

5.  **Update `SamAgentComponent` to Configure Scoping**:
    *   In `src/solace_agent_mesh/agent/sac/component.py`:
        *   Within the `__init__` method, after `initialize_artifact_service` is called, add a call to `artifact_helpers.configure_artifact_scoping`.
        *   Pass the `artifact_scope` from the component's configuration and the `namespace` value.

6.  **Update `BaseGatewayComponent` to Configure Scoping**:
    *   In `src/solace_agent_mesh/gateway/base/component.py`:
        *   Add a similar call to `artifact_helpers.configure_artifact_scoping` in the `__init__` method to ensure gateways also participate in the process-wide configuration.

### Phase 3: Update Test Infrastructure

7.  **Implement Test Isolation Fixture**:
    *   In `tests/integration/conftest.py`, create a new `autouse=True`, function-scoped `pytest` fixture.
    *   This fixture will call `artifact_helpers.reset_artifact_scoping_for_testing()` in its teardown phase (`yield`).

8.  **Update Declarative Test Runner**:
    *   In `tests/integration/scenarios_declarative/test_declarative_runner.py`:
        *   Modify `_setup_scenario_environment` to determine the `app_name` for artifact creation based on the `artifact_scope` in `test_runner_config_overrides`.
        *   Modify `_assert_generated_artifacts` to use the correct `app_name` for artifact lookups based on the test's `artifact_scope`.
        *   Modify `_assert_summary_in_text` to use the correct `app_name` for metadata lookups based on the test's `artifact_scope`.
        *   Modify `_assert_llm_interactions` to correctly determine the `app_name` for artifact summary assertions in prompts.

### Phase 4: Documentation and Cleanup

9.  **Update Configuration Schema Documentation**:
    *   In `src/solace_agent_mesh/agent/sac/app.py`, update the description for the `artifact_scope` parameter in `app_schema` to clarify that it is a global setting affecting all artifact services, not just the filesystem one.

10. **Update Existing Test Scenarios**:
    *   Review and update any declarative test YAML files in `tests/integration/scenarios_declarative/test_data/` that rely on the old `FilesystemArtifactService` behavior. Specifically, tests involving multiple agents and shared artifacts will need to be checked to ensure they correctly use the `namespace` scope via `test_runner_config_overrides`. Add `test_runner_config_overrides` where needed to test both `app` and `namespace` scopes.
