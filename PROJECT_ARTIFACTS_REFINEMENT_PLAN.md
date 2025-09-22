### **Refined Implementation Plan for Project Artifacts**

This plan outlines the steps to display project artifacts in the UI before a chat session starts and to differentiate them visually from other artifacts.

#### **Phase 1: Pre-Session Artifact Loading**

**Goal:** Show project artifacts in the artifact panel as soon as a project is activated, before any messages are sent.

1.  **Backend: Create New Endpoint**
    *   **File:** `src/solace_agent_mesh/gateway/http_sse/routers/projects.py`
    *   **Action:** Add a new API endpoint: `GET /api/v1/projects/{project_id}/artifacts`.
    *   **Logic:** This endpoint will take a `project_id` and use the `get_artifact_info_list` helper to retrieve the list of artifacts associated with that project. It will use the special session ID format `f"project-{project_id}"` to query the artifact store.

2.  **Frontend: Update Artifact Fetching Logic**
    *   **File:** `client/webui/frontend/src/lib/hooks/useArtifacts.ts`
    *   **Action:** Modify the `useArtifacts` hook to use the `useProjectContext` hook internally. It will no longer accept a `projectId` prop.
    *   **Logic:**
        *   The hook will get the `activeProject` from `useProjectContext`.
        *   If a `sessionId` is present, it will fetch artifacts from `/api/v1/artifacts/{sessionId}`. This is the primary data source for an active chat.
        *   If `sessionId` is `null` or empty, but an `activeProject.id` exists, it will fetch artifacts from the new `/api/v1/projects/{activeProject.id}/artifacts` endpoint. This covers the pre-session state.
        *   If neither is present, it will return an empty list.

3.  **Frontend: Connect Project Context**
    *   **File:** `client/webui/frontend/src/lib/providers/ChatProvider.tsx`
    *   **Action:** Simplify the `useArtifacts` hook invocation.
    *   **Logic:** The `useArtifacts` hook will no longer need the `activeProject.id` to be passed to it, as it now retrieves this internally. The call in `ChatProvider` will be simplified to just `useArtifacts(sessionId)`.

#### **Phase 2: Differentiating Project Artifacts**

**Goal:** Visually distinguish artifacts that originate from a project.

1.  **Backend: Update Data Models**
    *   **File:** `src/solace_agent_mesh/common/a2a/types.py`
    *   **Action:** Add an optional `source: Optional[str] = None` field to the `ArtifactInfo` Pydantic model.

2.  **Frontend: Update Data Models**
    *   **File:** `client/webui/frontend/src/lib/types/fe.ts`
    *   **Action:** Add an optional `source?: string;` field to the `ArtifactInfo` TypeScript interface.

3.  **Backend: Populate the `source` Field**
    *   **File:** `src/solace_agent_mesh/agent/utils/artifact_helpers.py`
    *   **Action:** In the `get_artifact_info_list` function, when processing each artifact's metadata, check for the existence of a `source` key. If present, add its value to the `ArtifactInfo` object being constructed.
    *   **File:** `src/solace_agent_mesh/gateway/http_sse/services/project_service.py`
    *   **Action:** In `create_project`, ensure the metadata dictionary passed to `save_artifact_with_metadata` includes `{"source": "project"}`. This ensures newly uploaded project artifacts have the correct source from the start.
    *   **File:** `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`
    *   **Action:** In `_inject_project_context`, when copying artifacts, ensure the metadata passed to `save_artifact_with_metadata` includes `{"source": "project"}`.

4.  **Frontend: Render Visual Indicator**
    *   **File:** `client/webui/frontend/src/lib/components/chat/artifact/ArtifactCard.tsx`
    *   **Action:** In the component, check if `artifact.source === 'project'`.
    *   **Logic:** If the condition is true, apply a different style or add a visual indicator to differentiate the artifact. The exact UI representation is to be determined.

#### **Phase 3: Transition to Active Session**

**Goal:** Ensure a smooth transition from the pre-session view to the active session view.

*   No new files are needed for this phase; the logic is handled by the changes in Phase 1.
*   **Flow:**
    1.  User activates a project in the UI. `ProjectProvider` updates its state, setting `activeProject`. `sessionId` in `ChatProvider` is empty.
    2.  The `useArtifacts` hook, powered by `useProjectContext`, detects the `activeProject` and calls the `/api/v1/projects/{projectId}/artifacts` endpoint. The artifact panel populates.
    3.  User sends the first message.
    4.  The backend creates a session, gets a `sessionId`, and copies project artifacts into that session's storage (as part of `_inject_project_context`).
    5.  The frontend `ChatProvider` receives the new `sessionId` and updates its state.
    6.  The `useArtifacts` hook re-renders. Now that `sessionId` is populated, its logic prioritizes fetching from `/api/v1/artifacts/{sessionId}`. The panel updates to show the artifacts from the session, which now includes the copied project artifacts with their `source` metadata.
