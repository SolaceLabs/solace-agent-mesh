# Implementation Checklist: A2A Proxy Protocol Translation Layer

This checklist corresponds to the `TRANSLATION_IMPLEMENTATION_PLAN.md` document and should be used to track progress.

## Phase 1: Create Translation Utilities

### 1. Create a New Translation Module

- [x] **1.1. File Creation:** Create `src/agent/proxies/a2a/translation.py`.

### 2. Implement Inbound Translator (Legacy SAM -> Modern A2A)

- [x] **2.1. Function Definition:** Create `translate_sam_to_modern_request`.
- [x] **2.2. Method Translation:**
    - [x] 2.2.1. Read the `method` from the legacy payload.
    - [x] 2.2.2. Map `tasks/send` to `message/send`.
    - [x] 2.2.3. Map `tasks/sendSubscribe` to `message/stream`.
    - [x] 2.2.4. Handle compatible methods (e.g., `tasks/cancel`).
- [x] **2.3. Parameter Translation (`TaskSendParams` -> `MessageSendParams`):**
    - [x] 2.3.1. Extract the legacy `params` object.
    - [x] 2.3.2. Create a new modern `a2a.types.Message` object.
        - [x] 2.3.2.1. Copy `parts` and `role`.
        - [x] 2.3.2.2. Map `legacy_params['id']` to `modern_message.task_id`.
        - [x] 2.3.2.3. Map `legacy_params['sessionId']` to `modern_message.context_id`.
        - [x] 2.3.2.4. Generate a new UUID for `modern_message.message_id`.
    - [x] 2.3.3. Create a new modern `a2a.types.MessageSendConfiguration` object.
        - [x] 2.3.3.1. Map `legacy_params['pushNotification']`.
        - [x] 2.3.3.2. Map `legacy_params['historyLength']`.
    - [x] 2.3.4. Create the final modern `a2a.types.MessageSendParams` object.
- [x] **2.4. Request Assembly:**
    - [x] 2.4.1. Construct the final modern request object (e.g., `SendMessageRequest`).
    - [x] 2.4.2. Return the validated Pydantic object.

### 3. Implement Outbound Translator (Modern A2A -> Legacy SAM)

- [x] **3.1. Function Definition:** Create `translate_modern_to_sam_response`.
- [x] **3.2. Task Translation:**
    - [x] 3.2.1. Handle `Task` objects, creating a legacy dictionary.
    - [x] 3.2.2. Map `modern_event.context_id` to `legacy_task['sessionId']`.
    - [x] 3.2.3. Recursively translate `Message` objects in `history` and `status.message`.
    - [x] 3.2.4. Copy other compatible fields.
- [x] **3.3. Event Translation (`TaskStatusUpdateEvent` / `TaskArtifactUpdateEvent`):**
    - [x] 3.3.1. Handle event objects, creating a legacy dictionary.
    - [x] 3.3.2. Map `modern_event.task_id` to `legacy_event['id']`.
    - [x] 3.3.3. Recursively translate nested objects.
- [x] **3.4. Return Value:** Ensure the function returns a JSON-serializable dictionary.

## Phase 2: Integrate Translators into `BaseProxyComponent`

### 4. Modify `BaseProxyComponent` (`src/agent/proxies/base/component.py`)

- [ ] **4.1. Import Translators:** Import functions from `src.agent.proxies.a2a.translation`.
- [ ] **4.2. Update `_handle_a2a_request`:**
    - [ ] 4.2.1. Remove `TypeAdapter` validation logic.
    - [ ] 4.2.2. Call `translate_sam_to_modern_request` on the payload.
    - [ ] 4.2.3. Pass the modern request object to `_forward_request`.
    - [ ] 4.2.4. Update the `except` block to handle translation errors.
- [ ] **4.3. Update `_publish_status_update`:**
    - [ ] 4.3.1. Change the method signature to accept a modern `a2a.types.TaskStatusUpdateEvent`.
    - [ ] 4.3.2. Call `translate_modern_to_sam_response` on the event.
    - [ ] 4.3.3. Use the translated dictionary as the `result` for the `JSONRPCResponse`.
- [ ] **4.4. Update `_publish_final_response`:**
    - [ ] 4.4.1. Change the method signature to accept a modern `a2a.types.Task`.
    - [ ] 4.4.2. Call `translate_modern_to_sam_response` on the task.
    - [ ] 4.4.3. Use the translated dictionary as the `result` for the `JSONRPCResponse`.

## Phase 3: Update `A2AProxyComponent`

### 5. Modify `A2AProxyComponent` (`src/agent/proxies/a2a/component.py`)

- [ ] **5.1. Update `_forward_request`:**
    - [ ] 5.1.1. Verify the `request` parameter is typed as `a2a.types.A2ARequest`.
    - [ ] 5.1.2. Ensure the modern request is passed correctly to the `A2AClient`.
- [ ] **5.2. Update `_process_downstream_response`:**
    - [ ] 5.2.1. Verify the `response` parameter is typed with modern `a2a.types`.
    - [ ] 5.2.2. Confirm modern objects are passed directly to the base class's publish methods.

## Phase 4: Validation

### 6. Run Test Case

- [ ] **6.1. Execute Test:** Run `test_a2a_proxy_simple.yaml`.
- [ ] **6.2. Verification:**
    - [ ] 6.2.1. Confirm legacy request is sent by the gateway.
    - [ ] 6.2.2. Confirm `BaseProxyComponent` calls the inbound translator.
    - [ ] 6.2.3. Confirm `A2AProxyComponent` forwards a modern request.
    - [ ] 6.2.4. Confirm `TestA2AAgentServer` responds with a modern event.
    - [ ] 6.2.5. Confirm `A2AProxyComponent` receives the modern event.
    - [ ] 6.2.6. Confirm `BaseProxyComponent` calls the outbound translator.
    - [ ] 6.2.7. Confirm a legacy response is published to Solace.
    - [ ] 6.2.8. Confirm the test assertions pass.
