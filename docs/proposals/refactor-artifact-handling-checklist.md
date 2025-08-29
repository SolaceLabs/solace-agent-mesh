# Implementation Checklist: Gateway-Centric Artifact Handling

This checklist tracks the implementation tasks for the artifact handling refactoring.

## Part 1: Foundational Backend Utilities & Configuration

- [x] **1. Create Artifact URI Utilities:**
    -   **File:** `src/solace_agent_mesh/agent/utils/artifact_helpers.py`
    -   **Task:** Add `format_artifact_uri` and `parse_artifact_uri` functions.

- [x] **2. Update Gateway Configuration:**
    -   **File:** `src/solace_agent_mesh/gateway/base/app.py`
    -   **Task:** Update the `artifact_handling_mode` parameter to include `passthrough` and set the default to `reference`.

- [x] **3. Enhance `FilePart` Preparation Utility:**
    -   **File:** `src/solace_agent_mesh/common/a2a/artifact.py`
    -   **Task:** Add logic to `prepare_file_part_for_publishing` to handle the `embed` mode by resolving URIs to bytes.

## Part 2: Gateway and Endpoint Logic

- [x] **4. Update Artifact Upload Endpoint:**
    -   **File:** `src/solace_agent_mesh/gateway/http_sse/routers/artifacts.py`
    -   **Task:** Modify the `upload_artifact` function to return a standard `artifact://` URI in its JSON response.

- [x] **5. Simplify HTTP SSE Gateway Input Handling:**
    -   **File:** `src/solace_agent_mesh/gateway/http_sse/component.py`
    -   **Task:** Refactor `_translate_external_input` to remove file-saving logic and pass `FilePart` objects through to the base component.

## Part 3: Agent-Side Processing

- [x] **6. Update A2A-to-ADK Translation:**
    -   **File:** `src/solace_agent_mesh/common/a2a/translation.py`
    -   **Task:** Update `translate_a2a_to_adk_content` to correctly process `FilePart` objects that contain inline `bytes`.

## Part 4: Frontend Implementation

- [ ] **7. Implement Hybrid File Upload in UI:**
    -   **File:** `client/webui/frontend/src/lib/providers/ChatProvider.tsx`
    -   **Task:** Refactor `handleSubmit` to implement the hybrid upload strategy based on the 1MB file size threshold.
