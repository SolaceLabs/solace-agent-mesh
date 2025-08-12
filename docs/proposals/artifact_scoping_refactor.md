# Proposal: Centralized Artifact Scoping

**Date:** 2025-08-12

## 1. Problem Statement

The current implementation of artifact storage scoping is inconsistent and misplaced. The `artifact_scope` configuration (`app` vs. `namespace`) is only implemented by the `FilesystemArtifactService`, which contains custom logic to handle it. Other services, like `InMemoryArtifactService` and `GcsArtifactService`, do not respect this setting, leading to divergent behavior depending on the configured service.

This approach is architecturally unsound because the responsibility for determining the storage scope should lie with the calling context (the application logic), not within a specific storage implementation. A full refactor to pass the scope configuration down through the entire call stack is infeasible due to the high impact on existing tools and external plugins that we must maintain backward compatibility with.

## 2. Goals

The primary goals of this refactor are to:

1.  **Ensure Consistent Behavior:** All artifact service implementations (`Filesystem`, `GCS`, `InMemory`) must behave identically with respect to the configured storage scope.
2.  **Centralize Scoping Logic:** Move the responsibility for determining the artifact scope from a specific service implementation to a higher, shared layer of the application.
3.  **Simplify Artifact Services:** Remove custom scoping logic from `FilesystemArtifactService`, making it and all other services simpler and strictly compliant with the `BaseArtifactService` interface.
4.  **Maintain Backward Compatibility:** The change must not require any modifications to existing tools or external plugins that interact with the artifact service.

## 3. Requirements

The solution must meet the following requirements:

1.  **Support Two Scopes:** The system must continue to support two artifact scopes:
    *   `app`: Artifacts are isolated to the specific agent instance.
    *   `namespace`: Artifacts are shared across all agents and components within the same A2A namespace.
2.  **Process-Wide Configuration:** The artifact scope setting must be applied consistently across a single Python process.
3.  **Conflict Detection:** The system must detect if multiple components within the same process are configured with conflicting artifact scopes. If a conflict is found, the application must fail at startup with a clear error message.
4.  **No Tool-Level Changes:** Existing tools that use artifact helper functions must not require any code changes to adopt the new scoping behavior.

## 4. Decisions

To meet the goals and requirements under the existing constraints, the following high-level decisions have been made:

1.  **Scoping Logic in `artifact_helpers`:** The logic for interpreting the `artifact_scope` configuration will be centralized within the `src/solace_agent_mesh/agent/utils/artifact_helpers.py` module. This module is the common entry point for most artifact operations.
2.  **Module-Level State:** A module-level variable will be used in `artifact_helpers` to store the process-wide artifact scope configuration. This avoids a large-scale refactor while still centralizing the logic.
3.  **Startup Configuration and Validation:** Each agent/gateway component will be responsible for registering its artifact scope configuration with the `artifact_helpers` module during initialization. The registration function will enforce the "one scope per process" rule.
4.  **Service-Agnostic `app_name`:** The `app_name` parameter passed to the `BaseArtifactService` methods will now represent the *effective scope identifier*. The `artifact_helpers` module will resolve this to either the component's specific name (for `app` scope) or the shared namespace name (for `namespace` scope).
5.  **Refactor `FilesystemArtifactService`:** The `FilesystemArtifactService` will be refactored to remove its internal `scope_identifier` logic. It will be simplified to use the `app_name` it receives directly for constructing its directory paths, making it consistent with other service implementations.
