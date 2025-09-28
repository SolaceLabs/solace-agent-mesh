# Declarative HTTP API Testing - Design Document

This document outlines the technical design for integrating HTTP API testing capabilities into the declarative (YAML-based) integration test framework.

## 1. Overview

The goal is to create a unified, high-fidelity testing environment where a single declarative test case can validate the entire system flow, from an initial HTTP request to the Web UI backend, through the event mesh to the agents, and back out through subsequent API calls for state verification. This design eliminates the need for a separate, heavily mocked API testing suite.

## 2. Test Harness Integration Design

The core of this change involves integrating the `WebUIBackendApp` into the main test harness, which currently only runs agent applications and a test gateway.

### 2.1. `WebUIBackendApp` Integration

The `shared_solace_connector` fixture in `tests/integration/conftest.py` will be modified to include the `WebUIBackendApp` in its list of applications to run.

-   **Application Definition**: A new entry will be added to the `app_infos` list for the `WebUIBackendApp`.
-   **Configuration**:
    -   It will be configured to use the same `namespace` as the other test components to ensure it communicates on the same event mesh.
    -   It will be configured to use a real, test-specific database via a `database_url` in its `session_service` configuration. This is critical for testing persistence features like task and session logging.
    -   It will be set to `dev_mode: True` to connect to the in-memory `DevBroker`.

### 2.2. Database Management

To support persistence features and ensure test isolation, a dedicated test database will be managed within the integration test environment.

-   **Database Instance**: A single temporary SQLite database will be created for the entire test session.
-   **Test Isolation**: A new `autouse`, function-scoped fixture will be created in `tests/integration/conftest.py`. This fixture will be responsible for deleting all data from the relevant tables (`tasks`, `task_events`, `feedback`, `sessions`, `chat_messages`) before each test run, ensuring a clean state without the overhead of recreating the database and schema for every test.

## 3. Fixture Design

New pytest fixtures will be created in `tests/integration/conftest.py` to provide the necessary components to the test runner.

### 3.1. `webui_api_client` Fixture

This fixture will provide a `fastapi.testclient.TestClient` instance for making HTTP requests to the running `WebUIBackendApp`.

-   **Dependency**: It will depend on the `shared_solace_connector` fixture to ensure all applications are running.
-   **Logic**:
    1.  It will retrieve the running `WebUIBackendApp` instance from the `SolaceAiConnector`.
    2.  It will access the `WebUIBackendComponent` within that app.
    3.  It will get the underlying FastAPI `app` object from the component.
    4.  It will instantiate and `yield` a `TestClient` wrapped around the FastAPI `app`.

### 3.2. Database Fixtures

-   **`test_db_engine` Fixture**: A session-scoped fixture that creates a temporary SQLite database and the corresponding SQLAlchemy engine. It will also be responsible for creating the database schema (all tables) once per test session.
-   **`clean_db_fixture` Fixture**: A function-scoped, `autouse` fixture that uses the `test_db_engine` to connect to the database and delete all data from tables between tests, ensuring test isolation.

## 4. YAML Schema Design

The declarative test case YAML schema will be extended with new top-level keys.

### 4.1. `http_request_input` Block

This block will serve as an alternative to the existing `gateway_input` for initiating a test. It will define an HTTP request to be made to the Web UI backend.

-   **Structure**:
    ```yaml
    http_request_input:
      method: "POST"  # Required. e.g., GET, POST, PATCH, DELETE
      path: "/api/v1/message:stream" # Required. The API endpoint path.
      query_params: # Optional.
        key: "value"
      json_body: # Optional. For POST/PATCH requests with a JSON body.
        # ... json payload ...
      # 'files' support can be added in a future iteration if needed.
    ```
-   **Behavior**: The test runner will use the `webui_api_client` to make this request. The response from this initial request (e.g., a `task_id`) will be captured and used for subsequent event collection, similar to how `gateway_input` works today.

### 4.2. `expected_http_responses` Block

This block will be processed at the end of a test scenario to perform final state assertions via the API.

-   **Structure**: A list of assertion blocks.
    ```yaml
    expected_http_responses:
      - description: "A human-readable description of this assertion."
        request:
          method: "GET"
          path: "/api/v1/tasks"
          query_params:
            search: "my task"
        expected_status_code: 200
        expected_json_body_matches: # Optional. Reuses existing subset matching logic.
          - id: "task-123"
            status: "completed"
        expected_body_is_empty_list: false # Optional. For simple empty list checks.
        expected_body_is_empty_dict: false # Optional. For simple empty object checks.
    ```
-   **Behavior**: The test runner will iterate through this list, making each specified HTTP request and asserting the response status code and body against the expectations.

## 5. Declarative Test Runner Design

The `test_declarative_runner.py` will be modified to orchestrate the new testing flow.

### 5.1. Test Initiation Logic

The `test_declarative_scenario` function will be updated:
1.  It will now accept the `webui_api_client` fixture.
2.  It will check for the presence of `http_request_input` in the YAML file.
3.  If `http_request_input` exists, it will use the `webui_api_client` to make the specified HTTP request. The `task_id` will be extracted from the JSON response of this call.
4.  If `gateway_input` exists, it will use the existing `TestGatewayComponent` logic.
5.  The test will fail if both or neither input block is present.

### 5.2. HTTP Assertion Logic

A new function, `_assert_http_responses`, will be added to the runner.
1.  This function will be called at the end of `test_declarative_scenario`, after all other assertions have passed.
2.  It will check for the `expected_http_responses` block in the YAML.
3.  If the block exists, it will loop through each entry:
    -   Make the specified HTTP request using the `webui_api_client`.
    -   Assert that the response's status code matches `expected_status_code`.
    -   If `expected_json_body_matches` is present, use the existing `_assert_dict_subset` logic to validate the JSON response body.
    -   Handle other simple assertions like `expected_body_is_empty_list`.
