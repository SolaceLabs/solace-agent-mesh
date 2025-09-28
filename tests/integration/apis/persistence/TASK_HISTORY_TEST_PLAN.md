# Test Plan: Task & Event Storage Feature

This document outlines the comprehensive test plan for validating the task history persistence and retrieval feature in the Solace Agent Mesh (SAM). The tests cover API functionality, configuration options, data integrity, and security aspects of the feature.

---

## Group 1: Task History API Tests (`/api/v1/tasks`)

This group of tests validates the public-facing API endpoints for searching and retrieving historical task data. These tests will be located in `tests/integration/apis/persistence/test_task_history_api.py`.

### Test 1.1: Empty State Retrieval

*   **Objective:** Verify that the API returns a correct empty response when no tasks have been recorded.
*   **Steps:**
    1.  Ensure the test database is in a clean state.
    2.  Make a `GET` request to `/api/v1/tasks`.
*   **Assertions:**
    *   The HTTP status code is `200 OK`.
    *   The response body is a JSON object containing an empty list for the `tasks` key.

### Test 1.2: Basic Task Creation and Retrieval

*   **Objective:** Ensure that a successfully created task is persisted and can be retrieved via the API.
*   **Steps:**
    1.  Submit a new task via the `/api/v1/message:stream` endpoint.
    2.  Make a `GET` request to `/api/v1/tasks`.
*   **Assertions:**
    *   The response contains a list with exactly one task.
    *   The task object in the response has the correct `id`, `user_id`, and a non-null `start_time`.
    *   The `initial_request_text` field matches the text from the initial user message.

### Test 1.3: Search and Filtering Logic

*   **Objective:** Validate the search and date-based filtering capabilities of the tasks API.
*   **Steps:**
    1.  Create three distinct tasks with unique initial messages (e.g., "Alpha task", "Bravo task", "Charlie task") at slightly different timestamps.
    2.  Perform a `GET` request to `/api/v1/tasks` using the `search` query parameter (e.g., `?search=Bravo`).
    3.  Perform `GET` requests using `start_date` and `end_date` ISO 8601 timestamp parameters to isolate specific tasks.
    4.  Perform a `GET` request combining both `search` and date filters.
*   **Assertions:**
    *   The search query correctly returns only the "Bravo task".
    *   The date filters correctly include/exclude tasks based on their `start_time`.
    *   The combined filter correctly returns the intersection of the results.

### Test 1.4: Pagination Logic

*   **Objective:** Verify that the API correctly paginates large sets of task results.
*   **Steps:**
    1.  Create 25 tasks in a loop.
    2.  Make a `GET` request to `/api/v1/tasks?page=1&page_size=10`.
    3.  Make a `GET` request to `/api/v1/tasks?page=2&page_size=10`.
    4.  Make a `GET` request to `/api/v1/tasks?page=3&page_size=10`.
*   **Assertions:**
    *   The first request returns 10 tasks.
    *   The second request returns 10 different tasks.
    *   The third request returns the final 5 tasks.
    *   The tasks in all responses are ordered by `start_time` in descending order (most recent first).

### Test 1.5: Task Detail Retrieval as `.stim` File

*   **Objective:** Ensure the `GET /api/v1/tasks/{task_id}` endpoint returns a complete, correctly formatted `.stim` file.
*   **Steps:**
    1.  Create a task and send a few follow-up messages to generate a history of events.
    2.  Make a `GET` request to `/api/v1/tasks/{task_id}` for the created task.
*   **Assertions:**
    *   The HTTP status code is `200 OK`.
    *   The `Content-Type` header is `application/x-yaml`.
    *   The `Content-Disposition` header suggests a filename like `{task_id}.stim`.
    *   The response body is valid YAML.
    *   The parsed YAML has the correct top-level keys: `invocation_details` and `invocation_flow`.
    *   `invocation_details` contains accurate metadata about the task (`id`, `user_id`, `status`, etc.).
    *   `invocation_flow` is a list containing all the request and response events that occurred during the task's lifecycle.

---

## Group 2: Task Logger Service & Configuration Tests

This group validates that the `TaskLoggerService` correctly adheres to the `task_logging` configuration block. These tests will require monkeypatching the component's configuration to simulate different settings.

### Test 2.1: Master `enabled` Flag

*   **Objective:** Verify that the top-level `enabled` flag controls the entire logging feature.
*   **Steps:**
    1.  Configure the component with `task_logging: { enabled: false }`.
    2.  Create a new task.
    3.  Make a `GET` request to `/api/v1/tasks`.
    4.  Re-configure the component with `task_logging: { enabled: true }`.
    5.  Create another new task.
    6.  Make a `GET` request to `/api/v1/tasks`.
*   **Assertions:**
    *   After step 3, the task list is empty.
    *   After step 6, the task list contains only the second task.

### Test 2.2: Event Type Logging Flags

*   **Objective:** Ensure that specific event types can be excluded from the log.
*   **Steps & Assertions:**
    *   **Scenario A (No Status Updates):**
        1.  Configure with `log_status_updates: false`.
        2.  Run a streaming task that is known to produce `status-update` events.
        3.  Retrieve the `.stim` file for the task.
        4.  Assert that the `invocation_flow` list contains no events where the payload's `kind` is `status-update`.
    *   **Scenario B (No Artifact Events):**
        1.  Configure with `log_artifact_events: false`.
        2.  Run a task that creates an artifact, producing an `artifact-update` event.
        3.  Retrieve the `.stim` file for the task.
        4.  Assert that the `invocation_flow` list contains no events where the payload's `kind` is `artifact-update`.

### Test 2.3: File Content Logging Configuration

