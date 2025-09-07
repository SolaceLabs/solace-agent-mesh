# Implementation Plan: A2A Proxy Integration Testing

This document outlines the step-by-step plan to integrate the A2A proxy component into the existing declarative test harness for comprehensive, end-to-end testing.

### 1. Create Downstream A2A Agent Server Fixture

**Objective:** Establish a test fixture that manages the lifecycle of a downstream A2A agent server, which the proxy will communicate with.

**File to Modify:** `tests/integration/conftest.py`

**Actions:**
1.  Create a new session-scoped pytest fixture named `test_a2a_agent_server_harness`.
2.  This fixture will depend on the `mock_agent_card` fixture to get a valid `AgentCard`.
3.  It will instantiate the `TestA2AAgentServer` from `sam_test_infrastructure.a2a_agent_server.server`.
4.  It will find a free port on the host machine to run the server, preventing port conflicts.
5.  The server will be started in a background thread.
6.  The fixture will perform a readiness check to ensure the server is running before yielding control to the test.
7.  It will `yield` the server instance, making its URL and other properties available to tests.
8.  A `finally` block will be used to guarantee that `server.stop()` is called, ensuring the server process is terminated after the test session.

### 2. Integrate A2A Proxy into the Test Connector

**Objective:** Configure the main `SolaceAiConnector` test fixture to launch and manage the `A2AProxyApp`.

**File to Modify:** `tests/integration/conftest.py`

**Actions:**
1.  Modify the `shared_solace_connector` fixture to accept the new `test_a2a_agent_server_harness` as a dependency.
2.  In the `app_infos` list within the fixture, add a new dictionary entry to define the `A2AProxyApp`.
3.  The `app_config` for the proxy will be configured as follows:
    *   `namespace`: Set to `"test_namespace"` to align with other test components.
    *   `proxied_agents`: Define a list containing one agent. The `name` will be a test alias (e.g., `"TestAgent_Proxied"`), and the `url` will be dynamically set from the `test_a2a_agent_server_harness.url` property.
    *   `artifact_service`: Configure to use the in-memory test service: `{"type": "test_in_memory"}`.
    *   `discovery_interval_seconds`: Set to a low value (e.g., `1`) to ensure rapid discovery during tests.

### 3. Update A2A Message Validator for Proxy

**Objective:** Enhance the `A2AMessageValidator` to automatically intercept and validate messages published by the proxy component.

**File to Modify:** `tests/sam-test-infrastructure/src/sam_test_infrastructure/a2a_validator/validator.py`

**Actions:**
1.  Import `BaseProxyComponent` from `solace_agent_mesh.agent.proxies.base.component`.
2.  In the `activate` method, add a new check: `is_base_proxy_component = isinstance(component_instance, BaseProxyComponent)`.
3.  If the component is a proxy, set `method_name_to_patch` to `_publish_a2a_message`. This will ensure that any message the proxy sends to the Solace mesh is validated against the A2A JSON schema.

### 4. Monkeypatch Proxy's Artifact Service

**Objective:** Ensure the A2A proxy uses the single, shared `TestInMemoryArtifactService` instance so that artifact-related assertions work correctly.

**File to Modify:** `tests/integration/conftest.py`

**Actions:**
1.  Inside the `shared_solace_connector` fixture, use the `session_monkeypatch` object.
2.  Add a new `monkeypatch.setattr` call to intercept the proxy's artifact service initialization.
3.  The target for the patch will be `solace_agent_mesh.agent.proxies.base.component.initialize_artifact_service`.
4.  The replacement will be a `lambda` function that ignores the component argument and returns the shared `test_artifact_service_instance`.

### 5. Enhance Declarative Test Runner

**Objective:** Update the YAML-based test runner to support configuration of the downstream A2A agent's behavior.

**File to Modify:** `tests/integration/scenarios_declarative/test_declarative_runner.py`

**Actions:**
1.  The main test function, `test_declarative_scenario`, will be updated to accept the `test_a2a_agent_server_harness` fixture as an argument.
2.  A new function will be added to `TestA2AAgentServer` (e.g., `prime_responses`) that allows it to be configured with a sequence of responses.
3.  The test runner will look for a new top-level key in the test YAML file, such as `downstream_a2a_agent_responses: List[Dict]`.
4.  If this key is present, the runner will call the `prime_responses` method on the `test_a2a_agent_server_harness` instance, passing the specified response data. This will happen before the main `gateway_input` is executed.

### 6. Create Initial Proxy Test Case

**Objective:** Develop a baseline "happy path" test case in YAML to verify the entire testing setup.

**File to Create:** `tests/integration/scenarios_declarative/test_data/proxy/test_proxy_simple_passthrough.yaml`

**Actions:**
1.  Create a new YAML file for the test scenario.
2.  **`gateway_input`**: Define a simple text message targeting the proxied agent's name (e.g., `TestAgent_Proxied`).
3.  **`downstream_a2a_agent_responses`**: Define a single, simple, successful `Task` object that the `TestA2AAgentServer` will return when it receives the request.
4.  **`expected_gateway_output`**: Define assertions to verify that the final response captured by the `TestGatewayComponent` is identical to the `Task` object defined in the previous step.

This initial test will validate that a request can flow correctly through the entire chain: Test Gateway -> Solace Mesh -> A2A Proxy -> Test A2A Agent Server -> A2A Proxy -> Solace Mesh -> Test Gateway.
