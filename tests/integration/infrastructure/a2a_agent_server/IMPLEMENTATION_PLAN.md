# Implementation Plan: Declarative Test A2A Agent Server

This document provides a step-by-step plan for implementing the Declarative Test A2A Agent Server, as described in the corresponding design document.

## Phase 1: Core Test Agent Implementation

### 1. Create the `DeclarativeAgentExecutor`

This is the "brain" of the test agent. It will interpret test directives and play back scripted responses.

1.1. **File Creation:** Create a new file: `tests/integration/test_support/a2a_agent/executor.py`.

1.2. **Class Definition:**
    1.2.1. Define a class `DeclarativeAgentExecutor` that inherits from `a2a.server.agent_execution.AgentExecutor`.
    1.2.2. The `__init__` method will accept a reference to the parent `TestA2AAgentServer` instance to access its state cache.

1.3. **Implement `execute` Method:**
    1.3.1. Get the `RequestContext` and create a `TaskUpdater`.
    1.3.2. Extract the user's message content from `context.get_user_input()`.
    1.3.3. Parse the message content to find `[test_case_id=...]` and `[responses_json=...]` directives using regular expressions. If not found, the agent should fail gracefully with an informative error.
    1.3.4. Use the `test_case_id` to interact with the state cache on the `TestA2AAgentServer` instance.
    1.3.5. **Turn 0 Logic:** If the `test_case_id` is not in the cache:
        1.3.5.1. Base64-decode the `responses_json` string.
        1.3.5.2. JSON-deserialize the decoded string into a Python list of lists (the response sequence).
        1.3.5.3. Store this response sequence in the server's state cache, keyed by `test_case_id`.
    1.3.6. **Turn-Based Playback:**
        1.3.6.1. Determine the current turn index. A reliable way is to count the number of `role: "user"` messages in the `task.history`. The first request will have a turn index of 0.
        1.3.6.2. Retrieve the list of A2A event dictionaries for the current turn from the cached response sequence. Handle out-of-bounds errors gracefully.
    1.3.7. **Event Processing:**
        1.3.7.1. Iterate through the list of event dictionaries for the current turn.
        1.3.7.2. For each dictionary, dynamically inject the current `task_id` and `context_id` from the `RequestContext`.
        1.3.7.3. Deserialize the dictionary into the appropriate Pydantic A2A event model (`Task`, `TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`).
        1.3.7.4. Enqueue the resulting Pydantic event object into the `event_queue` using `updater.event_queue.enqueue_event()`.
    1.3.8. **Finalization:** After enqueuing all events for the turn, close the event queue using `updater.event_queue.close()`.

1.4. **Implement `cancel` Method:**
    1.4.1. This method can be simple. It should create a `TaskUpdater` and call `await updater.cancel()`.

### 2. Create the `TestA2AAgentServer`

This class will manage the lifecycle and hosting of the test agent.

2.1. **File Creation:** Create a new file: `tests/integration/infrastructure/a2a_agent_server/server.py`.

2.2. **Class Definition:**
    2.2.1. Define the `TestA2AAgentServer` class.
    2.2.2. The `__init__` method will accept `host`, `port`, and an `AgentCard` object.
    2.2.3. Initialize instance variables: `_uvicorn_server`, `_server_thread`, `captured_requests: List`, and `_stateful_responses_cache: Dict`.

2.3. **A2A Application Setup (in `__init__`):**
    2.3.1. Instantiate the `DeclarativeAgentExecutor`, passing `self` as the reference to the server instance.
    2.3.2. Instantiate `a2a.server.tasks.InMemoryTaskStore`.
    2.3.3. Instantiate `a2a.server.request_handlers.DefaultRequestHandler`, providing the executor and task store.
    2.3.4. Instantiate `a2a.server.apps.A2AFastAPIApplication`, providing the agent card and the request handler.
    2.3.5. Call the `.build()` method on the `A2AFastAPIApplication` instance to get the FastAPI app object.
    2.3.6. **Request Capture:** Add a custom FastAPI middleware to the app that intercepts requests to the RPC endpoint, deserializes the JSON body, and appends it to the `self.captured_requests` list.