*   **Objective:** Validate the rules for logging file content within event payloads.
*   **Steps & Assertions:**
    *   **Scenario A (File Parts Disabled):**
        1.  Configure with `log_file_parts: false`.
        2.  Send a task with a file attachment.
        3.  Retrieve the `.stim` file and inspect the initial request event payload.
        4.  Assert that the `parts` array in the payload does not contain the `file` part.
    *   **Scenario B (Small File):**
        1.  Configure with `log_file_parts: true`.
        2.  Send a task with a small (e.g., 1KB) file.
        3.  Retrieve the `.stim` file.
        4.  Assert that the `file` part exists in the request payload and its `bytes` field contains the full base64-encoded content.
    *   **Scenario C (Large File Truncation):**
        1.  Configure with `log_file_parts: true` and `max_file_part_size_bytes: 1024`.
        2.  Send a task with a 2KB file.
        3.  Retrieve the `.stim` file.
        4.  Assert that the `file` part's `bytes` field has been replaced with the string `"[Content stripped, size > 1024 bytes]"`.

---

## Group 3: Data Integrity and Edge Case Tests

This group focuses on the correctness and consistency of the data stored in the database.

### Test 3.1: Task Lifecycle Status Updates

*   **Objective:** Verify that the `status` and `end_time` fields of a task record are correctly updated as it progresses.
*   **Steps:**
    1.  Create a new task.
    2.  Immediately query the `tasks` table for that task record.
    3.  Wait for the task to complete successfully.
    4.  Query the record again.
    5.  Create a separate task designed to fail.
    6.  Wait for it to fail and query its record.
*   **Assertions:**
    *   After step 2, the `status` and `end_time` columns are `NULL`.
    *   After step 4, `end_time` is a non-null integer, and `status` is `'completed'`.
    *   After step 6, `end_time` is non-null, and `status` is `'failed'`.

### Test 3.2: Initial Request Text Extraction

*   **Objective:** Ensure the `initial_request_text` is correctly extracted and stored.
*   **Steps & Assertions:**
    *   **Scenario A (Simple Text):** Create a task with a simple text message. Assert `initial_request_text` in the DB matches the message.
    *   **Scenario B (Multi-part):** Create a task with both text and a file. Assert `initial_request_text` contains only the text portion.
    *   **Scenario C (Truncation):** Create a task with a message longer than 1024 characters. Assert `initial_request_text` is truncated to 1024 characters.

### Test 3.3: Schema Integrity (Code Review)

*   **Objective:** Confirm that the database schema enforces referential integrity.
*   **Action:** Review the Alembic migration file (`...add_tasks_task_events...py`).
*   **Assertion:**
    *   Verify that the `ForeignKey` constraint on `task_events.task_id` includes the `ondelete='CASCADE'` option. This is a code inspection rather than a runtime test.

---

## Group 4: Authorization and Security Tests

This group validates that the task history API correctly enforces user-based access control.

### Test 4.1: User Data Isolation in List View

*   **Objective:** Ensure users can only see their own tasks in the main list view.
*   **Steps:**
    1.  Use a multi-user test fixture to get two authenticated clients (User A and User B).
    2.  User A creates two tasks.
    3.  User B creates one task.
    4.  User A calls `GET /api/v1/tasks`.
    5.  User B calls `GET /api/v1/tasks`.
*   **Assertions:**
    *   User A's response contains only their two tasks.
    *   User B's response contains only their one task.

### Test 4.2: Direct Access Control for Task Details

*   **Objective:** Prevent users from directly accessing the `.stim` file of another user's task.
*   **Steps:**
    1.  User A creates a task and gets its ID.
    2.  User B attempts to make a `GET` request to `/api/v1/tasks/{user_A_task_id}`.
*   **Assertions:**
    *   The request from User B fails with an `HTTP 403 Forbidden` status code.

### Test 4.3: Privileged Access with `tasks:read:all` Scope

*   **Objective:** Verify that users with a specific permission scope can query tasks for other users.
*   **Steps:**
    1.  Configure a test user ("admin") with the `tasks:read:all` scope in their user config.
    2.  Have a regular user ("user") create a task.
    3.  The admin user calls `GET /api/v1/tasks?query_user_id={user_id}`.
    4.  The admin user calls `GET /api/v1/tasks` (with no `query_user_id`).
    5.  The regular user attempts to call `GET /api/v1/tasks?query_user_id={admin_id}`.
*   **Assertions:**
    *   The admin's request in step 3 succeeds and returns the regular user's task.
    *   The admin's request in step 4 succeeds and returns tasks from all users.
    *   The regular user's request in step 5 fails with an `HTTP 403 Forbidden` status code.

---

## Test Implementation Checklist

### Group 1: API Tests
- [ ] Test 1.1: Empty State Retrieval
- [ ] Test 1.2: Basic Task Creation and Retrieval
- [ ] Test 1.3: Search and Filtering Logic
- [ ] Test 1.4: Pagination Logic
- [ ] Test 1.5: Task Detail Retrieval as `.stim` File

### Group 2: Configuration Tests
- [ ] Test 2.1: Master `enabled` Flag
- [ ] Test 2.2: Event Type Logging Flags
- [ ] Test 2.3: File Content Logging Configuration

### Group 3: Data Integrity Tests
- [ ] Test 3.1: Task Lifecycle Status Updates
- [ ] Test 3.2: Initial Request Text Extraction
- [ ] Test 3.3: Schema Integrity (Code Review)

### Group 4: Authorization Tests
- [ ] Test 4.1: User Data Isolation in List View
- [ ] Test 4.2: Direct Access Control for Task Details
- [ ] Test 4.3: Privileged Access with `tasks:read:all` Scope
