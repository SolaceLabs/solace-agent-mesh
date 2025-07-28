# Implementation Checklist: Declarative Test A2A Agent Server

This checklist corresponds to the `IMPLEMENTATION_PLAN.md` document and should be used to track progress.

## Phase 1: Core Test Agent Implementation

### 1. Create the `DeclarativeAgentExecutor`

- [x] **1.1. File Creation:** Create `tests/integration/test_support/a2a_agent/executor.py`.
- [x] **1.2. Class Definition:**
    - [x] 1.2.1. Define `DeclarativeAgentExecutor` inheriting from `a2a.server.agent_execution.AgentExecutor`.
    - [x] 1.2.2. `__init__` accepts a reference to `TestA2AAgentServer`.
- [x] **1.3. Implement `execute` Method:**
    - [x] 1.3.1. Get `RequestContext` and create `TaskUpdater`.
    - [x] 1.3.2. Extract user message content.
    - [x] 1.3.3. Parse `[test_case_id=...]` and `[responses_json=...]` directives.
    - [x] 1.3.4. Use `test_case_id` to interact with the server's state cache.
    - [x] 1.3.5. **Turn 0 Logic:**
        - [x] 1.3.5.1. Base64-decode `responses_json`.
        - [x] 1.3.5.2. JSON-deserialize into a list of lists.
        - [x] 1.3.5.3. Store the response sequence in the server's state cache.
    - [x] 1.3.6. **Turn-Based Playback:**
        - [x] 1.3.6.1. Determine the current turn index from task history.
        - [x] 1.3.6.2. Retrieve the correct list of event dictionaries for the current turn.
    - [x] 1.3.7. **Event Processing:**
        - [x] 1.3.7.1. Iterate through the event dictionaries for the turn.
        - [x] 1.3.7.2. Dynamically inject `task_id` and `context_id` into each event dictionary.
        - [x] 1.3.7.3. Deserialize the dictionary into the correct Pydantic A2A event model.
        - [x] 1.3.7.4. Enqueue the Pydantic event object into the `event_queue`.
    - [x] 1.3.8. **Finalization:** Close the event queue after enqueuing all events for the turn.
- [ ] **1.4. Implement `cancel` Method:**
    - [ ] 1.4.1. Create a `TaskUpdater` and call `await updater.cancel()`.

### 2. Create the `TestA2AAgentServer`

- [ ] **2.1. File Creation:** Create `tests/integration/infrastructure/a2a_agent_server/server.py`.
- [ ] **2.2. Class Definition:**
    - [ ] 2.2.1. Define the `TestA2AAgentServer` class.
    - [ ] 2.2.2. `__init__` accepts `host`, `port`, and `AgentCard`.
    - [ ] 2.2.3. Initialize instance variables (`_uvicorn_server`, `_server_thread`, `captured_requests`, `_stateful_responses_cache`).
- [ ] **2.3. A2A Application Setup (in `__init__`):**
    - [ ] 2.3.1. Instantiate `DeclarativeAgentExecutor`.
    - [ ] 2.3.2. Instantiate `InMemoryTaskStore`.
    - [ ] 2.3.3. Instantiate `DefaultRequestHandler`.
    - [ ] 2.3.4. Instantiate `A2AFastAPIApplication`.
    - [ ] 2.3.5. Call `.build()` to get the FastAPI app.
    - [ ] 2.3.6. Add FastAPI middleware to capture requests.
- [ ] **2.4. Lifecycle Management:**
    - [ ] 2.4.1. Implement `start()` method to run `uvicorn` in a thread.
    - [ ] 2.4.2. Implement `stop()` method to shut down `uvicorn`.
    - [ ] 2.4.3. Implement `clear_captured_requests()` and `clear_stateful_cache()` methods.

## Phase 2: Test Framework Integration

### 3. Integrate with `conftest.py`

- [ ] **3.1. File Modification:** Open `tests/integration/conftest.py` for editing.
- [ ] **3.2. Create `test_a2a_agent_server` Fixture:**
    - [ ] 3.2.1. Define a session-scoped pytest fixture named `test_a2a_agent_server`.
    - [ ] 3.2.2. Define a static `AgentCard` for the test agent.
    - [ ] 3.2.3. Instantiate `TestA2AAgentServer`.
    - [ ] 3.2.4. Call `server.start()`.
    - [ ] 3.2.5. Implement a readiness check loop.
    - [ ] 3.2.6. `yield` the server instance.
    - [ ] 3.2.7. Call `server.stop()` in the teardown block.
- [ ] **3.3. Create State-Clearing Fixture:**
    - [ ] 3.3.1. Define a function-scoped, `autouse=True` fixture named `clear_a2a_agent_server_state`.
    - [ ] 3.3.2. The fixture takes `test_a2a_agent_server` as an argument.
    - [ ] 3.3.3. After `yield`, call the `clear_captured_requests()` and `clear_stateful_cache()` methods.
- [ ] **3.4. Update `shared_solace_connector` Fixture:**
    - [ ] 3.4.1. Add `test_a2a_agent_server` to the fixture's parameter list.
    - [ ] 3.4.2. Add the `A2AProxyApp` configuration to the `app_infos` list.
    - [ ] 3.4.3. Set the `app_module` to `src.agent.proxies.a2a.app`.
    - [ ] 3.4.4. Configure `proxied_agents` with the name and URL of the test agent server.

## Phase 3: Validation and Testing

### 4. Create Initial Declarative Test Case

- [ ] **4.1. File Creation:** Create the directory `tests/integration/scenarios_declarative/test_data/proxy/`.
- [ ] **4.2. Create YAML Test File:** Create `test_a2a_proxy_simple.yaml` inside the new directory.
- [ ] **4.3. Test Case Definition:**
    - [ ] 4.3.1. Define `test_case_id`.
    - [ ] 4.3.2. Define `description`.
    - [ ] 4.3.3. Define `gateway_input` with `target_agent_name` and a prompt containing the control directives.
    - [ ] 4.3.4. Create and Base64-encode the `responses_json` content.
    - [ ] 4.3.5. Define an empty `llm_interactions` list.
    - [ ] 4.3.6. Define `expected_gateway_output` with assertions for the final response.
    - [ ] 4.3.7. Define an empty `expected_artifacts` list.

### 5. Run and Verify

- [ ] **5.1. Execute** the declarative test runner.
- [ ] **5.2. Confirm** that the new `test_a2a_proxy_simple.yaml` test case is discovered and runs.
- [ ] **5.3. Verify** that the test case passes.
