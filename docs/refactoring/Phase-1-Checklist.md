# A2A SDK Migration: Phase 1 Implementation Checklist

This checklist tracks the development tasks for Phase 1.

### Section A: Schema and Data Model Setup

- [x] 1. Create directory: `src/solace_agent_mesh/common/a2a_spec/schemas/`.
- [x] 2. Create `tool_invocation_start.json` schema file.
- [x] 3. Create `llm_invocation.json` schema file.
- [x] 4. Create `agent_progress_update.json` schema file.
- [x] 5. Create `artifact_creation_progress.json` schema file.
- [x] 6. Create file: `src/solace_agent_mesh/common/data_parts.py`.
- [x] 7. Add Pydantic models to `data_parts.py` corresponding to the new JSON schemas.

### Section B: Refactor Agent Request Handling (`event_handlers.py`)

- [x] 8. Replace legacy `...common.types` imports with `a2a.types`.
- [x] 9. In `handle_a2a_request`, replace `A2ARequest.validate_python` with `A2ARequest.model_validate`.
- [x] 10. In `handle_a2a_request`, update `isinstance` checks to use `a2a_request.root`.
- [x] 11. In `handle_a2a_request`, implement server-side `taskId` generation for new tasks.
- [x] 12. In `handle_a2a_request`, extract `contextId` and `messageId` from the incoming message.
- [x] 13. In `handle_a2a_request`, update the `a2a_context` dictionary with the new IDs.
- [x] 14. In `handle_a2a_request`, update `CancelTaskRequest` handling to get the `taskId` from `request.root.params.id`.

### Section C: Refactor Status Update Generation (`callbacks.py`)

- [x] 15. Replace legacy type imports with `a2a.types` and the new `data_parts` models.
- [x] 16. Refactor `notify_tool_invocation_start_callback` to create and publish a `TaskStatusUpdateEvent` containing a `DataPart` with `ToolInvocationStartData`.
- [x] 17. Refactor `solace_llm_invocation_callback` to use a `DataPart` with `LlmInvocationData`.
- [x] 18. Refactor progress update logic in `process_artifact_blocks_callback` to use a `DataPart` with `ArtifactCreationProgressData`.

### Section D: Refactor Peer Agent Delegation

- [x] 19. In `peer_agent_tool.py`, modify `run_async` to generate a unique `messageId` for each peer request.
- [x] 20. In `peer_agent_tool.py`, modify `run_async` to propagate the `contextId` from the parent task to the peer request.
- [x] 21. In `SamAgentComponent.submit_a2a_task`, modify the method signature and logic to accept and process a modern `a2a.types.SendMessageRequest`.
- [x] 22. In `event_handlers.handle_a2a_response`, update the correlation logic to handle the server-generated `taskId` from peer agents.

### Section E: Update Test Infrastructure

- [x] 23. In `TestGatewayComponent`, refactor `submit_a2a_task` to instantiate and serialize `a2a.types.SendMessageRequest`.
- [x] 24. In `TestGatewayComponent`, refactor response handling logic to parse incoming data into `a2a.types.JSONRPCResponse`.
- [ ] 25. Update assertions in integration tests to check for the new `DataPart`-based status update structures.
- [ ] 26. Update all mock A2A message fixtures in `tests/integration/conftest.py` to conform to the new `a2a.json` schema.

### Section F: Final Validation

- [ ] 27. Run the full integration test suite.
- [ ] 28. Debug and fix any failing tests, using the `A2AMessageValidator` to identify protocol mismatches.
- [ ] 29. Confirm that all tests within the scope of Phase 1 are passing.
