# Phase 1 Implementation Plan: Test Infrastructure

This document provides a step-by-step guide for executing the refactoring of the `sam-test-infrastructure` library as outlined in the corresponding design document.

---

## Section A: Update Memory Monitor

The `MemoryMonitor` tracks specific A2A object types. We will start by updating these references.

1.  **Update Imports in `memory_monitor.py`**:
    -   Locate the line `from solace_agent_mesh.common.types import Task, TaskStatusUpdateEvent`.
    -   Replace it with `from a2a.types import Task, TaskStatusUpdateEvent`.

2.  **Update Tracked Classes in `memory_monitor.py`**:
    -   In the `__init__` method, find the `self.classes_to_track` list.
    -   Ensure the list correctly references the newly imported `Task` and `TaskStatusUpdateEvent` from `a2a.types`. The names are the same, so this step is primarily to confirm the import change was sufficient.

---

## Section B: Refactor `TestGatewayComponent`

This is the core of the refactoring effort. We will proceed method by method to ensure a controlled migration.

3.  **Migrate Type System in `gateway_interface/component.py`**:
    -   Remove all imports from `solace_agent_mesh.common.types` related to A2A objects (e.g., `A2APart`, `TextPart`, `Task`, `TaskStatusUpdateEvent`, etc.).
    -   Add imports for the corresponding models from `a2a.types`. Refer to `docs/refactoring/A2A-Type-Migration-Map.md` for the correct mappings.
    -   Update all type hints in method signatures and variable annotations throughout the file to use the new `a2a.types` models. For example, change `List[A2APart]` to `list[A2APart]` (from `a2a.types`).

4.  **Refactor Task Submission Logic in `submit_a2a_task`**:
    -   Modify the method to construct an `a2a.types.Message` object.
    -   Generate a `messageId` using `uuid.uuid4().hex`.
    -   Use the `a2a_session_id` from `external_request_context` as the `contextId`.
    -   Set the required `kind` field to `"message"`.
    -   Wrap the `a2a.types.Message` object in `a2a.types.MessageSendParams`.
    -   Conditionally create either a `a2a.types.SendMessageRequest` or `a2a.types.SendStreamingMessageRequest` using the `MessageSendParams`. The `id` of this request should be the `task_id`.
    -   Update the call to `publish_a2a_message` to serialize the final request object using `.model_dump(by_alias=True, exclude_none=True)`.

5.  **Refactor Response Handling in `_handle_agent_event`**:
    -   In the `try` block, change the payload parsing from a manual dictionary check to `JSONRPCResponse.model_validate(payload)`.
    -   Update the logic to access the `result` or `error` via `rpc_response.root.result` and `rpc_response.root.error`.
    -   Replace the direct call to `_process_parsed_a2a_event` with a call to the new `_parse_a2a_event_from_rpc_result` helper (to be created in the next step).

6.  **Implement New Event Parsing Logic in `_parse_a2a_event_from_rpc_result`**:
    -   Create this new private helper method. It will accept `rpc_result: Dict` and `expected_task_id: Optional[str]` as arguments.
    -   Inside the method, use the `kind` field from `rpc_result` to determine which `a2a.types` model to use for parsing (`Task`, `TaskStatusUpdateEvent`, or `TaskArtifactUpdateEvent`).
    -   Extract the task ID from the payload (`id` for `Task`, `taskId` for events) and validate it against `expected_task_id`.
    -   Return the validated Pydantic object on success or `None` on failure.

7.  **Update `_handle_agent_event` to Use New Parser**:
    -   Integrate the `_parse_a2a_event_from_rpc_result` method created in the previous step.
    -   If parsing is successful, pass the resulting Pydantic object to `_process_parsed_a2a_event`.
    -   If parsing fails (returns `None`), log an error and NACK the message.

8.  **Update `_process_parsed_a2a_event`**:
    -   Change the type hint for the `parsed_event` parameter to `Union[Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError]`.
    -   Update the `isinstance` checks to use the new `a2a.types` models.

9.  **Update Output Capture Queues**:
    -   In the `__init__` method, update the type hint for `self._captured_outputs` to `Dict[str, asyncio.Queue[Union[Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, JSONRPCError]]]`.
    -   Update the return type hints for `get_next_captured_output` and `get_all_captured_outputs` to match this new union of types.

10. **Refactor URI and Embed Resolution Logic**:
    -   Review `_resolve_uri_in_payload` and `_resolve_embeds_and_handle_signals`.
    -   Update the object traversal logic within these methods to correctly access fields in the new `a2a.types` models (e.g., accessing `event.status.message.parts` instead of legacy paths).

---

## Section C: Validation and Finalization

11. **Update `A2AMessageValidator`**:
    -   In `a2a_validator/validator.py`, review the logic that maps a request `method` to a schema definition name.
    -   Ensure it correctly handles all A2A methods (e.g., `message/send`, `tasks/get`, `tasks/cancel`).
    -   Confirm that the `_load_schema` method correctly points to the synchronized `a2a.json` file.

12. **Update Validator Unit Tests**:
    -   In `a2a_validator/test_validator.py`, review all mock payloads.
    -   Update the payloads to be fully compliant with the `a2a.json` schema, ensuring all required fields (`kind`, `messageId`, etc.) are present.

13. **Update Integration Tests**:
    -   Run the full integration test suite.
    -   For any failing declarative tests, update the `expected_gateway_output` sections in the YAML files to match the new structure of `Task`, `TaskStatusUpdateEvent`, and `TaskArtifactUpdateEvent` objects.
    -   For any failing programmatic tests, update the assertions to validate against the new `a2a.types` models returned by the `TestGatewayComponent`.
