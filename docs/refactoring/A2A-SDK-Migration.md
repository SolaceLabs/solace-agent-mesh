# Refactoring: A2A Protocol Alignment and SDK Adoption

## 1. Overview

This document outlines a strategic refactoring initiative to align the Solace Agent Mesh (SAM) platform with the latest official Agent-to-Agent (A2A) protocol specification. The core of this effort involves migrating from our custom, legacy A2A type definitions and client/server implementations to the official `a2a-sdk` for Python.

This is a foundational architectural improvement that will reduce technical debt, improve maintainability, and ensure SAM remains compliant and interoperable within the broader A2A ecosystem. The refactoring will impact the full stack, from the agent backend and gateways to the test infrastructure and the web UI frontend.

## 2. Goals

The primary objectives of this refactoring are:

*   **Protocol Compliance:** Fully align with the current A2A JSON specification, ensuring our agents and gateways are interoperable with other A2A-compliant systems.
*   **SDK Adoption:** Replace our bespoke A2A client, server, and type implementations with the official `a2a-sdk`. This will insulate the project from future specification changes and leverage the community-supported standard.
*   **Improved Maintainability:** Eliminate the technical debt associated with maintaining a custom implementation of a public standard. This will simplify future development and onboarding.
*   **Standardized Status Communication:** Refactor the transmission of non-visible status updates (e.g., tool invocations, LLM calls) away from custom `metadata` fields and into the standardized `DataPart` structure, as recommended by the A2A specification. This will create a more robust and parsable data stream for clients.
*   **Future-Proofing:** Position the SAM platform to easily adopt new features and capabilities as the A2A protocol evolves.

## 3. Requirements (Definition of Done)

This refactoring will be considered complete when the following requirements are met:

1.  **Type System Migration:** All internal usages of the legacy A2A types defined in `src/solace_agent_mesh/common/types.py` have been replaced with the corresponding types from the `a2a.types` module of the `a2a-sdk`.
2.  **Component Compliance:** All backend components, including agents (`SamAgentComponent`) and gateways (`BaseGatewayComponent` and its derivatives), use the `a2a.types` models for serializing and deserializing A2A messages sent over the Solace message bus.
3.  **Standardized Status Updates:** All non-visible status messages (e.g., tool start, LLM invocation, progress updates) are transmitted using `DataPart` objects within the A2A `Message` structure, not via custom `metadata` fields.
4.  **Legacy Code Removal:** The custom-built A2A modules are deprecated and removed from the codebase, specifically:
    *   `src/solace_agent_mesh/common/types.py`
    *   `src/solace_agent_mesh/common/client/`
    *   `src/solace_agent_mesh/common/server/`
5.  **Test Suite Validation:** The entire integration test suite passes, with tests updated to use the new `a2a-sdk` client and validate against the new A2A message formats.
6.  **Frontend Compatibility:** The Web UI frontend is successfully updated to parse, process, and correctly render the new A2A message and event structures, including the new `DataPart`-based status updates.

## 4. Scope

### In Scope

*   Modifying all backend Python code that creates, processes, or validates A2A messages. This includes agents, gateways, and core protocol handlers.
*   Updating the entire test infrastructure, including fixtures and the `A2AMessageValidator`, to align with the new protocol.
*   Refactoring the Web UI's data layer and components to consume and render the new A2A message format from the gateway's SSE stream.
*   Adding the `a2a-sdk` as a new project dependency.

### Out of Scope

*   Changing the core business logic of the agent's tools.
*   Changing the underlying transport mechanism (the system will continue to use Solace as the message bus). The `a2a-sdk` will be used for its data models and object structures, not its built-in HTTP transport.
*   Major redesigns of the Web UI's appearance or user experience, beyond what is necessary to support the new data format.
*   Implementing new features that are not directly related to achieving protocol compliance.

## 5. High-Level Approach

We will adopt a phased, iterative approach to manage risk and complexity. The strategy is to first refactor and validate a complete end-to-end vertical slice of the system in a controlled test environment before rolling out the changes to production-facing components and the UI.

*   **Phase 0: Preparation & Tooling**
    *   Integrate the `a2a-sdk` library into the project's dependencies.
    *   Update the `A2AMessageValidator` test utility to use the official `a2a.json` schema as its source of truth. This will be a critical tool for debugging throughout the refactoring.
    *   Create a high-level mapping of legacy types to the new `a2a.types` to guide the migration.

*   **Phase 1: Backend Refactoring & Validation**
    *   Focus exclusively on the agent backend and the test infrastructure.
    *   The `TestGatewayComponent` will be the first "client" to be refactored. It will be modified to construct and send requests using the new `a2a.types` models.
    *   The `SamAgentComponent` and its associated handlers (`event_handlers.py`, `callbacks.py`) will be refactored to parse the new request format and, crucially, to generate responses and status updates using the new `DataPart` standard.
    *   The integration test suite will be updated to drive this process. The goal of this phase is to make the existing tests pass with the fully refactored backend and test gateway, proving the new implementation is correct before touching any user-facing code.

*   **Phase 2: Gateway & Frontend Migration**
    *   With a validated backend, apply the now-proven refactoring patterns to the other gateway implementations (`http_sse`, `slack`, etc.).
    *   Once the `http_sse` gateway is emitting the new A2A message format, begin the frontend migration. This will involve updating the frontend's type definitions, data parsing logic in the React contexts, and UI components to correctly render the new event stream.

*   **Phase 3: Cleanup**
    *   After all components have been migrated and the full system is validated, the final step is to remove the now-obsolete legacy A2A modules from the codebase.
