# Implementation Checklist: Centralized Artifact Scoping

This checklist provides a terse summary of the tasks required to implement the centralized artifact scoping feature.

### Phase 1: Core Logic Implementation

-   [X] **1. Implement Centralized Scoping in `artifact_helpers.py`**
    -   [X] Add module-level state: `_scope_config`, `_scope_config_lock`.
    -   [X] Define `ArtifactScopingError` exception.
    -   [X] Implement `configure_artifact_scoping()` with conflict detection.
    -   [X] Implement `reset_artifact_scoping_for_testing()`.
    -   [X] Implement `_get_scoped_app_name()` helper.

-   [ ] **2. Integrate Scoping Logic into `artifact_helpers.py` Functions**
    -   [ ] Modify `save_artifact_with_metadata` to use `_get_scoped_app_name`.
    -   [ ] Modify `load_artifact_content_or_metadata` to use `_get_scoped_app_name`.
    -   [ ] Modify `get_latest_artifact_version` to use `_get_scoped_app_name`.
    -   [ ] Modify `get_artifact_info_list` to use `_get_scoped_app_name`.
    -   [ ] Modify `generate_artifact_metadata_summary` to use `_get_scoped_app_name`.

### Phase 2: Refactor Existing Services and Components

-   [ ] **3. Refactor `FilesystemArtifactService`**
    -   [ ] Remove `scope_identifier` from `__init__`.
    -   [ ] Rewrite `_get_artifact_dir` to use the `app_name` parameter for path construction.

-   [ ] **4. Update `initialize_artifact_service` Factory**
    -   [ ] Remove `scope_identifier` calculation logic.
    -   [ ] Update `FilesystemArtifactService` instantiation to only pass `base_path`.

-   [ ] **5. Update `SamAgentComponent` to Configure Scoping**
    -   [ ] Add a call to `artifact_helpers.configure_artifact_scoping` in the `__init__` method.

-   [ ] **6. Update `BaseGatewayComponent` to Configure Scoping**
    -   [ ] Add a call to `artifact_helpers.configure_artifact_scoping` in the `__init__` method.

### Phase 3: Update Test Infrastructure

-   [ ] **7. Implement Test Isolation Fixture**
    -   [ ] Add an `autouse` pytest fixture in `tests/integration/conftest.py` to call `reset_artifact_scoping_for_testing` after each test.

-   [ ] **8. Update Declarative Test Runner**
    -   [ ] Modify `_setup_scenario_environment` to use `artifact_scope` for setting up artifacts.
    -   [ ] Modify `_assert_generated_artifacts` to use `artifact_scope` for lookups.
    -   [ ] Modify `_assert_summary_in_text` to use `artifact_scope` for lookups.
    -   [ ] Modify `_assert_llm_interactions` to use `artifact_scope` for lookups.

### Phase 4: Documentation and Cleanup

-   [ ] **9. Update Configuration Schema Documentation**
    -   [ ] In `SamAgentApp`, update the description for `artifact_scope` to reflect its new global behavior.

-   [ ] **10. Update Existing Test Scenarios**
    -   [ ] Review declarative test YAML files and add `test_runner_config_overrides` for `artifact_scope` where necessary to test both `app` and `namespace` scopes.
