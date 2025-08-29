# Refactoring Proposal: `SamComponentBase`

## 1. Goals

The primary goals of this refactoring effort are to:

-   **Reduce Code Duplication:** Eliminate redundant code between the `SamAgentComponent` and `BaseGatewayComponent`, particularly for message publishing and asynchronous task management.
-   **Improve Maintainability:** Centralize shared logic in one place, making future updates easier and less error-prone.
-   **Standardize Component Behavior:** Ensure that core functionalities, such as message publishing with size validation and async lifecycle management, are handled consistently across all high-level components.
-   **Establish a Foundation:** Create a solid architectural base (`SamComponentBase`) for any future shared component logic, such as standardized health checks, metrics, or configuration handling.

## 2. Requirements

To achieve these goals, the refactoring must address the following requirements:

-   **Shared Publishing Logic:** A single, shared method for publishing A2A messages must be created.
-   **Message Size Validation:** The shared publishing method must include message size validation, configurable per component.
-   **Async Lifecycle Management:** The common logic for creating, managing, and cleaning up the dedicated `asyncio` event loop and its thread must be centralized.
-   **Consistent Configuration Access:** Components should have a standardized way to access common configuration parameters (e.g., `namespace`).
-   **SAC Integration:** The solution must inherit from and integrate correctly with the existing `solace_ai_connector.components.component_base.ComponentBase`.

## 3. Decisions

Based on the analysis of the requirements, the following decisions have been made:

-   **Introduce a Shared Base Class:** A new abstract base class named `SamComponentBase` will be created to house all shared logic. This approach is favored over standalone utility functions for its stronger encapsulation and architectural clarity.
-   **Update Inheritance:** `SamAgentComponent` and `BaseGatewayComponent` will be modified to inherit from the new `SamComponentBase` instead of directly from `ComponentBase`.
-   **File Location:** The new base class will be located in a new file at the following path: `src/solace_agent_mesh/common/sac/sam_component_base.py`.
-   **Centralize Publishing:** The `publish_a2a_message` method, including size validation and logging, will be implemented in `SamComponentBase`.
-   **Centralize Async Management:** The methods and properties related to managing the `asyncio` event loop and its dedicated thread (`_run_async_operations`, `_start_async_loop`, `_async_loop`, `_async_thread`, etc.) will be moved into `SamComponentBase`.
