### **Implementation Plan: Project File Management**

This plan details the necessary backend and frontend changes to allow users to add, remove, and edit the descriptions of files within a project.

**Files to be modified or created:**
- `src/solace_agent_mesh/gateway/http_sse/routers/projects.py`
- `src/solace_agent_mesh/gateway/http_sse/services/project_service.py`
- `client/webui/frontend/src/lib/providers/ProjectProvider.tsx`
- `client/webui/frontend/src/lib/types/projects.ts`
- `client/webui/frontend/src/lib/components/projects/ProjectFilesManager.tsx` (new file)
- `client/webui/frontend/src/lib/components/projects/ProjectDetailView.tsx`

---

### **Backend Implementation**

The backend will be updated with new endpoints and service logic to handle file manipulations for a specific project.

#### **1. Router Updates: `src/solace_agent_mesh/gateway/http_sse/routers/projects.py`**

Three new endpoints will be added to this router to manage project artifacts. A fourth will be added for fetching artifacts in a RESTful way. All endpoints must perform authorization checks to ensure the user owns the project.

1.  **Endpoint to Get Project Artifacts:**
    *   **Route:** `GET /projects/{project_id}/artifacts`
    *   **Response Model:** `list[ArtifactInfo]`
    *   **Logic:**
        *   Accepts `project_id` from the path.
        *   Depends on `get_project_service` and `get_user_id`.
        *   Calls a new service method `project_service.get_project_artifacts(project_id, user_id)`.
        *   Returns the list of `ArtifactInfo` objects.

2.  **Endpoint to Add Files to a Project:**
    *   **Route:** `POST /projects/{project_id}/artifacts`
    *   **Request:** `multipart/form-data` with `files: list[UploadFile]` and optional `file_metadata: str`.
    *   **Logic:**
        *   Accepts `project_id` from the path.
        *   Calls a new service method `project_service.add_artifacts_to_project(project_id, user_id, files, file_metadata)`.
        *   Returns a success response, potentially with details of the added artifacts.

3.  **Endpoint to Remove a File from a Project:**
    *   **Route:** `DELETE /projects/{project_id}/artifacts/{filename}`
    *   **Status Code:** `204 NO CONTENT` on success.
    *   **Logic:**
        *   Accepts `project_id` and `filename` from the path.
        *   Calls `project_service.delete_artifact_from_project(project_id, user_id, filename)`.

4.  **Endpoint to Update File Metadata:**
    *   **Route:** `PUT /projects/{project_id}/artifacts/{filename}/metadata`
    *   **Request Body:** A JSON object, e.g., `{ "description": "New file description" }`.
    *   **Logic:**
        *   Accepts `project_id` and `filename` from the path and a request body with the metadata to update.
        *   Calls `project_service.update_artifact_metadata_in_project(project_id, user_id, filename, update_data)`.
        *   Returns the updated artifact metadata on success.

#### **2. Service Layer Updates: `src/solace_agent_mesh/gateway/http_sse/services/project_service.py`**

New methods will be added to the `ProjectService` class to encapsulate the business logic.

1.  **`get_project_artifacts(self, project_id: str, user_id: str) -> List[ArtifactInfo]`:**
    *   **Logic:**
        *   Verifies user has access to the project using `self.get_project(project_id, user_id)`.
        *   Constructs the storage `session_id` for project artifacts: `f"project-{project_id}"`.
        *   Uses the shared `artifact_service` and the `get_artifact_info_list` helper to fetch and return the list of artifacts.

2.  **`add_artifacts_to_project(self, project_id: str, user_id: str, files: List[UploadFile], file_metadata: Optional[dict]) -> List[Dict]`:**
    *   **Logic:**
        *   Verifies user access to the project.
        *   Constructs the storage `session_id`: `f"project-{project_id}"`.
        *   Iterates through the uploaded files. For each file:
            *   Reads the file content.
            *   Constructs a `metadata` dictionary, including `{"source": "project"}` and any description from `file_metadata`.
            *   Calls `save_artifact_with_metadata` with the correct context.
        *   Returns a list of results from the save operations.

