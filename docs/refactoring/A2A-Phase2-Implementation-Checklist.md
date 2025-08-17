# Implementation Checklist: Phase 2 - Web UI & Gateway Migration

This checklist provides a terse, actionable summary of the tasks required for the Phase 2 refactoring. Refer to the Detailed Design and Implementation Plan documents for more context.

---

### Part 1: Backend Gateway Refactoring

**Step 1: Update Gateway API Endpoints (`tasks.py`)**
- [x] 1.1. Update `@router.post` decorators to use new A2A REST URLs (`/message:send`, `/message:stream`, `/tasks/{taskId}:cancel`).
- [x] 1.2. Update `cancel_agent_task` handler to get `taskId` from the URL path and expect an `a2a.types.CancelTaskRequest` body.
- [x] 1.3. Update `send_task_to_agent` and `subscribe_task_from_agent` handlers to expect an `application/json` body validating against `a2a.types.SendMessageRequest`.

**Step 2: Update Gateway A2A Event Parsing (`component.py`)**
- [x] 2.1. In `BaseGatewayComponent._handle_agent_event`, parse incoming agent messages into `a2a.types.JSONRPCResponse`.
- [x] 2.2. In `BaseGatewayComponent._parse_a2a_event_from_rpc_result`, use the `kind` field to discriminate and parse the result into specific `a2a.types` models (`Task`, `TaskStatusUpdateEvent`, etc.).
- [x] 2.3. Update task ID extraction in `_parse_a2a_event_from_rpc_result` to use the `taskId` field from the new event types.

**Step 3: Update Gateway SSE Forwarding (`component.py`)**
- [x] 3.1. In `WebUIBackendComponent`, update the type hints for `event_data`, `task_data`, and `error_data` parameters in the `_send_*_to_external` methods to use the official `a2a.types`.
- [ ] 3.2. In `WebUIBackendComponent`, update the serialization logic in `_send_*_to_external` methods to use `.model_dump()` for creating the JSON payload sent to the UI.

---

### Part 2: Frontend Web UI Refactoring

**Step 4: Migrate Frontend Type System**
- [ ] 4.1. Add the `@a2a-js/sdk` package as a `devDependency` in `package.json`.
- [ ] 4.2. In `be.ts`, delete all legacy A2A interfaces and replace them with type exports from `@a2a-js/sdk`.
- [ ] 4.3. Create a new `MessageFE` interface that extends the official `Message` type from the SDK to include UI-specific state.

**Step 5: Refactor API Calls and SSE Parsing (`ChatProvider.tsx`)**
- [ ] 5.1. Update `handleSubmit` to call the new `POST /api/v1/message:stream` endpoint with a JSON `SendMessageRequest` body.
- [ ] 5.2. Update `handleCancel` to call the new `POST /api/v1/tasks/{taskId}:cancel` endpoint.
- [ ] 5.3. Rewrite the `handleSseMessage` function to parse incoming event data as a `JSONRPCResponse` from the SDK.
- [ ] 5.4. In `handleSseMessage`, use `result.kind` to determine the event type (`status-update`, `artifact-update`, `task`).
- [ ] 5.5. In `handleSseMessage`, iterate through the `message.parts` array and use a `switch` on `part.kind`.
- [ ] 5.6. Implement the logic for `part.kind === 'data'` to parse status signals (e.g., `tool_invocation_start`) from `part.data`, replacing the old `metadata` parsing logic.
- [ ] 5.7. Update the end-of-turn detection logic to use the `final` flag from `TaskStatusUpdateEvent`.

**Step 6: Update UI Component Rendering**
- [ ] 6.1. Refactor `VisualizerStepCard.tsx` to access data from the new structured `DataPart` objects instead of a flat `metadata` object.
- [ ] 6.2. Refactor `MessageBubble.tsx` to correctly render `ToolEvent` data that is now populated from `DataPart` objects.

---

### Part 3: Validation

**Step 7: End-to-End Testing**
- [ ] 7.1. Launch the fully refactored system (gateway, agent, UI).
- [ ] 7.2. Execute and validate a simple chat scenario.
- [ ] 7.3. Execute and validate a tool-use scenario, checking for correct UI status updates and `TaskMonitor` visualization.
- [ ] 7.4. Execute and validate a file upload and processing scenario.
- [ ] 7.5. Review all logs (browser, gateway, agent) to ensure there are no parsing errors or other exceptions.
