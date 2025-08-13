# Detailed Design: Scoped Artifact Service Wrapper

**Date:** 2025-08-13
**Status:** Approved

## 1. Overview

This document provides the detailed technical design for the `ScopedArtifactServiceWrapper`. This component will act as a proxy to the concrete artifact service instance, transparently applying the correct storage scope (`namespace` or `app`) to all operations. This approach centralizes scoping logic and eliminates the need for global state.

## 2. Component Breakdown

### 2.1. `ScopedArtifactServiceWrapper` Class

This new class will be the cornerstone of the solution.

-   **Location:** `src/solace_agent_mesh/agent/adk/services.py`
-   **Inheritance:** `class ScopedArtifactServiceWrapper(BaseArtifactService):`
-   **Initialization:**
    -   The constructor will accept the concrete service instance and the scope configuration:
        ```python
        def __init__(self, wrapped_service: BaseArtifactService, scope_type: str, scope_value: str):
            self.wrapped_service = wrapped_service
            self.scope_type = scope_type
            self.scope_value = scope_value
        ```
-   **Scoping Logic:**
    -   A private method will determine the effective `app_name` for any operation.
        ```python
        def _get_scoped_app_name(self, app_name: str) -> str:
            if self.scope_type == "namespace":
                return self.scope_value
            return app_name
        ```
-   **Implemented Methods:**
    -   The wrapper will implement all abstract methods from `BaseArtifactService`: `save_artifact`, `load_artifact`, `list_versions`, `list_artifact_keys`, and `delete_artifact`.
    -   Each implementation will first resolve the `scoped_app_name` and then delegate the call to the `self.wrapped_service` instance.
    -   Example implementation for `save_artifact`:
        ```python
        @override
        async def save_artifact(self, *, app_name: str, ...) -> int:
            scoped_app_name = self._get_scoped_app_name(app_name)
            return await self.wrapped_service.save_artifact(
                app_name=scoped_app_name,
                ... # all other arguments passed through
            )
        ```

### 2.2. `initialize_artifact_service` Factory Function

The existing factory will be updated to construct and return the wrapper.

-   **Location:** `src/solace_agent_mesh/agent/adk/services.py`
-   **Updated Logic:**
    1.  The function will instantiate the concrete service (`InMemoryArtifactService`, `GcsArtifactService`, etc.) based on the component's YAML configuration, as it does today.
    2.  It will read the `artifact_scope` setting from the configuration.
    3.  It will determine the `scope_value` (which is the component's `namespace`).
    4.  It will instantiate `ScopedArtifactServiceWrapper`, passing the concrete service instance and the scope configuration.
    5.  It will **return the wrapper instance**, not the concrete service.

## 3. Code Cleanup Plan

With the wrapper in place, the previous global state-based implementation becomes obsolete and will be removed.

1.  **`src/solace_agent_mesh/agent/utils/artifact_helpers.py`:**
    -   **Remove:** The `_scope_config` global variable, `_scope_config_lock`, `configure_artifact_scoping` function, `reset_artifact_scoping_for_testing` function, and `_get_scoped_app_name` function.
    -   **Update:** Any helper functions that were using `_get_scoped_app_name` will now simply pass the `app_name` they receive to the service method, as the service object itself is now the scope-aware wrapper.

2.  **`src/solace_agent_mesh/agent/sac/component.py` & `src/solace_agent_mesh/gateway/base/component.py`:**
    -   **Remove:** The call to `configure_artifact_scoping()` from the `__init__` method in both components.

3.  **`tests/integration/conftest.py`:**
    -   **Remove:** The `reset_artifact_scoping_fixture` and its usage, as it is no longer necessary.

## 4. Benefits of this Design

-   **Centralized & Encapsulated:** All scoping logic is contained within the wrapper class.
-   **No Global State:** Eliminates fragile module-level state, improving reliability and testability.
-   **Transparent:** Consumers of the `artifact_service` do not need to be aware of the wrapping.
-   **Maintainable:** Future changes to scoping logic only need to be made in one place.
