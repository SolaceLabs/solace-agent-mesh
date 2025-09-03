# A2A Proxy Refactoring: Implementation Checklist

## Phase 1: Setup and Dependencies

- [x] 1. **Confirm File Deletion:** Verify that `src/solace_agent_mesh/agent/proxies/a2a/translation.py` is deleted.
- [x] 2. **Add Documentation:** Add `DESIGN.md` and `IMPLEMENTATION_PLAN.md` to the `src/solace_agent_mesh/agent/proxies/` directory.
- [x] 3. **Update Dependencies:** Add `"a2a-sdk[http-server]>=0.3.1"` to `pyproject.toml`.

## Phase 2: Refactor `BaseProxyComponent`

*File: `src/solace_agent_mesh/agent/proxies/base/component.py`*

- [x] 4. **Update Imports:** Remove `translation` imports and add `common.a2a` helpers and `pydantic.TypeAdapter`.
- [x] 5. **Refactor `_handle_a2a_request`:**
    - [x] 5a. Replace translation with `TypeAdapter(A2ARequest).validate_python(payload)`.
    - [x] 5b. Use `a2a.get_request_id` and `a2a.get_message_from_send_request` helpers.
    - [x] 5c. Add a call to the new `_resolve_inbound_artifacts` method.
- [x] 6. **Create `_resolve_inbound_artifacts` Method:** Implement the new private method to resolve `artifact://` URIs into bytes using `a2a.resolve_file_part_uri`.
- [x] 7. **Refactor Publishing Methods:**
    - [x] 7a. In `_publish_status_update`, `_publish_final_response`, and `_publish_artifact_update`, replace translation logic with `a2a.create_success_response`.
    - [x] 7b. In `_publish_error_response`, replace translation logic with `a2a.create_error_response`.
- [x] 8. **Refactor Discovery Methods:** In `_discover_and_publish_agents` and `_publish_discovered_cards`, remove calls to `translate_modern_card_to_sam_card` and publish the modern card directly.

## Phase 3: Refactor `A2AProxyComponent`

*File: `src/solace_agent_mesh/agent/proxies/a2a/component.py`*

- [x] 9. **Update `_process_downstream_response`:** Remove the `produced_artifacts` parameter from all calls to `_publish_final_response`.
- [x] 10. **Update `_handle_outbound_artifacts`:** Refactor the URI creation to use `a2a.create_file_part_from_uri` for consistency after saving an artifact.

## Phase 4: Update Test Infrastructure

*File: `tests/integration/conftest.py`*

- [ ] 11. **Add `test_a2a_agent_server` Fixture:** Add the new session-scoped fixture to manage the test A2A server.
- [ ] 12. **Add `clear_a2a_agent_server_state` Fixture:** Add the new `autouse` fixture to clear the test server's state between tests.
- [ ] 13. **Update `shared_solace_connector` Fixture:**
    - [ ] 13a. Add the `TestA2AProxyApp` to the list of applications to be started.
    - [ ] 13b. Inject the `test_a2a_agent_server` fixture and use its URL to configure the `TestA2AProxyApp`.

## Phase 5: Validation

- [ ] 14. **Run Tests:** Execute the integration tests and confirm that `test_a2a_proxy_simple.yaml` passes, validating the end-to-end flow.
