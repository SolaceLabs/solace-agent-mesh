# System Prompt Implementation Plan

**Goal:** Add a "system prompt" field to projects. This prompt will be automatically prepended to the first message of any chat session associated with that project.

---

### Phase 1: Backend - Extend Data Model and APIs

This phase focuses on updating the backend to store and manage the `system_prompt` for each project.

1.  **Update Database Model (`src/solace_agent_mesh/gateway/http_sse/infrastructure/persistence/models.py`)**:
    *   Add a `system_prompt` column (e.g., `Column(Text, nullable=True)`) to the `Project` model.

2.  **Update DTOs**:
    *   **`src/solace_agent_mesh/gateway/http_sse/api/dto/requests/project_requests.py`**:
        *   Add an optional `system_prompt: Optional[str]` field to `CreateProjectRequest` and `UpdateProjectRequest`.
    *   **`src/solace_agent_mesh/gateway/http_sse/api/dto/responses/project_responses.py`**:
        *   Add `system_prompt: Optional[str]` to the `ProjectResponse` model.

3.  **Update Domain Model (`src/solace_agent_mesh/gateway/http_sse/domain/entities/project_domain.py`)**:
    *   Add `system_prompt: Optional[str]` to the `ProjectDomain` model.

4.  **Update Repository (`src/solace_agent_mesh/gateway/http_sse/infrastructure/repositories/project_repository.py`)**:
    *   Modify `create_project` to accept and save the `system_prompt`.
    *   Modify `update` to handle updates to the `system_prompt` field.

5.  **Update Service (`src/solace_agent_mesh/gateway/http_sse/application/services/project_service.py`)**:
    *   Modify the signatures of `create_project` and `update_project` to accept `system_prompt`.
    *   Pass the `system_prompt` to the corresponding repository methods.
    *   Ensure the `system_prompt` is included when converting the database model to `ProjectDomain`.

6.  **Update Controller (`src/solace_agent_mesh/gateway/http_sse/api/controllers/project_controller.py`)**:
    *   Update `create_project` and `update_project` to read `system_prompt` from the request body and pass it to the service.
    *   Ensure `get_project` and `get_user_projects` include `system_prompt` in the `ProjectResponse`.

---

### Phase 2: Frontend - UI for Managing System Prompts

This phase adds the necessary UI elements for users to create and view system prompts.

1.  **Update Types (`client/webui/frontend/src/lib/types/projects.ts`)**:
    *   Add an optional `system_prompt?: string | null` field to the `Project` interface.
    *   Add an optional `system_prompt: string` field to the `ProjectFormData` interface.
    *   Add `system_prompt` to the `CreateProjectRequest` interface.

2.  **Update Create Project Dialog (`client/webui/frontend/src/lib/components/projects/CreateProjectDialog.tsx`)**:
    *   Add a new `<FormField>` with a `<Textarea>` for the `system_prompt`. This field should be optional.
    *   Initialize the field in `useForm`'s `defaultValues`.

3.  **Update Projects Page (`client/webui/frontend/src/lib/components/projects/ProjectsPage.tsx`)**:
    *   Modify `handleCreateProject` to include `system_prompt` in the data passed to the `createProject` function.

4.  **Update Project Detail View (`client/webui/frontend/src/lib/components/projects/ProjectDetailView.tsx`)**:
    *   Render the `system_prompt` from the project details, for instance in its own section below the description. Clearly indicate if no system prompt is provided.

---

### Phase 3: Backend - Implement Prompt Injection

This phase implements the core logic to inject the system prompt into the chat.

1.  **Modify Injection Logic (`src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`)**:
    *   Locate the existing project description injection logic inside the `_submit_task` function.
    *   Within the `if not history or history.total_message_count == 0:` block where the project is already being fetched, add logic to also retrieve the `system_prompt`.
    *   Construct a combined context string that includes both the system prompt and the project description (if they exist).
    *   Prepend this combined context to the `message_text`.
    *   Ensure the logic gracefully handles cases where `system_prompt` or `description` are missing. The existing `project_service.get_project` call can be reused, preventing an extra database lookup.
