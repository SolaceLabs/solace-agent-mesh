# Implementation Plan: Declarative HTTP API Testing

This document details the step-by-step implementation of the design for integrating HTTP API testing into the declarative test framework.

## Part 1: Test Harness and Fixture Setup (`tests/integration/conftest.py`)

### 1. Create Database Fixtures

-   **File:** `tests/integration/conftest.py`
-   **Action:**
    -   Create a new session-scoped fixture named `test_db_engine`. This fixture will:
        -   Create a temporary SQLite database file.
        -   Create a SQLAlchemy engine for it.
        -   Run Alembic migrations to create the schema (`command.upgrade(cfg, "head")`).
        -   Yield the engine.
    -   Create a new function-scoped, `autouse=True` fixture named `clean_db_fixture`. This fixture will:
        -   Depend on `test_db_engine`.
        -   Before each test, delete all data from the tables: `tasks`, `task_events`, `feedback`, `sessions`, and `chat_messages`.

### 2. Integrate `WebUIBackendApp` into Test Harness

-   **File:** `tests/integration/conftest.py`
-   **Action:**
    -   Modify the `shared_solace_connector` fixture.
    -   Add a new dictionary to the `app_infos` list to define the `WebUIBackendApp`. This configuration must include:
        -   `name`: "WebUIBackendApp"
        -   `app_module`: "solace_agent_mesh.gateway.http_sse.app"
        -   `broker`: `{"dev_mode": True}`
        -   `app_config`: A dictionary containing:
            -   `namespace`: "test_namespace"
            -   `gateway_id`: "TestWebUIGateway_01"
            -   `session_secret_key`: "a_secure_test_secret_key"
            -   `session_service`: A dictionary with `type: "sql"` and `database_url` pointing to the test database created in Step 1.
            -   `task_logging`: A dictionary with `enabled: True`.

### 3. Create API Client Fixture

-   **File:** `tests/integration/conftest.py`
-   **Action:**
    -   Create a new function-scoped fixture named `webui_api_client`.
    -   This fixture will depend on `shared_solace_connector`.
    -   It will retrieve the running "WebUIBackendApp" instance from the connector.
    -   It will access the `WebUIBackendComponent` within the app.
    -   It will get the underlying FastAPI `app` object from the component.
    -   It will instantiate and `yield` a `fastapi.testclient.TestClient` wrapped around this FastAPI app.

## Part 2: Declarative Test Runner Implementation (`tests/integration/scenarios_declarative/test_declarative_runner.py`)

### 4. Update Test Runner Signature

-   **File:** `tests/integration/scenarios_declarative/test_declarative_runner.py`
-   **Action:** Modify the `test_declarative_scenario` function signature to accept the new `webui_api_client` fixture.

### 5. Implement HTTP Request Initiation

-   **File:** `tests/integration/scenarios_declarative/test_declarative_runner.py`
-   **Action:**
    -   Create a new async helper function, `_execute_http_and_collect_events`.
    -   This function will take the `webui_api_client` and the `http_request_input` YAML block as arguments.
    -   It will use the client to make the specified HTTP request (`method`, `path`, `json_body`, etc.).
    -   It will parse the JSON response to extract the `task_id`.
    -   It will then use the existing `get_all_task_events` helper to collect all subsequent events for that `task_id` from the `test_gateway_app_instance`.
    -   Modify the main `test_declarative_scenario` function to check for `http_request_input` vs. `gateway_input` and call the appropriate execution helper (`_execute_http_and_collect_events` or the existing `_execute_gateway_and_collect_events`). The test should fail if both or neither are present (unless `expected_http_responses` is used alone).

### 6. Implement HTTP Response Assertions

-   **File:** `tests/integration/scenarios_declarative/test_declarative_runner.py`
-   **Action:**
    -   Create a new async helper function, `_assert_http_responses`.
    -   This function will take the `webui_api_client` and the `expected_http_responses` YAML block.
    -   It will loop through each entry in the block. For each entry, it will:
        -   Make the specified HTTP request using the client.
        -   Assert that the response status code matches `expected_status_code`.
        -   If `expected_json_body_matches` is present, parse the response JSON and use the existing `_assert_dict_subset` helper for validation.
        -   Add logic to handle new simple assertions like `expected_body_is_empty_list`.

### 7. Integrate Assertions into Runner

-   **File:** `tests/integration/scenarios_declarative/test_declarative_runner.py`
-   **Action:** In the `test_declarative_scenario` function, add a call to the new `_assert_http_responses` function at the end of the `try` block, after all other assertions have passed.

## Part 3: Create Initial Test Case and Cleanup

### 8. Create a "Smoke Test" Declarative Scenario

-   **File:** `tests/integration/scenarios_declarative/test_data/api/test_get_empty_tasks.yaml` (new file)
-   **Action:** Create a simple YAML test case to validate the new functionality. This test will:
    -   Have no `gateway_input` or `http_request_input`.
    -   Contain an `expected_http_responses` block that makes a `GET` request to `/api/v1/tasks`.
    -   Assert that the `expected_status_code` is `200`.
    -   Assert that `expected_body_is_empty_list` is `true`.

### 9. Create a Full End-to-End Declarative Test

-   **File:** `tests/integration/scenarios_declarative/test_data/api/test_create_and_get_task.yaml` (new file)
-   **Action:** Create a YAML test that uses the full new flow:
    -   Use `http_request_input` to create a task via `POST /api/v1/message:stream`.
    -   Include `llm_interactions` to define the agent's behavior.
    -   Include `expected_gateway_output` to assert on the A2A events.
    -   Include `expected_http_responses` to make a `GET` request to `/api/v1/tasks` and assert that the newly created task appears in the list.

### 10. Remove Old API Test Framework

-   **Action:** Once the new framework is validated, the old, isolated API testing infrastructure can be removed. This involves deleting the following files and directories:
    -   `tests/integration/apis/conftest.py`
    -   `tests/integration/apis/infrastructure/` (entire directory)
    -   `tests/integration/apis/persistence/` (entire directory)
    -   `tests/integration/apis/test_feedback_api.py`
-   The `tests/integration/apis/__init__.py` file should be cleared or updated to reflect the removal of the sub-modules.