2.4. **Lifecycle Management:**
    2.4.1. Implement a `start()` method that creates and starts a `uvicorn.Server` in a new `threading.Thread`. This should mirror the implementation in `TestLLMServer`.
    2.4.2. Implement a `stop()` method to gracefully shut down the uvicorn server and join the thread.
    2.4.3. Implement `clear_captured_requests()` and `clear_stateful_cache()` methods to reset state between tests.

## Phase 2: Test Framework Integration

### 3. Integrate with `conftest.py`

This step makes the test agent available to all integration tests.

3.1. **File Modification:** Edit `tests/integration/conftest.py`.

3.2. **Create `test_a2a_agent_server` Fixture:**
    3.2.1. Define a new `pytest.fixture` with `scope="session"` named `test_a2a_agent_server`.
    3.2.2. Inside the fixture, define a static `AgentCard` for the test agent. The `url` field should be constructed from the host and port (`http://127.0.0.1:8090/a2a`).
    3.2.3. Instantiate `TestA2AAgentServer` with the defined card and a fixed host/port.
    3.2.4. Call `server.start()`.
    3.2.5. Implement a readiness check loop (similar to `test_llm_server`) to wait for the server to be fully started before yielding.
    3.2.6. `yield` the server instance.
    3.2.7. Call `server.stop()` in the teardown part of the fixture (after `yield`).

3.3. **Create State-Clearing Fixture:**
    3.3.1. Define a new `pytest.fixture` with `scope="function"` and `autouse=True` named `clear_a2a_agent_server_state`.
    3.3.2. This fixture will take `test_a2a_agent_server: TestA2AAgentServer` as an argument.
    3.3.3. After its `yield`, it will call `test_a2a_agent_server.clear_captured_requests()` and `test_a2a_agent_server.clear_stateful_cache()`.

3.4. **Update `shared_solace_connector` Fixture:**
    3.4.1. Add `test_a2a_agent_server: TestA2AAgentServer` to the fixture's parameter list.
    3.4.2. In the `app_infos` list, add a new dictionary for the `A2AProxyApp`.
    3.4.3. The `app_module` for this new entry should point to `src.agent.proxies.a2a.app`.
    3.4.4. The `app_config` for the proxy will contain a `proxied_agents` list. This list will contain one entry:
        *   `name`: The name the agent will have on the Solace mesh (e.g., `ProxiedDownstreamAgent`).
        *   `url`: The URL of the running test agent, retrieved from `test_a2a_agent_server.url`.

## Phase 3: Validation and Testing

### 4. Create Initial Declarative Test Case

This first test will validate the end-to-end functionality of the new infrastructure.

4.1. **File Creation:** Create a new directory `tests/integration/scenarios_declarative/test_data/proxy/`.

4.2. **Create YAML Test File:** Inside the new directory, create `test_a2a_proxy_simple.yaml`.

4.3. **Test Case Definition:**
    4.3.1. `test_case_id`: A unique ID (e.g., `a2a_proxy_simple_echo_001`).
    4.3.2. `description`: A clear description of the test's purpose.
    4.3.3. `gateway_input`:
        *   `target_agent_name`: The name of the proxied agent as defined in `conftest.py` (e.g., `ProxiedDownstreamAgent`).
        *   `prompt.parts[0].text`: A string containing the user prompt, the `[test_case_id=...]` directive, and the `[responses_json=...]` directive.
    4.3.4. **`responses_json` Content:**
        *   Create a simple JSON structure for the response. For example: `[[{"kind": "task", "status": {"state": "completed", "message": {"role": "agent", "parts": [{"kind": "text", "text": "Echo from test agent"}]}}}]]`.
        *   Base64-encode this JSON string and place it in the `responses_json` directive.
    4.3.5. `llm_interactions`: This should be an empty list `[]`, as the proxy does not directly interact with an LLM.
    4.3.6. `expected_gateway_output`:
        *   Define a single `final_response` event.
        *   Assert that `task_state` is `completed`.
        *   Assert that `content_parts` contains the text "Echo from test agent".
    4.3.7. `expected_artifacts`: This should be an empty list `[]` for the simple test.

### 5. Run and Verify

5.1. Execute the declarative test runner via `pytest`.
5.2. The runner should discover and execute the new `test_a2a_proxy_simple.yaml` test case.
5.3. Verify that the test passes, confirming that all components (Test A2A Agent, A2A Proxy, Test Gateway) are working together as designed.
