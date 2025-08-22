# A2A Helper Layer Refactoring Checklist

This checklist tracks the progress of refactoring the codebase to use the `common.a2a` helper layer, insulating the application logic from the `a2a-sdk` implementation details.

## Phase 1: High-Priority Refactoring

These files have the most significant and direct interaction with `a2a.types` and will yield the largest improvements in maintainability.

1.  **`src/solace_agent_mesh/agent/protocol/event_handlers.py`**
    - [x] Replace manual `CancelTaskRequest`, `SendMessageRequest` creation with `a2a` helpers.
    - [x] Replace direct access to `a2a_request.root.params.message` with `a2a.get_message_from_send_request`.
    - [ ] Replace manual iteration over `message.parts` with `a2a.get_data_parts_from_message` and `a2a.get_text_from_message`.
    - [ ] Replace manual `JSONRPCResponse` creation for errors with `a2a.create_internal_error_response`.
    - [ ] Refactor `handle_a2a_response` to use `a2a.get_response_result` and `a2a.get_response_error`.
    - [ ] Refactor `handle_a2a_response` to use `a2a.get_data_parts_from_status_update` instead of manual iteration.

2.  **`src/solace_agent_mesh/gateway/base/component.py`**
    - [ ] Replace `JSONRPCResponse.model_validate(payload)` with helpers where applicable.
    - [ ] Replace direct access to `rpc_response.root.result` and `rpc_response.root.error` with `a2a.get_response_result` and `a2a.get_response_error`.
    - [ ] Refactor `submit_a2a_task` to use helpers for creating `SendMessageRequest` and `SendStreamingMessageRequest`.
    - [ ] Refactor `_translate_external_input` to use `a2a` part creation helpers instead of direct instantiation.
    - [ ] Refactor `_process_parsed_a2a_event` to use helpers for creating `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent`.

3.  **`src/solace_agent_mesh/gateway/http_sse/component.py`**
    - [ ] Replace direct creation of `SendStreamingMessageSuccessResponse` and `A2AJSONRPCErrorResponse` with `a2a.create_success_response` and `a2a.create_internal_error_response`.
    - [ ] Refactor `_translate_external_input` to use `a2a.create_text_part` and `a2a.create_file_part` helpers.
    - [ ] Refactor `_infer_visualization_event_details` to operate on validated `a2a.types` objects using helpers, rather than parsing raw dictionaries.

4.  **`src/solace_agent_mesh/core_a2a/service.py`**
    - [ ] Refactor `submit_task` to use a helper for creating `SendMessageRequest`.
    - [ ] Refactor `submit_streaming_task` to use a helper for creating `SendStreamingMessageRequest`.
    - [ ] Refactor `cancel_task` to use a helper for creating `CancelTaskRequest`.

5.  **`src/solace_agent_mesh/agent/sac/component.py`**
    - [ ] Replace manual `TaskStatus` creation with helpers in `finalize_task_success`, `finalize_task_canceled`, and `finalize_task_error`.
    - [ ] Replace direct `DataPart` and `TextPart` creation with `a2a` part creation helpers.
    - [ ] Replace manual `CancelTaskRequest` creation with a helper when propagating cancellations.
    - [ ] Refactor `_format_final_task_status` to use `a2a.create_agent_parts_message`.
    - [ ] Refactor `finalize_task_success` to use `a2a.create_final_task`.

## Phase 2: Secondary Refactoring

These files have fewer direct interactions but should be updated for consistency and completeness.

6.  **`src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`**
    - [ ] Replace manual `Task` and `TaskStatus` creation with `a2a.create_initial_task`.
    - [ ] Replace `SendMessageSuccessResponse` with `a2a.create_success_response`.

7.  **`src/solace_agent_mesh/gateway/http_sse/routers/sessions.py`**
    - [ ] Replace `JSONRPCSuccessResponse` with `a2a.create_success_response`.
    - [ ] Refactor error handling to use `a2a.create_internal_error_response` before raising `HTTPException`.

8.  **`src/solace_agent_mesh/agent/tools/peer_agent_tool.py`**
    - [ ] Refactor `_prepare_a2a_parts` to use `a2a.create_agent_text_message` or similar helpers.

## Phase 3: Final Cleanup and Verification

9.  **Code-wide Search:**
    - [ ] Search the entire codebase for any remaining direct imports from `a2a.types` outside of the `common/a2a` helper layer.
    - [ ] Search for manual dictionary creations that mimic A2A objects (e.g., `{"role": "agent", "parts": [...]}`).

10. **Testing:**
    - [ ] Run the full integration test suite to ensure no regressions were introduced.
    - [ ] Update any tests that were creating A2A objects manually to use the new helpers for test data setup.
