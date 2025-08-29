# Implementation Plan: Gateway-Centric Artifact Handling

This document outlines the step-by-step implementation plan for the artifact handling refactoring.

## Part 1: Foundational Backend Utilities & Configuration

### 1. Create Artifact URI Utilities

**Goal:** Centralize the creation and parsing of `artifact://` URIs to ensure consistency.

*   **File:** `src/solace_agent_mesh/agent/utils/artifact_helpers.py`
*   **Action:** Add two new functions, `format_artifact_uri` and `parse_artifact_uri`, to this file. These will handle the creation and deconstruction of `artifact://` URIs.

### 2. Update Gateway Configuration

**Goal:** Update the gateway's configuration schema to support the new artifact handling policies.

*   **File:** `src/solace_agent_mesh/gateway/base/app.py`
*   **Action:** In the `BASE_GATEWAY_APP_SCHEMA` constant, find the `artifact_handling_mode` parameter and update its definition.
    *   Change the `enum` to `["reference", "embed", "passthrough"]`.
    *   Change the `default` value to `"reference"`.
    *   Update the `description` to clearly explain what each of the three modes does.

### 3. Enhance the `FilePart` Preparation Utility

**Goal:** Update the core utility for gateway normalization to handle the new `embed` mode, where it must resolve a URI into inline bytes.

*   **File:** `src/solace_agent_mesh/common/a2a/artifact.py`
*   **Action:** Modify the `prepare_file_part_for_publishing` function.
    *   Add logic for when `mode == "embed"`.
    *   If the incoming `FilePart` has a `uri`, this new logic will use the `artifact_service` to load the artifact's content.
    *   It will then base64-encode the content and return a new `FilePart` with the `bytes` field populated.

## Part 2: Gateway and Endpoint Logic

### 4. Update the Artifact Upload Endpoint

**Goal:** Ensure the artifact upload endpoint returns a standard URI that the frontend expects for large file uploads.

*   **File:** `src/solace_agent_mesh/gateway/http_sse/routers/artifacts.py`
*   **Action:** Modify the `upload_artifact` function.
    *   After the file is successfully saved, call the new `format_artifact_uri` utility function from Step 1.
    *   Add the generated `uri` string to the JSON dictionary that is returned to the frontend.

### 5. Simplify the HTTP SSE Gateway's Input Handling

**Goal:** Remove redundant file-saving logic from the `WebUIBackendComponent` to allow the frontend's hybrid approach to work correctly.

*   **File:** `src/solace_agent_mesh/gateway/http_sse/component.py`
*   **Action:** Refactor the `_translate_external_input` method.
    *   Remove the existing logic that saves `UploadFile` objects to the artifact store.
    *   The new, simpler logic will inspect the `FilePart` objects it receives from the frontend (which will now contain either `bytes` or a `uri`) and pass them through directly. The `BaseGatewayComponent` will handle the normalization.

## Part 3: Agent-Side Processing

### 6. Update A2A-to-ADK Translation

**Goal:** Ensure the agent can correctly process an A2A message that contains an inline file.

*   **File:** `src/solace_agent_mesh/common/a2a/translation.py`
*   **Action:** Modify the `translate_a2a_to_adk_content` function.
    *   In the loop that processes message parts, add a condition to check if a `FilePart` contains `file.bytes`.
    *   If it does, the function must base64-decode the string into raw bytes and create an `adk_types.Part.from_data()` object.

## Part 4: Frontend Implementation

### 7. Implement Hybrid File Upload in the UI

**Goal:** Implement the client-side logic to handle small and large files differently.

*   **File:** `client/webui/frontend/src/lib/providers/ChatProvider.tsx`
*   **Action:** Refactor the `handleSubmit` function.
    *   Define a constant for the file size threshold: `const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB`.
    *   Add a helper utility function within the provider to convert a `File` object into a base64 string.
    *   In `handleSubmit`, replace the current file upload logic. The new logic will iterate through the user's selected files:
        *   If a file's size is less than the threshold, it will be converted to base64, and a `FilePart` with `bytes` will be created.
        *   If a file's size is greater than or equal to the threshold, the existing `uploadArtifactFile` function will be called, and a `FilePart` with the returned `uri` will be created.
    *   These newly created `FilePart` objects will then be added to the message payload sent to the backend.
