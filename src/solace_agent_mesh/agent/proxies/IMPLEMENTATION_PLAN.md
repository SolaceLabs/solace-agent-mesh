# A2A Agent Proxy: Refactoring Implementation Plan

## 1. Objective

The goal of this refactoring is to modernize the A2A Agent Proxy by removing the legacy protocol translation layer. The proxy will be updated to natively handle the modern, spec-compliant A2A protocol, using the new `common/a2a` abstraction layer for all interactions. This will result in a cleaner, more maintainable, and more efficient implementation that acts as a pure transport bridge between the Solace Event Mesh and downstream A2A-over-HTTPS agents.

---

## 2. File Structure Changes

1.  **Confirm Deletion:** Ensure the file `src/solace_agent_mesh/agent/proxies/a2a/translation.py` has been deleted, as it contains the logic we are replacing.
2.  **Add Documentation:** This implementation plan and the `DESIGN.md` document will be added to the `src/solace_agent_mesh/agent/proxies/` directory to document the new architecture.

---

## 3. Dependency Management

1.  **Update `pyproject.toml`:** Ensure the `a2a-sdk` is included as a project dependency. It is required by the `A2AProxyComponent` to communicate with downstream agents.

    *   **Action:** Add `"a2a-sdk[http-server]>=0.3.1"` to the `dependencies` list.

---

## 4. Refactor `BaseProxyComponent`

The majority of the changes will be in `src/solace_agent_mesh/agent/proxies/base/component.py` to align it with the modern A2A protocol.

1.  **Update Imports:**
    *   **Action:** Remove the imports from `..a2a.translation`.
    *   **Action:** Add imports from the new `common/a2a` helper modules (`protocol`, `message`) and `pydantic.TypeAdapter`.

2.  **Refactor `_handle_a2a_request`:**
    *   **Action:** Replace the call to `translate_sam_to_modern_request` with direct validation of the incoming Solace message payload using `TypeAdapter(A2ARequest).validate_python(payload)`.
    *   **Action:** Use the `a2a.get_request_id` and `a2a.get_message_from_send_request` helpers to extract data from the now-validated modern request object.
    *   **Action:** Integrate a call to a new helper method, `_resolve_inbound_artifacts`, to handle `artifact://` URIs before forwarding the request.

3.  **Create `_resolve_inbound_artifacts` Method:**
    *   **Action:** Add a new private async method to `BaseProxyComponent`.
    *   **Logic:** This method will inspect the incoming `A2ARequest`, find any `FilePart`s with `artifact://` URIs, and use the `a2a.resolve_file_part_uri` helper to load the artifact bytes from the shared `ArtifactService`. It will then return a new `Message` object with the URI-based parts replaced by byte-based parts.

4.  **Refactor Publishing Methods:**
    *   **Files to change:** `_publish_status_update`, `_publish_final_response`, `_publish_artifact_update`, `_publish_error_response`.
    *   **Action:** Remove all calls to `translate_modern_to_sam_response`.
    *   **Action:** Use the `a2a.create_success_response` and `a2a.create_error_response` helpers. These helpers take the modern Pydantic models (`Task`, `TaskStatusUpdateEvent`, `InternalError`, etc.) and correctly wrap them in a `JSONRPCResponse` envelope.
    *   **Action:** The result of calling these helpers can be passed directly to `.model_dump(exclude_none=True)` to generate the payload for Solace.

5.  **Refactor Discovery Methods:**
    *   **Files to change:** `_discover_and_publish_agents`, `_publish_discovered_cards`.
    *   **Action:** Remove all calls to `translate_modern_card_to_sam_card`.
    *   **Action:** The logic will now directly take the `AgentCard` object from the registry, update its `url` field to point to the proxy's Solace topic, and publish the result of `.model_dump(exclude_none=True)` to the discovery topic.

---

## 5. Refactor `A2AProxyComponent`

The changes in `src/solace_agent_mesh/agent/proxies/a2a/component.py` are minor and focus on aligning artifact handling with the base class changes.

1.  **Update `_process_downstream_response`:**
    *   **Action:** The `produced_artifacts` parameter is no longer needed in calls to `_publish_final_response`, as this information is now contained within the `Task` object's metadata. Remove this parameter from the method calls.

2.  **Update `_handle_outbound_artifacts`:**
    *   **Action:** This method correctly saves byte-based artifacts from the downstream agent. To ensure consistency, we will refactor it to use `a2a.create_file_part_from_uri` when creating the new reference-based `FilePart` after saving the artifact. This aligns it with the patterns used in the new `common/a2a` abstraction layer.

---

## 6. Update Test Infrastructure

To support testing the refactored proxy, the test infrastructure in `tests/integration/conftest.py` needs to be updated.

1.  **Add `test_a2a_agent_server` Fixture:**
    *   **Action:** Add the new session-scoped `test_a2a_agent_server` fixture. This fixture will start and stop the `TestA2AAgentServer`, which acts as a controllable downstream agent for integration tests.

2.  **Add `clear_a2a_agent_server_state` Fixture:**
    *   **Action:** Add the new function-scoped, `autouse` fixture `clear_a2a_agent_server_state`. This will ensure that the test agent server's state (captured requests, etc.) is cleared between tests, guaranteeing test isolation.

3.  **Update `shared_solace_connector` Fixture:**
    *   **Action:** Add the `TestA2AProxyApp` to the list of applications started by the `shared_solace_connector`. This ensures the proxy is running and configured correctly for all integration tests.
    *   **Action:** Pass the `test_a2a_agent_server` fixture to the `shared_solace_connector` so it can be used to configure the proxy's target URL.

---

## 7. Validation

After implementing these changes, the `test_a2a_proxy_simple.yaml` declarative test case should pass. This test validates the complete end-to-end data path:
1.  A client sends a request to the proxy's Solace topic.
2.  The proxy forwards the request to the `TestA2AAgentServer`.
3.  The `TestA2AAgentServer` returns a scripted response.
4.  The proxy relays the response back to the client on Solace.

Passing this test will confirm that the refactored proxy is functioning correctly as a transport bridge without the legacy translation layer.
