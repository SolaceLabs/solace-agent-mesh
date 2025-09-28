# Implementation Checklist: Declarative HTTP API Testing

This checklist tracks the implementation of the declarative HTTP API testing feature, corresponding to the steps outlined in the implementation plan.

## Part 1: Test Harness and Fixture Setup

- [x] **Step 1: Create Database Fixtures**
  - [x] Create `test_db_engine` session-scoped fixture in `tests/integration/conftest.py`.
  - [x] Create `clean_db_fixture` function-scoped, `autouse` fixture in `tests/integration/conftest.py`.

- [x] **Step 2: Integrate `WebUIBackendApp` into Test Harness**
  - [x] Modify `shared_solace_connector` in `tests/integration/conftest.py`.
  - [x] Add `WebUIBackendApp` definition to the `app_infos` list with correct configuration (namespace, DB URL, task logging).

- [x] **Step 3: Create API Client Fixture**
  - [x] Create `webui_api_client` function-scoped fixture in `tests/integration/conftest.py`.

## Part 2: Declarative Test Runner Implementation

- [x] **Step 4: Update Test Runner Signature**
  - [x] Modify `test_declarative_scenario` in `test_declarative_runner.py` to accept the `webui_api_client` fixture.

- [x] **Step 5: Implement HTTP Request Initiation**
  - [x] Create `_execute_http_and_collect_events` helper function in `test_declarative_runner.py`.
  - [x] Update `test_declarative_scenario` to handle `http_request_input` and `gateway_input` logic.

- [x] **Step 6: Implement HTTP Response Assertions**
  - [x] Create `_assert_http_responses` helper function in `test_declarative_runner.py`.

- [ ] **Step 7: Integrate Assertions into Runner**
  - [ ] Add a call to `_assert_http_responses` at the end of the `test_declarative_scenario` function.

## Part 3: Create Initial Test Case and Cleanup

- [ ] **Step 8: Create a "Smoke Test" Declarative Scenario**
  - [ ] Create `tests/integration/scenarios_declarative/test_data/api/test_get_empty_tasks.yaml`.

- [ ] **Step 9: Create a Full End-to-End Declarative Test**
  - [ ] Create `tests/integration/scenarios_declarative/test_data/api/test_create_and_get_task.yaml`.

- [ ] **Step 10: Remove Old API Test Framework**
  - [ ] Delete `tests/integration/apis/conftest.py`.
  - [ ] Delete `tests/integration/apis/infrastructure/` directory.
  - [ ] Delete `tests/integration/apis/persistence/` directory.
  - [ ] Delete `tests/integration/apis/test_feedback_api.py`.
  - [ ] Clean up `tests/integration/apis/__init__.py`.
