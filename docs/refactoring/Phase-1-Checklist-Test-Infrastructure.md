# Phase 1 Implementation Checklist: Test Infrastructure

## Section A: Update Memory Monitor
- [x] 1. Update imports in `memory_monitor.py` to use `a2a.types`.
- [x] 2. Update `classes_to_track` in `memory_monitor.py` to reference new `a2a.types` models.

## Section B: Refactor `TestGatewayComponent`
- [x] 3. Migrate all A2A type hints and imports in `gateway_interface/component.py` to `a2a.types`.
- [x] 4. Refactor `submit_a2a_task` to construct and serialize compliant `SendMessageRequest` / `SendStreamingMessageRequest` objects.
- [x] 5. Refactor `_handle_agent_event` to parse incoming payloads using `JSONRPCResponse.model_validate`.
- [x] 6. Implement the new `_parse_a2a_event_from_rpc_result` helper method to parse the `result` field using the `kind` discriminator.
- [x] 7. Update `_handle_agent_event` to use the new `_parse_a2a_event_from_rpc_result` helper.
- [x] 8. Update `_process_parsed_a2a_event` method signature and `isinstance` checks to use new `a2a.types` models.
- [x] 9. Update type hints for `_captured_outputs` queue and its accessor methods.
- [x] 10. Refactor `_resolve_uri_in_payload` and `_resolve_embeds_and_handle_signals` to traverse the new `a2a.types` object structures.

## Section C: Validation and Finalization
- [x] 11. Review and update the `method`-to-schema mapping in `A2AMessageValidator`.
- [x] 12. Update mock payloads in `a2a_validator/test_validator.py` to be compliant with the `a2a.json` schema.
- [ ] 13. Run the full integration test suite and update any failing declarative or programmatic tests to align with the new A2A object structures.
