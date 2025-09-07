# A2A Proxy Integration Test Implementation Checklist

1.  [x] **Create Downstream A2A Agent Server Fixture**: Implement the `test_a2a_agent_server_harness` fixture in `tests/integration/conftest.py` to manage the lifecycle of the `TestA2AAgentServer`.

2.  [ ] **Integrate A2A Proxy into Test Connector**: Modify the `shared_solace_connector` fixture in `tests/integration/conftest.py` to launch the `A2AProxyApp`, configuring it to proxy requests to the `test_a2a_agent_server_harness`.

3.  [ ] **Update A2A Message Validator**: In `tests/sam-test-infrastructure/src/sam_test_infrastructure/a2a_validator/validator.py`, update `A2AMessageValidator.activate` to recognize and patch `BaseProxyComponent` instances, enabling automatic message validation.

4.  [ ] **Monkeypatch Proxy's Artifact Service**: In the `shared_solace_connector` fixture in `tests/integration/conftest.py`, add a `monkeypatch.setattr` call to ensure the proxy's `initialize_artifact_service` function returns the shared `test_artifact_service_instance`.

5.  [ ] **Enhance Declarative Test Runner**:
    - In `tests/integration/scenarios_declarative/test_declarative_runner.py`, update the `test_declarative_scenario` function to accept the `test_a2a_agent_server_harness` fixture.
    - Add logic to the test runner to parse a new `downstream_a2a_agent_responses` key from the test YAML and use it to configure the `TestA2AAgentServer`'s behavior for the scenario.

6.  [ ] **Create Initial Proxy Test Case**: Create the first declarative test case at `tests/integration/scenarios_declarative/test_data/proxy/test_proxy_simple_passthrough.yaml` to verify the end-to-end test setup with a simple request/response flow.
