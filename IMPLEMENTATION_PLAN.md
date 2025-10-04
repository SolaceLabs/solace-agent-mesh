# Implementation Plan: Real-Time Artifact Creation Status

This document outlines the steps required to integrate the real-time artifact creation status feature into the current codebase. The plan is divided into three phases: project configuration, backend implementation, and frontend implementation.

## Phase 1: Project Configuration & Cleanup

This phase involves updating project configuration files and renaming example files for consistency.

1.  **Update `.gitignore`**: Add a pattern to ignore rotated log files (e.g., `sam.log.1`).

2.  **Update VS Code Launch Configuration**: Modify `.vscode/launch.json` to:
    *   Remove the hardcoded `LOGGING_CONFIG_PATH` environment variable from all launch configurations.
    *   Update the `args` to point to the new, renamed example YAML files.
    *   Add the new "Employee" launch configuration.

3.  **Rename Example Files**: This is a manual step. You will need to rename the following files in your `examples/` directory to align with the updated launch configuration.
    *   `examples/agents/orchestrator_example.yaml` -> `examples/a2a_orchestrator.yaml`
    *   `examples/agents/a2a_agents_example.yaml` -> `examples/a2a_agents.yaml`
    *   `examples/gateways/webui_example.yaml` -> `examples/webui_backend.yaml`
    *   `examples/agents/a2a_multimodal_example.yaml` -> `examples/a2a_multimodal.yaml`
    *   `examples/gateways/slack_gateway_example.yaml` -> `examples/slack_gateway_example.yaml`
    *   `examples/gateways/webhook_gateway_example.yaml` -> `examples/webhook_gateway_example.yaml`
    *   `examples/gateways/sam_em_gateway.yaml` -> `examples/sam_em_gateway.yaml`

## Phase 2: Backend Implementation

This phase focuses on updating the data contracts and backend logic to generate and send the new progress events.

4.  **Update Data Contract Schema**: Modify `src/solace_agent_mesh/common/a2a_spec/schemas/artifact_creation_progress.json`. This change introduces the `status` field, renames `bytes_saved` to `bytes_transferred`, and makes `artifact_chunk` optional.

5.  **Update Pydantic Model**: Align the `ArtifactCreationProgressData` model in `src/solace_agent_mesh/common/data_parts.py` with the new JSON schema.

6.  **Enhance Backend Callback Logic**: Update the `process_artifact_blocks_callback` function in `src/solace_agent_mesh/agent/adk/callbacks.py`. This is a critical step where the logic will be changed to publish `in-progress`, `completed`, and `failed` status updates based on the state of artifact streaming.

## Phase 3: Frontend Implementation

This phase involves creating the new UI components and updating the state management to render the real-time progress.

7.  **Update Frontend Type Definition**: Add the optional `inProgressArtifact` property to the `MessageFE` interface in `client/webui/frontend/src/lib/types/fe.ts`. This allows the frontend message state to track an in-progress artifact upload.

8.  **Create New UI Component for In-Progress State**: Create a new file `client/webui/frontend/src/lib/components/chat/file/InProgressFileMessage.tsx`. This component will render the "Saving..." capsule with a loading spinner and byte count.

9.  **Create New UI Component for Artifact Notification**: Create a new file `client/webui/frontend/src/lib/components/chat/artifact/ArtifactNotificationMessage.tsx`. This component will render the final artifact capsule upon completion and is designed to handle cases where the full artifact info might not be available immediately.

10. **Create Component Index Files**: To make imports cleaner, create two new files:
    *   `client/webui/frontend/src/lib/components/chat/file/index.ts`
    *   `client/webui/frontend/src/lib/components/chat/artifact/index.ts`
    These files will export the new components from their respective directories.

11. **Update Chat Message Rendering**: Modify `client/webui/frontend/src/lib/components/chat/ChatMessage.tsx`. The logic here will be updated to conditionally render the new `InProgressFileMessage` and `ArtifactNotificationMessage` components, separate from the main chat bubble.

12. **Refactor Core Chat State Management**: This is the most complex step. The `handleSseMessage` function (or its equivalent) within `client/webui/frontend/src/lib/providers/ChatProvider.tsx` must be significantly refactored. The new logic will function as a state machine to:
    *   Create a new "in-progress" message bubble when an `artifact_creation_progress` event with `status: "in-progress"` is received.
    *   Find and update the existing in-progress bubble with new `bytesTransferred` on subsequent progress events.
    *   Transform the in-progress bubble into a final artifact notification or an error message when a `completed` or `failed` status is received.
    *   Handle edge cases, such as finalizing any lingering in-progress bubbles when a task ends unexpectedly.

