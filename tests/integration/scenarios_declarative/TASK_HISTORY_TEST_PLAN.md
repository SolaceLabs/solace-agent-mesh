# Test Plan: Task & Event Storage Feature (Declarative & Imperative)

This document outlines the comprehensive test plan for validating the task history persistence and retrieval feature in the Solace Agent Mesh (SAM). The plan utilizes a hybrid approach:

-   **Declarative Tests (YAML):** For validating the primary API functionality and data integrity in a high-fidelity, end-to-end environment. These tests are located in `tests/integration/scenarios_declarative/test_data/api/`.
-   **Imperative Tests (Python):** For testing complex configuration variations and multi-user security scenarios that require fine-grained control over the test setup. These tests will remain in `tests/integration/apis/`.

---

## Group 1: Declarative API Tests (`/api/v1/tasks`)

This group of tests validates the public-facing API endpoints for searching and retrieving historical task data using the declarative YAML framework.

### Test 1.1: Empty State Retrieval

*   **Objective:** Verify that the API returns a correct empty response when no tasks have been recorded.
*   **Implementation:** A YAML test with no `http_request_input`, only an `expected_http_responses` block that asserts `GET /api/v1/tasks` returns an empty list.
*   **Status:** Implemented in `api_get_empty_tasks.yaml`.

### Test 1.2: Basic Task Creation and Retrieval

*   **Objective:** Ensure that a successfully created task is persisted and can be retrieved via the API.
*   **Implementation:** A YAML test using `http_request_input` to create a task, and `expected_http_responses` to assert its presence in the `GET /api/v1/tasks` list.
*   **Status:** Implemented in `api_create_and_get_task.yaml`.

### Test 1.3: Search and Filtering Logic

*   **Objective:** Validate the search and date-based filtering capabilities of the tasks API.
*   **Implementation:**
    1.  Create multiple tasks with unique messages and timestamps via `http_request_input` across several YAML files.
    2.  Use `expected_http_responses` with `query_params` (`search`, `start_date`, `end_date`) to test filtering.
    3.  Assert that the response body contains only the expected tasks.

### Test 1.4: Pagination Logic

*   **Objective:** Verify that the API correctly paginates large sets of task results.
*   **Implementation:**
    1.  Create a large number of tasks (e.g., >10).
    2.  Use multiple `expected_http_responses` blocks to query different pages (`?page=1&page_size=5`, `?page=2&page_size=5`).
    3.  Assert the content of each page and the total number of items.

### Test 1.5: Task Detail Retrieval as `.stim` File

*   **Objective:** Ensure the `GET /api/v1/tasks/{task_id}` endpoint returns a complete, correctly formatted `.stim` file.
*   **Implementation:**
    1.  Create a task via `http_request_input`.
    2.  Use `expected_http_responses` to `GET /api/v1/tasks/{task_id}`.
    3.  Assert the `Content-Type` header is `application/x-yaml`.
    4.  Use `text_contains` to verify key strings are present in the YAML output (e.g., `invocation_details`, `task_id`).

---

## Group 2: Declarative Data Integrity Tests

This group focuses on the correctness and consistency of the data stored in the database, validated through the declarative API tests.

### Test 2.1: Task Lifecycle Status Updates

*   **Objective:** Verify that the `status` and `end_time` fields of a task record are correctly updated as it progresses.
*   **Implementation:** In a declarative test, after the task completes, the `expected_http_responses` block will query `GET /api/v1/tasks` and assert that the task's `status` is `'completed'` and `end_time` is not null.
*   **Status:** Partially covered by `api_create_and_get_task.yaml`.

### Test 2.2: Initial Request Text Extraction

*   **Objective:** Ensure the `initial_request_text` is correctly extracted and stored.
*   **Implementation:** In a declarative test, assert that the `initial_request_text` field in the response from `GET /api/v1/tasks` matches (or contains) the text from the initial `http_request_input`.
*   **Status:** Implemented in `api_create_and_get_task.yaml`.

### Test 2.3: Schema Integrity (Code Review)

*   **Objective:** Confirm that the database schema enforces referential integrity.
*   **Action:** Review the Alembic migration file (`...add_tasks_task_events...py`).
*   **Assertion:** Verify that the `ForeignKey` constraint on `task_events.task_id` includes the `ondelete='CASCADE'` option. This is a code inspection, not a runtime test.

---

## Group 3: Imperative Configuration Tests (Python)

These tests require monkeypatching the gateway component's configuration and are better suited for imperative Python tests. They will remain in `tests/integration/apis/`.

*   **Test 3.1: Master `enabled` Flag:** Verify that `task_logging: { enabled: false }` disables all logging.
*   **Test 3.2: Event Type Logging Flags:** Verify `log_status_updates` and `log_artifact_events` flags.
*   **Test 3.3: File Content Logging Configuration:** Verify `log_file_parts` and `max_file_part_size_bytes` behavior.

---

## Group 4: Imperative Authorization & Security Tests (Python)

These tests require a multi-user context and are best handled with imperative Python tests in `tests/integration/apis/`.

*   **Test 4.1: User Data Isolation in List View:** Ensure users only see their own tasks.
*   **Test 4.2: Direct Access Control for Task Details:** Ensure a user cannot `GET` another user's task `.stim` file.
*   **Test 4.3: Privileged Access with `tasks:read:all` Scope:** Verify admin-level query capabilities.

---

## Test Implementation Checklist

### Declarative Tests (YAML)
- [x] Test 1.1: Empty State Retrieval
- [x] Test 1.2: Basic Task Creation and Retrieval
- [x] Test 1.3: Search and Filtering Logic
- [x] Test 1.4: Pagination Logic
- [x] Test 1.5: Task Detail Retrieval as `.stim` File
- [x] Test 2.1: Task Lifecycle Status Updates (Basic)
- [x] Test 2.2: Initial Request Text Extraction
- [ ] Test 2.3: Schema Integrity (Code Review)

### Imperative Tests (Python)
- [ ] Test 3.1: Master `enabled` Flag
- [ ] Test 3.2: Event Type Logging Flags
- [ ] Test 3.3: File Content Logging Configuration
- [ ] Test 4.1: User Data Isolation in List View
- [ ] Test 4.2: Direct Access Control for Task Details
- [ ] Test 4.3: Privileged Access with `tasks:read:all` Scope
