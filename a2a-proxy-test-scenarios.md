# A2A Proxy Test Scenarios

This document outlines the comprehensive list of test scenarios to be implemented for the A2A proxy component. Each scenario is designed to be implemented as a declarative YAML test case.

### 1. Happy Path Scenarios

These tests verify the core functionality of the proxy under normal operating conditions.

- [ ] **Test 1: Simple Request/Response Passthrough**
  - **Objective:** Confirm that a basic, non-streaming request is correctly forwarded and the final response is returned.
  - **Setup:** `gateway_input` sends a simple message.
  - **Downstream Behavior:** `downstream_a2a_agent_responses` contains a single, final `Task` object with a `completed` state.
  - **Assertion:** `expected_gateway_output` verifies the final `Task` is received correctly.

- [ ] **Test 2: Full Streaming Response**
  - **Objective:** Verify that the proxy correctly handles a full streaming conversation with multiple intermediate events.
  - **Setup:** `gateway_input` sends a request. Set `skip_intermediate_events: false` in the YAML.
  - **Downstream Behavior:** `downstream_a2a_agent_responses` contains a sequence of events:
    1.  A `TaskStatusUpdateEvent` with `state: "working"`.
    2.  Another `TaskStatusUpdateEvent` with a text delta.
    3.  A final `Task` object with `state: "completed"`.
  - **Assertion:** `expected_gateway_output` asserts that all three events are received by the test gateway in the correct order and with the correct content.

### 2. Artifact Handling Scenarios

This is a critical feature of the proxy. These tests ensure that artifacts are correctly managed as they pass through the proxy in both directions.

- [ ] **Test 3: Inbound Artifact Resolution**
  - **Objective:** Ensure the proxy correctly resolves an `artifact://` URI from the mesh into raw bytes before forwarding it to the downstream agent.
  - **Setup:**
    - `setup_artifacts` block creates an initial artifact (e.g., `test.txt`) in the test artifact service.
    - `gateway_input` sends a message containing a `FilePart` with the URI `artifact://test_namespace/TestAgent/test.txt`.
  - **Downstream Behavior:** The `TestA2AAgentServer` is primed to return a simple success response.
  - **Assertion:**
    - This will require a new assertion key in our test runner, e.g., `assert_downstream_request`.
    - This assertion will check the request captured by `TestA2AAgentServer` and verify that the `FilePart` it received contains the raw `bytes` of `test.txt`, not the URI.

- [ ] **Test 4: Outbound Artifact Handling**
  - **Objective:** Verify that the proxy intercepts an artifact with raw bytes from the downstream agent, saves it to its own artifact store, and rewrites the response to contain a valid `artifact://` URI.
  - **Setup:** `gateway_input` sends a simple request.
  - **Downstream Behavior:** `downstream_a2a_agent_responses` contains a final `Task` with an `Artifact` that has a `FilePart` containing raw bytes (e.g., base64-encoded).
  - **Assertion:**
    - `expected_gateway_output` asserts that the final `Task` received by the test gateway has the `FilePart` rewritten to an `artifact://` URI.
    - `assert_artifact_state` block verifies that the artifact content was correctly saved to the proxy's `TestInMemoryArtifactService`.

### 3. Error Handling and Resilience Scenarios

These tests ensure the proxy behaves predictably and provides meaningful errors when things go wrong.

- [ ] **Test 5: Downstream Agent Unavailable**
  - **Objective:** Verify the proxy returns a specific error when the downstream agent's URL is unreachable.
  - **Setup:** Configure the proxy in the `shared_solace_connector` fixture to point to a known-bad port (e.g., `http://127.0.0.1:9999`).
  - **Assertion:** `expected_gateway_output` should expect a single `JSONRPCError` event with a message indicating a connection error.

- [ ] **Test 6: Downstream Agent HTTP Error**
  - **Objective:** Verify the proxy correctly translates a downstream HTTP error (e.g., 500 Internal Server Error) into a proper A2A error response.
  - **Setup:** `gateway_input` sends a request.
  - **Downstream Behavior:** This requires a new feature in `TestA2AAgentServer` to prime an HTTP error response. The `downstream_a2a_agent_responses` would specify `status_code: 500`.
  - **Assertion:** `expected_gateway_output` expects a `JSONRPCError` that contains the HTTP 500 status and error message.

- [ ] **Test 7: Downstream Agent A2A Error**
  - **Objective:** Verify the proxy correctly forwards a valid, but unsuccessful, A2A JSON-RPC error response from the downstream agent.
  - **Setup:** `gateway_input` sends a request.
  - **Downstream Behavior:** `downstream_a2a_agent_responses` contains a single JSON-RPC response with an `error` field instead of a `result` field (e.g., a `TaskNotFoundError`).
  - **Assertion:** `expected_gateway_output` asserts that the exact same `JSONRPCError` object is received by the test gateway.

### 4. Advanced Feature Scenarios

These tests cover more complex interactions and configurations.

- [ ] **Test 8: Request Cancellation**
  - **Objective:** Ensure that a cancellation request from the mesh is correctly propagated to the downstream agent.
  - **Setup:**
    - This requires a new test runner feature. We can add a key like `gateway_actions_after_input` to the YAML.
    - The test would send a `gateway_input`, and then the `gateway_actions_after_input` block would instruct the `TestGatewayComponent` to call its `cancel_task` method.
  - **Downstream Behavior:** The `TestA2AAgentServer` needs a way to confirm it received a cancellation. We can check its captured requests for the `tasks/cancel` method call.
  - **Assertion:** `expected_gateway_output` asserts the final `Task` has a state of `canceled`.

- [ ] **Test 9: Authentication Passthrough**
  - **Objective:** Verify that authentication tokens configured on the proxy are correctly passed as headers to the downstream agent.
  - **Setup:**
    - In `conftest.py`, modify the proxy's `app_config` to include an `authentication` block for the proxied agent.
    - `gateway_input` sends a simple request.
  - **Assertion:** Use the `assert_downstream_request` key (from Test 3) to inspect the request received by `TestA2AAgentServer` and verify that the `Authorization: Bearer ...` header is present and correct.

- [ ] **Test 10: Request Timeout**
  - **Objective:** Ensure the proxy respects the configured request timeout.
  - **Setup:**
    - In `conftest.py`, configure the proxied agent with a very short timeout (e.g., `request_timeout_seconds: 1`).
    - This requires a new feature in `TestA2AAgentServer` to add a delay to its response. The `downstream_a2a_agent_responses` would specify `delay_seconds: 2`.
  - **Assertion:** `expected_gateway_output` should expect a `JSONRPCError` indicating a client-side timeout.
