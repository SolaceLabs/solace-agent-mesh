# Proposal: Artifact Scoping Refactor

**Date:** 2025-08-13
**Status:** Approved

## 1. Goals

-   **Centralize Logic:** Ensure all artifact scoping logic resides in a single, well-defined location.
-   **Consistent Behavior:** Guarantee that all interactions with the artifact storage layer correctly respect the configured scope (`namespace` or `app`).
-   **Improve Maintainability:** Make the artifact storage layer easier to understand, test, and modify in the future.
-   **Minimize Impact:** Reduce the amount of code that needs to be refactored in components that *use* the artifact service.

## 2. Problem Statement

The system requires that artifacts can be scoped either to a specific application (`app`) or shared across a `namespace`. The initial implementation placed this scoping logic in helper functions within `artifact_helpers.py`.

However, a code audit revealed that several parts of the codebase bypass these helpers and interact with the `artifact_service` object directly. This creates two major problems:

1.  **Inconsistent Scoping:** Direct calls do not apply the `namespace` scope, leading to bugs where artifacts are stored in or retrieved from the wrong location.
2.  **Fragile Configuration:** The helper-based approach relied on a global, module-level variable to hold the scope configuration, which is not a robust pattern and complicates testing.

## 3. Proposed Solutions & Decision

### Option 1: Helper Functions (Rejected)

This approach involved creating a new helper function in `artifact_helpers.py` for every method on the `BaseArtifactService` interface (e.g., `helpers.delete_artifact`, `helpers.list_versions`).

-   **Pros:** Conceptually simple.
-   **Cons:** Would require refactoring every call site from `service.method(...)` to `helpers.method(service, ...)`, which is invasive and error-prone. It would also perpetuate the use of a fragile global state for configuration.

### Option 2: Wrapper Class (Decorator/Proxy Pattern) (Accepted)

This approach involves creating a `ScopedArtifactServiceWrapper` class that implements the `BaseArtifactService` interface and contains the actual service instance.

-   **Pros:**
    -   **True Encapsulation:** The scoping logic is part of the service object itself.
    -   **No Global State:** The wrapper holds the scope configuration as instance variables, making it clean and easy to test.
    -   **Transparent to Callers:** The wrapper is a drop-in replacement for the real service. No changes are needed at the call sites (`service.method(...)` works as-is).
-   **Cons:** Requires slightly more setup in the factory function that creates the service.

### Decision

**Option 2, the Wrapper Class, was chosen.** It is a more robust, maintainable, and object-oriented solution that aligns with best practices for software design. It solves the core problem with minimal disruption to the rest of the codebase.

## 4. Requirements

-   The solution must be transparent to any code that currently uses an `artifact_service` object.
-   The solution must eliminate the need for a global, module-level state for artifact scoping.
-   All calls to the artifact service must correctly apply the configured `namespace` or `app` scope.
-   The solution must be type-safe and fully compatible with the `BaseArtifactService` interface.
