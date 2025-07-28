# Implementation Plan: A2A Proxy Protocol Translation Layer

This document provides a step-by-step plan for implementing the A2A protocol translation layer within the proxy components, as described in the corresponding design document.

## Phase 1: Create Translation Utilities

### 1. Create a New Translation Module

1.1. **File Creation:** Create a new file: `src/agent/proxies/a2a/translation.py`. This will house all the protocol translation logic, keeping it isolated from the component's core responsibilities.

### 2. Implement Inbound Translator (Legacy SAM -> Modern A2A)

2.1. **Function Definition:** In `translation.py`, create a function `translate_sam_to_modern_request(legacy_payload: Dict[str, Any]) -> a2a.types.A2ARequest`.

2.2. **Method Translation:**
    2.2.1. Read the `method` from `legacy_payload`.
    2.2.2. Map `tasks/send` to `message/send`.
    2.2.3. Map `tasks/sendSubscribe` to `message/stream`.
    2.2.4. For other methods like `tasks/cancel`, which are compatible, the method name can remain the same.

2.3. **Parameter Translation (`TaskSendParams` -> `MessageSendParams`):**
    2.3.1. Extract the legacy `params` object.
    2.3.2. Create a new modern `a2a.types.Message` object.
        2.3.2.1. Copy `parts` and `role` from the legacy message.
        2.3.2.2. Map `legacy_params['id']` to `modern_message.task_id`.
        2.3.2.3. Map `legacy_params['sessionId']` to `modern_message.context_id`.
        2.3.2.4. **Generate a new UUID** for `modern_message.message_id`.
    2.3.3. Create a new modern `a2a.types.MessageSendConfiguration` object if needed.
        2.3.3.1. Map `legacy_params['pushNotification']` to `modern_config.push_notification_config`.
        2.3.3.2. Map `legacy_params['historyLength']` to `modern_config.history_length`.
    2.3.4. Create the final modern `a2a.types.MessageSendParams` object, assembling the new message and configuration.

2.4. **Request Assembly:**
    2.4.1. Construct the final modern request object (e.g., `a2a.types.SendMessageRequest`) using the translated method name and params.
    2.4.2. Return the validated Pydantic object.

### 3. Implement Outbound Translator (Modern A2A -> Legacy SAM)

3.1. **Function Definition:** In `translation.py`, create a function `translate_modern_to_sam_response(modern_event: Union[a2a.types.Task, a2a.types.TaskStatusUpdateEvent, a2a.types.TaskArtifactUpdateEvent]) -> Dict[str, Any]`.

3.2. **Task Translation:**
    3.2.1. If `modern_event` is a `Task`, create a new dictionary for the legacy `Task`.
    3.2.2. Map `modern_event.context_id` to `legacy_task['sessionId']`.
    3.2.3. Recursively translate any `Message` objects within `modern_event.history` and `modern_event.status.message` by mapping `context_id` to `sessionId` if present.
    3.2.4. Copy all other compatible fields (`id`, `status`, `artifacts`, etc.).

3.3. **Event Translation (`TaskStatusUpdateEvent` / `TaskArtifactUpdateEvent`):**
    3.3.1. If the event is a status or artifact update, create a new dictionary for the legacy event.
    3.3.2. Map `modern_event.task_id` to `legacy_event['id']`. The modern `context_id` will be discarded as there is no equivalent field in the legacy event model.
    3.3.3. Recursively translate the nested `status` or `artifact` objects as needed.

3.4. **Return Value:** The function should return a dictionary that is ready to be serialized to JSON and published.

## Phase 2: Integrate Translators into `BaseProxyComponent`

### 4. Modify `BaseProxyComponent` (`src/agent/proxies/base/component.py`)

4.1. **Import Translators:** Import the new translation functions from `src.agent.proxies.a2a.translation`.

4.2. **Update `_handle_a2a_request`:**
    4.2.1. Remove the `TypeAdapter` validation logic for `A2ARequest`.
    4.2.2. After parsing the JSON payload, call `translate_sam_to_modern_request(payload)`.
    4.2.3. Pass the returned modern A2A request object to `self._forward_request()`.
    4.2.4. Modify the `except` block to catch any exceptions raised from the translation function and wrap them in a legacy `InvalidRequestError`.

4.3. **Update `_publish_status_update`:**
    4.3.1. The method signature will now accept a modern `a2a.types.TaskStatusUpdateEvent`.
    4.3.2. Before creating the `JSONRPCResponse`, call `translate_modern_to_sam_response(event)` to get the legacy payload dictionary.
    4.3.3. Use this translated dictionary as the `result` in the `JSONRPCResponse`.

4.4. **Update `_publish_final_response`:**
    4.4.1. The method signature will now accept a modern `a2a.types.Task`.
    4.4.2. Before creating the `JSONRPCResponse`, call `translate_modern_to_sam_response(task)` to get the legacy payload dictionary.
    4.3.3. Use this translated dictionary as the `result` in the `JSONRPCResponse`.

## Phase 3: Update `A2AProxyComponent`

### 5. Modify `A2AProxyComponent` (`src/agent/proxies/a2a/component.py`)

5.1. **Update `_forward_request`:**
    5.1.1. Verify the `request` parameter is now typed as `a2a.types.A2ARequest`.
    5.1.2. Ensure the method correctly passes this modern request object to the `a2a.client.A2AClient` methods (`send_message` or `send_message_streaming`).

5.2. **Update `_process_downstream_response`:**
    5.2.1. Verify the `response` parameter is typed with modern `a2a.types` (e.g., `SendMessageResponse`, `Task`, etc.).
    5.2.2. Confirm that these modern objects are passed directly to the base class's `_publish_status_update` and `_publish_final_response` methods without modification.

## Phase 4: Validation

### 6. Run Test Case

6.1. **Execute Test:** Run the `test_a2a_proxy_simple.yaml` declarative test.
6.2. **Verification:**
    6.2.1. The `TestGatewayComponent` sends a legacy `tasks/sendSubscribe` request.
    6.2.2. The `BaseProxyComponent` receives it and calls the inbound translator.
    6.2.3. The `A2AProxyComponent` forwards a modern `message/stream` request to the `TestA2AAgentServer`.
    6.2.4. The `TestA2AAgentServer` responds with modern `Task` event.
    6.2.5. The `A2AProxyComponent` receives the modern `Task`.
    6.2.6. The `BaseProxyComponent` calls the outbound translator.
    6.2.7. A legacy `Task` object (with `sessionId`) is published to the Solace mesh.
    6.2.8. The `TestGatewayComponent` receives the legacy response, and the test assertions pass.
