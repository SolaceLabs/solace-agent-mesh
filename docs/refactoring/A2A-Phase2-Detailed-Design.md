# Detailed Design: Phase 2 - Web UI & Gateway Migration

## 1. Introduction

This document provides the detailed technical design for the A2A Phase 2 refactoring. It expands on the high-level proposal by specifying the required changes to the `http_sse` gateway and the Web UI frontend. The goal is to achieve full compliance with the A2A specification for the entire web-based user interaction flow.

This design adheres to the architectural decisions outlined in the proposal: the gateway will not use the `a2a-sdk` server, the frontend will not use the `a2a-js` client, and the SDKs will be used as data modeling libraries.

---

## 2. Backend Design: `http_sse` Gateway Refactoring

### 2.1. Gateway API Refactoring (REST Compliance)

The gateway's task-related HTTP endpoints will be refactored to align with the A2A REST transport specification.

**Endpoint Mapping:**

| Operation | Legacy Endpoint | New A2A-Compliant Endpoint | HTTP Method |
| :--- | :--- | :--- | :--- |
| Submit Streaming Task | `POST /api/v1/tasks/subscribe` | `POST /api/v1/message:stream` | `POST` |
| Submit Non-Streaming Task | `POST /api/v1/tasks/send` | `POST /api/v1/message:send` | `POST` |
| Cancel Task | `POST /api/v1/tasks/cancel` | `POST /api/v1/tasks/{taskId}:cancel` | `POST` |

**Implementation Changes (`tasks.py`):**

1.  **URL Routing:** The `@router.post()` decorators in `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py` will be updated to the new URL paths.
2.  **Request Body:** The request body format will change from `multipart/form-data` to `application/json`. The API handlers will now expect a Pydantic model that validates against the official `a2a.types` request objects (e.g., `SendMessageRequest`, `CancelTaskRequest`).
3.  **File Uploads:** The existing file upload mechanism will be preserved. The frontend will continue to upload files to the dedicated artifact endpoint (`/api/v1/artifacts`). The gateway's `_translate_external_input` method will be responsible for creating the `artifact://` URI and placing it in the `FilePart` of the `SendMessageRequest` payload.

### 2.2. A2A Event Processing (`component.py`)

The gateway's core logic for handling messages from the Solace bus will be updated to use the new SDK types.

1.  **Event Parsing (`BaseGatewayComponent`):**
    *   The `_handle_agent_event` method will be modified to parse incoming JSON payloads into `a2a.types.JSONRPCResponse` objects.
    *   The `_parse_a2a_event_from_rpc_result` helper method will be updated to use the `kind` field as a discriminator to parse the `result` into specific `a2a.types` models like `Task`, `TaskStatusUpdateEvent`, or `TaskArtifactUpdateEvent`.

2.  **SSE Forwarding (`WebUIBackendComponent`):**
    *   The `_send_update_to_external` and `_send_final_response_to_external` methods will now receive `a2a.types` Pydantic objects as arguments.
    *   These methods must be updated to correctly serialize the objects to JSON (`.model_dump(by_alias=True, exclude_none=True)`) before sending them over the SSE stream to the Web UI.

---

## 3. Frontend Design: Web UI Refactoring

### 3.1. Dependency and Type System Migration

1.  **Add Dependency:** The `@a2a-js/sdk` package will be added as a `devDependency` to the `package.json` file to provide official TypeScript types.
2.  **Refactor `be.ts`:** The file `client/webui/frontend/src/lib/types/be.ts` will be refactored. All legacy, manually-defined interfaces (`Task`, `Message`, `Part`, etc.) will be removed and replaced with type exports from `@a2a-js/sdk`.
3.  **Extend `Message` Type:** A new `MessageFE` (Frontend) interface will be created that `extends` the official `Message` type from the SDK. This will allow us to add UI-specific state (e.g., `isStatusBubble`, `isComplete`) while maintaining type compatibility with the core protocol.

### 3.2. API and SSE Consumer Refactoring

1.  **API Calls (`ChatProvider.tsx`):**
    *   The `handleSubmit` and `handleCancel` functions will be updated to call the new A2A-compliant REST endpoints on the gateway.
    *   The request body will be changed from `FormData` to a JSON object conforming to the `SendMessageRequest` or `CancelTaskRequest` type from the SDK.

2.  **SSE Parsing (`ChatProvider.tsx`):**
    *   The `handleSseMessage` function will be rewritten to parse incoming SSE data as a `JSONRPCResponse` from the `@a2a-js/sdk`.
    *   The core logic will iterate through the `parts` array of the `Message` object found within a `TaskStatusUpdateEvent`.
    *   A `switch` statement on `part.kind` will be used:
        *   `case 'data'`: The logic will inspect `part.data.type` to identify and process status signals (e.g., `tool_invocation_start`). This replaces the old `metadata` parsing logic.
        *   `case 'text'`: The logic will append the text content to the current message bubble.
        *   `case 'file'`: The logic will handle file attachments.

### 3.3. Component Rendering Updates

1.  **`VisualizerStepCard.tsx`:** This component will be updated to receive props that conform to the new SDK types. Its rendering logic will be changed to access data from the structured `part.data` object (e.g., `step.data.toolInvocationStart.tool_name`) instead of a flat `metadata` object.
2.  **`MessageBubble.tsx`:** This component will be updated to correctly render the new `DataPart` signals, displaying tool calls and other status updates in a structured format within the chat history.

---

## 4. DataPart Schema Contract

To ensure a clear contract between the backend and frontend, all status signals communicated via `DataPart` objects will adhere to the official JSON schemas defined in `src/solace_agent_mesh/common/a2a_spec/schemas/`.

The frontend will implement parsers for the following key signals:

| Signal Type (`data.type`) | Schema File | Purpose |
| :--- | :--- | :--- |
| `tool_invocation_start` | `tool_invocation_start.json` | Indicates that an agent is about to execute a tool. |
| `llm_invocation` | `llm_invocation.json` | Indicates that an agent is making a call to an LLM. |
| `agent_progress_update` | `agent_progress_update.json` | Provides a generic, human-readable status update from the agent. |
| `artifact_creation_progress` | `artifact_creation_progress.json` | Signals progress during the creation of a large artifact. |

This explicit contract will guide the implementation on both sides, ensuring robust and predictable status communication.
