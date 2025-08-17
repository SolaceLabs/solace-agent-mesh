# Implementation Plan: Phase 2 - Web UI & Gateway Migration

## 1. Introduction

This document provides a detailed, step-by-step implementation plan for the A2A Phase 2 refactoring. It is the technical companion to the high-level proposal and detailed design documents. The plan is divided into three main parts: backend gateway refactoring, frontend UI refactoring, and end-to-end validation.

Each step is designed to be a discrete unit of work, allowing for incremental progress and validation.

---

## Part 1: Backend Gateway Refactoring

**Objective:** Modify the `http_sse` gateway to align its public API and internal message handling with the A2A specification and the `a2a-sdk` types.

### Step 1: Update Gateway API Endpoints (`tasks.py`)

1.1. **Modify URL Routes:** In `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`, update the FastAPI `@router.post` decorators to match the A2A REST specification:
    -   Change `/send` to `/message:send`.
    -   Change `/subscribe` to `/message:stream`.
    -   Change `/cancel` to `/tasks/{taskId}:cancel`.

1.2. **Update `cancel_agent_task` Handler:**
    -   Modify the function signature to accept `taskId: str` from the URL path.
    -   Change the `payload` parameter from the legacy `CancelTaskApiPayload` to the official `a2a.types.CancelTaskRequest`.

1.3. **Update `send_task_to_agent` and `subscribe_task_from_agent` Handlers:**
    -   Remove the `Form` dependencies (`agent_name`, `message`, `files`).
    -   Change the request body to expect a single `application/json` payload that validates against `a2a.types.SendMessageRequest`.
    -   The logic for handling file uploads will now be driven by `artifact://` URIs present in the `FilePart` of the request, which are created by the frontend via the existing `/api/v1/artifacts` endpoint.

### Step 2: Update Gateway A2A Event Parsing (`component.py`)

2.1. **Refactor `_handle_agent_event` in `BaseGatewayComponent`:**
    -   Modify the `rpc_response` validation to parse the incoming payload into an `a2a.types.JSONRPCResponse` object.
    -   Update the logic that retrieves the `result` to handle the new `RootModel` structure of the SDK's response type.

2.2. **Refactor `_parse_a2a_event_from_rpc_result` in `BaseGatewayComponent`:**
    -   Rewrite the parsing logic to use the `kind` field as the primary discriminator for the `rpc_result` dictionary.
    -   Use `TaskStatusUpdateEvent.model_validate(rpc_result)`, `TaskArtifactUpdateEvent.model_validate(rpc_result)`, and `Task.model_validate(rpc_result)` to parse the data into the correct Pydantic models.
    -   Update the task ID extraction logic to use the `taskId` field from `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` (instead of the old `id` field).

### Step 3: Update Gateway SSE Forwarding (`component.py`)

3.1. **Update Method Signatures in `WebUIBackendComponent`:**
    -   The `_send_update_to_external` method's `event_data` parameter will now be typed as `Union[a2a.types.TaskStatusUpdateEvent, a2a.types.TaskArtifactUpdateEvent]`.
    -   The `_send_final_response_to_external` method's `task_data` parameter will now be typed as `a2a.types.Task`.
    -   The `_send_error_to_external` method's `error_data` parameter will now be typed as `a2a.types.JSONRPCError`.

3.2. **Update Serialization Logic:**
    -   In all three methods listed above, replace any manual dictionary creation with the Pydantic `model_dump(by_alias=True, exclude_none=True)` method on the received `a2a.types` objects to ensure correct JSON serialization before sending the data to the SSE manager.

---

## Part 2: Frontend Web UI Refactoring

**Objective:** Refactor the Web UI to use the official `@a2a-js/sdk` types, consume the new gateway API, and correctly process the new `DataPart`-based status signals.

### Step 4: Migrate Frontend Type System

4.1. **Add SDK Dependency:** Add `@a2a-js/sdk` as a `devDependency` to the `package.json` file.