3.  **`delete_artifact_from_project(self, project_id: str, user_id: str, filename: str) -> bool`:**
    *   **Logic:**
        *   Verifies user access.
        *   Constructs the storage `session_id`: `f"project-{project_id}"`.
        *   Calls `self.artifact_service.delete_artifact` with the correct context.

4.  **`update_artifact_metadata_in_project(self, project_id: str, user_id: str, filename: str, update_data: dict) -> Dict`:**
    *   **Logic:**
        *   Verifies user access.
        *   Constructs storage context (`app_name`, `storage_user_id`, `storage_session_id`).
        *   Loads the latest version of the artifact's content using `load_artifact_content_or_metadata`.
        *   Loads the latest version of the artifact's *metadata* separately.
        *   Merges `update_data` (e.g., the new description) into the loaded metadata.
        *   Calls `save_artifact_with_metadata` using the original content bytes and the *newly merged* metadata dictionary. This will create a new version of the artifact with the updated metadata.
        *   Returns the result.

---

### **Frontend Implementation**

The frontend will introduce a new component for file management and update the project context provider.

#### **1. Project Provider Updates: `client/webui/frontend/src/lib/providers/ProjectProvider.tsx`**

The `ProjectProvider` will be enhanced with functions to call the new backend endpoints. These functions will be exposed via the `useProjectContext` hook.

*   **`addFilesToProject(projectId: string, formData: FormData) => Promise<void>`:**
    *   Makes a `POST` request to `/api/v1/projects/${projectId}/artifacts` with the `formData`.
*   **`removeFileFromProject(projectId: string, filename: string) => Promise<void>`:**
    *   Makes a `DELETE` request to `/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`.
*   **`updateFileDescription(projectId: string, filename: string, description: string) => Promise<void>`:**
    *   Makes a `PUT` request to `/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}/metadata` with a JSON body: `{ "description": description }`.

These functions will be added to the `ProjectContextValue` interface in `client/webui/frontend/src/lib/types/projects.ts`.

#### **2. New Component: `client/webui/frontend/src/lib/components/projects/ProjectFilesManager.tsx`**

A new component will be created to encapsulate all UI and logic for managing a project's files.

*   **Props:** `project: Project`, `isEditing: boolean`.
*   **State & Hooks:**
    *   Will use a new hook, `useProjectArtifacts(projectId)`, which fetches data from the `GET /api/v1/projects/{projectId}/artifacts` endpoint. This hook will be similar in structure to `useArtifacts`, providing `artifacts`, `isLoading`, `error`, and a `refetch` function.
*   **UI Rendering:**
    *   An "Add Files" button, which is always visible. Clicking it will trigger a file input dialog.
    *   A list of artifact cards, mapped from the `artifacts` state.
    *   Each card will display the artifact's name, icon, and other info.
    *   **Conditional UI based on `isEditing` prop:**
        *   If `true`, each artifact's description will be an editable `textarea` with a "Save" button.
        *   If `true`, a "Remove" button will be visible for each artifact.
        *   If `false`, the description is plain text, and edit/remove controls are hidden.
*   **Logic:**
    *   The component will use the functions from `useProjectContext` (`addFilesToProject`, etc.).
    *   After any file operation (add, remove, update), it will call the `refetch` function from its local `useProjectArtifacts` hook to update the file list.

#### **3. View Integration: `client/webui/frontend/src/lib/components/projects/ProjectDetailView.tsx`**

This view will be updated to host the new file manager and control its edit state.

*   **State:**
    *   Add a local state variable: `const [isEditing, setIsEditing] = useState(false);`.
*   **UI:**
    *   Add an "Edit Project" button to the view's header or content area. This button will toggle the `isEditing` state.
    *   Integrate the new `<ProjectFilesManager project={project} isEditing={isEditing} />` component within the `CardContent`.
    *   The project `name` and `description` fields can also be made conditionally editable based on the `isEditing` state. When a "Save" button is clicked for these fields, it will call the existing project update logic.
