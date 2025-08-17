# Refactoring Proposal: Phase 2 - Web UI & Gateway Migration

## 1. Overview

This document outlines the refactoring initiative for Phase 2 of the A2A protocol alignment project, with a specific focus on the Web UI and its supporting `http_sse` gateway. This phase builds upon the successful backend refactoring completed in Phase 1.

The core of this effort is to make the Web UI and its gateway fully compliant with the official A2A specification, both in its data structures and its API interactions. This involves migrating from our legacy A2A types to the official `a2a-sdk` (Python) and `@a2a-js/sdk` (TypeScript) libraries, and aligning our gateway's API with the A2A REST transport specification.

## 2. Goals

The primary objectives of this refactoring are:

*   **Full-Stack Protocol Compliance:** Achieve end-to-end A2A compliance for the Web UI flow, from the gateway's HTTP API to the data structures rendered in the browser.
*   **SDK Adoption:** Replace all legacy A2A type definitions in the gateway and frontend code with the official SDK models (`a2a.types` and `@a2a-js/sdk` types).
*   **Standardized API:** Refactor the `http_sse` gateway's custom API endpoints for task management to align with the A2A REST transport specification.
*   **Standardized Status Communication:** Migrate the communication of non-visible status updates (e.g., tool invocations, LLM calls) from custom `metadata` fields to the standardized `DataPart` structure, creating a robust and parsable data stream for the UI.
*   **Improve Maintainability:** Eliminate the technical debt associated with maintaining custom A2A types and API structures, simplifying future development.

## 3. Requirements (Definition of Done)

This refactoring phase will be considered complete when the following requirements are met:

1.  **Gateway API Compliance:** The `http_sse` gateway's task-related endpoints (`send`, `subscribe`, `cancel`) have been refactored to match the A2A REST transport specification for URLs and request/response bodies.
2.  **Backend Type Migration:** The `http_sse` gateway and `BaseGatewayComponent` use the `a2a.types` models for creating A2A requests and parsing A2A responses from the message bus.
3.  **Frontend Type Migration:** The Web UI's TypeScript types (`be.ts`) have been replaced with imports from the `@a2a-js/sdk`, and all related application code (contexts, components) has been updated to use these new types.
4.  **Standardized Status Handling:** The Web UI (`ChatProvider`, `TaskMonitorContext`) correctly parses `DataPart` objects from the SSE stream to display status updates, and no longer relies on custom `metadata` fields for this purpose.
5.  **End-to-End Validation:** The refactored Web UI and gateway are fully integrated and tested. A user can successfully initiate a multi-step, tool-using task from the UI, see real-time status updates, and receive a final response, with all data flowing through the new compliant structures.

## 4. Key Architectural Decisions

The following key decisions have been made to guide the implementation of this phase:

1.  **Gateway Will Not Use the `a2a-sdk` Server:** The `http_sse` gateway will **not** be replaced with the `a2a-sdk`'s built-in server. Our gateway acts as a bridge and a Backend-for-Frontend (BFF) with many custom endpoints, a role for which the SDK's server is not designed. We will continue to use our existing FastAPI server.
2.  **Frontend Will Not Use the `a2a-js` Client:** The Web UI will **not** use the `a2a-js` client for networking. The gateway's custom API (e.g., using `multipart/form-data` and a two-step SSE connection process) is incompatible with the standard A2A client's expectations. We will continue to use our existing `authenticatedFetch` and `EventSource` logic.
3.  **SDKs Will Be Used for Data Modeling:** The `a2a-sdk` (Python) and `@a2a-js/sdk` (TypeScript) will be used primarily as **data modeling and validation libraries**. Their Pydantic and TypeScript types will serve as the source of truth for all A2A data structures throughout the stack, ensuring compliance at the data-interchange level.

This approach allows us to achieve full protocol compliance while retaining control over our custom server architecture and minimizing unnecessary refactoring of the networking layers.