4.2. **Refactor `be.ts`:**
    -   Delete all legacy A2A-related interfaces (`JSONRPCResponse`, `Message`, `Part`, `Task`, `TaskStatusUpdateEvent`, etc.) from `client/webui/frontend/src/lib/types/be.ts`.
    -   Replace them with direct type exports from the SDK: `export type { Message, Task, Part, DataPart, TaskStatusUpdateEvent, ... } from "@a2a-js/sdk";`.

4.3. **Create `MessageFE` Type:**
    -   In `be.ts` or a new UI-specific types file, define a new interface `MessageFE` that extends the official `Message` from the SDK, adding UI-specific fields like `isStatusBubble`, `isComplete`, and `uploadedFiles`.

### Step 5: Refactor API Calls and SSE Parsing (`ChatProvider.tsx`)

5.1. **Update `handleSubmit`:**
    -   Change the `fetch` call's URL from `/api/v1/tasks/subscribe` to `/api/v1/message:stream`.
    -   Modify the request `body` to be a JSON string created from a `SendMessageRequest` object, conforming to the new SDK type. The `Content-Type` header must be set to `application/json`.

5.2. **Update `handleCancel`:**
    -   Change the `fetch` call's URL to `/api/v1/tasks/{taskId}:cancel`.
    -   Update the request `body` to be a JSON object conforming to the `CancelTaskRequest` type.

5.3. **Rewrite `handleSseMessage`:**
    -   Parse the incoming `event.data` into a `JSONRPCResponse` object from the SDK.
    -   Check for `rpcResponse.error`. If present, handle the error state.
    -   If `rpcResponse.result` exists, check its `kind` property (`status-update`, `artifact-update`, or `task`).
    -   For a `status-update`, access the `message` via `result.status.message`.
    -   Iterate through the `message.parts` array. Use a `switch` on `part.kind`:
        -   `case 'data'`: This is the new status signal logic. Inspect `part.data.type` (e.g., `tool_invocation_start`, `llm_invocation`) and update the UI state accordingly. This replaces all previous logic that parsed the `metadata` field.
        -   `case 'text'`: Append `part.text` to the content of the current message bubble.
    -   Update the logic that determines the end of a turn to use the `final` flag from `TaskStatusUpdateEvent` or the receipt of a final `Task` object.

### Step 6: Update UI Component Rendering

6.1. **Refactor `VisualizerStepCard.tsx`:**
    -   The `VisualizerStep` type will need to be updated to store the structured data from `DataPart`s instead of a flat `metadata` object.
    -   The rendering functions within the component (e.g., `renderToolInvocationStartData`) must be updated to access data from the new structured fields (e.g., `step.data.toolInvocationStart.tool_name`).

6.2. **Refactor `MessageBubble.tsx`:**
    -   Update the component to correctly render the new `ToolEvent` data structure, which will now be populated from the parsed `DataPart` objects. This may involve creating new sub-components to display tool arguments and results in a structured way.

---

## Part 3: Validation

### Step 7: End-to-End Testing

7.1. **Launch System:** Start the refactored `http_sse` gateway, a backend agent, and the refactored Web UI.

7.2. **Execute Test Scenarios:**
    -   **Scenario A (Simple Chat):** Send a simple message and verify a text response is received and displayed correctly.
    -   **Scenario B (Tool Use):** Send a message that requires the agent to use a tool (e.g., "search the web for X").
        -   Verify that the UI displays the correct intermediate status messages (e.g., "Calling tool: web_search...").
        -   Verify that the `TaskMonitor` page correctly visualizes the tool call step.
        -   Verify the final result is displayed correctly.
    -   **Scenario C (File Upload & Processing):** Upload a file and ask the agent to process it.
        -   Verify the file is uploaded via the `/artifacts` endpoint.
        -   Verify the `/message:stream` call contains the correct `artifact://` URI.
        -   Verify the agent processes the file and returns a result.

7.3. **Verify Logs:** Check the browser console, gateway logs, and agent logs for any parsing errors, warnings, or exceptions throughout the test scenarios.
