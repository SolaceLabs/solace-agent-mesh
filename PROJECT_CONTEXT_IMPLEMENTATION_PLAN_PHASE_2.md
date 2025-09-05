# Phase 2: Project Context Integration and Session Filtering

**Goal:** Connect the project context to the application, introduce a project detail view, and filter chat sessions based on an "active" project.

---

### Step 1: Backend - Associate Sessions with Projects

First, we need to update the backend to link sessions to projects.

1.  **Update Database Model (`database/models.py`)**:
    *   Add a `project_id` column to the `Session` model. This should be a nullable foreign key to the `projects.id` table with `ondelete="CASCADE"`.

2.  **Update DTOs (`api/dto/requests/session_requests.py`)**:
    *   In `CreateSessionRequest`, add an optional `project_id: str` field.

3.  **Update Session Service (`business/services/session_service.py`)**:
    *   Modify `create_session` to accept and save the `project_id`.
    *   Modify `get_user_sessions` to accept an optional `project_id` and filter the query accordingly. If `project_id` is provided, return only sessions matching that project.

4.  **Update Session Controller (`api/controllers/session_controller.py`)**:
    *   In the `get_all_sessions` endpoint, accept an optional `project_id` query parameter and pass it to the service.

---

### Step 2: Frontend - Implement Project Detail and Activation Flow

Next, we'll create the UI for viewing and activating a project.

1.  **Create `ProjectDetailView.tsx` Component**:
    *   This new component will display a project's name and description.
    *   It will include an "Activate Project" button.
    *   It will have a "Back to all projects" button that calls `setCurrentProject(null)`.

2.  **Update `ProjectsPage.tsx`**:
    *   Modify the component to use the `currentProject` from `useProjectContext`.
    *   If `currentProject` is `null`, render the `ProjectList`.
    *   If `currentProject` is set, render the new `ProjectDetailView` component.

3.  **Update `ProjectProvider.tsx`**:
    *   Add `activeProject` and `setActiveProject` to the context state and value. `activeProject` will be set when the user clicks "Activate Project".

---

### Step 3: Frontend - Display Active Project and Filter Sessions

Finally, we'll make the `ChatPage` aware of the active project.

1.  **Update `ChatPage.tsx`**:
    *   Consume `useProjectContext` to get `activeProject` and `setActiveProject`.
    *   Modify the `Header`'s `title` prop to display the `activeProject.name` when a project is active.
    *   Add a leading action (e.g., an "Exit Project" button) to the `Header` that calls `setActiveProject(null)` and navigates the user back to the projects page.

2.  **Update `ChatProvider.tsx`**:
    *   Consume `useProjectContext` to get `activeProject`.
    *   Create a `useEffect` hook that listens for changes to `activeProject`.
    *   When `activeProject` changes, refetch the list of sessions by calling the `/api/v1/sessions` endpoint with a `?project_id=${activeProject.id}` query parameter.
    *   When `activeProject` is set, clear the current chat messages and session list to reflect the new context.
    *   Modify `handleSubmit` to include the `project_id` from `activeProject` when creating a new session via the `/tasks/subscribe` endpoint. This ensures new chats are correctly associated with the active project.

3.  **Update `SessionSidePanel.tsx` and `ChatSessions.tsx`**:
    *   No direct changes are needed here. Since these components get their session list from `ChatProvider`, they will automatically display the filtered list of sessions once `ChatProvider` is updated.
