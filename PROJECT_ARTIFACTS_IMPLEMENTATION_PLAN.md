### **Phase 1: Backend - Storing Project Artifacts**

1.  **Modify Project Creation Endpoint (`project_controller.py`):**
    *   Change the `create_project` function signature to accept multipart form data instead of a JSON body.
    *   It will now take `name: str = Form(...)`, `description: Optional[str] = Form(None)`, `system_prompt: Optional[str] = Form(None)`, and `files: List[UploadFile] = File(...)`.
    *   Pass the uploaded files to the service layer.

2.  **Update Project Service Logic (`project_service.py`):**
    *   Define the constant `GLOBAL_PROJECT_USER_ID = "_global_"` at the top of the file.
    *   Modify the `create_project` service method to accept the list of `UploadFile` objects.
    *   Inside the method, first, create the project entry in the database to obtain its `id`.
    *   Then, iterate through the list of `UploadFile`s. For each file:
        *   Use the existing `save_artifact_with_metadata` helper function.
        *   Pass the `project.user_id` as the `user_id` parameter to the helper (or `GLOBAL_PROJECT_USER_ID` for global projects).
        *   Pass a conventional `session_id` like `f"project-{project.id}"`.
    *   This will store the artifacts scoped to the newly created project.

3.  **Update Project Repository (`project_repository.py`):**
    *   The `copy_from_template` method in the repository needs to be updated to also copy the `system_prompt` from the template to the new project.

### **Phase 2: Frontend - Uploading Artifacts at Project Creation**

1.  **Enhance Project Creation Dialog (`CreateProjectDialog.tsx`):**
    *   Add a file input element (`<input type="file" multiple />`) to the form.
    *   Add state to manage the list of selected files and render their names in the UI so the user can see what they've staged for upload.

2.  **Update Form Submission Logic (`ProjectsPage.tsx`):**
    *   Modify the `handleCreateProject` function.
    *   Instead of passing a simple object, it will now construct a `FormData` object.
    *   Append the project's `name`, `description`, and `system_prompt` as fields to the `FormData`.
    *   Iterate through the selected files and append each one to the `FormData`.

3.  **Adapt Project Provider (`ProjectProvider.tsx`):**
    *   Change the `createProject` function to accept the `FormData` object.
    *   In the `authenticatedFetch` call for creating a project, pass the `FormData` object as the body.
    *   **Crucially**, remove the `Content-Type: application/json` header. The browser will automatically set the correct `multipart/form-data` header with the boundary.

### **Phase 3: Backend - Session Initialization & Artifact Copying**

1.  **Modify Task Submission Logic (`routers/tasks.py`):**
    *   In the `_submit_task` helper, add logic that runs only for the *first* message in a session that belongs to a project (`project_id` is present).
    *   Use `session_service.get_session_history` to check if the message count is zero.

2.  **Implement Artifact Copying:**
    *   If it's the first message, get the project details via `project_service.get_project`.
    *   Determine the source `user_id` for artifacts (the `project.user_id` or `GLOBAL_PROJECT_USER_ID` if it's a global project).
    *   Use `get_artifact_info_list` to list all artifacts from the project's special storage (`session_id = f"project-{project.id}"`).
    *   Loop through the resulting artifact list. For each artifact:
        *   Load its content and metadata using `load_artifact_content_or_metadata`.
        *   Save a *copy* into the current, real session using `save_artifact_with_metadata`, targeting the real `session_id` and `user_id`.

### **Phase 4: Backend - Prompt Injection**

1.  **Modify Task Submission Logic (`routers/tasks.py`):**
    *   During the artifact copy loop from Phase 3, build up a formatted string that describes the artifacts being added (e.g., `"- {filename}: {description}"`).
    *   Prepend this multi-line string to the user's message content, similar to how the project description and system prompt are already injected. This makes the agent aware of the files from the very first turn.
