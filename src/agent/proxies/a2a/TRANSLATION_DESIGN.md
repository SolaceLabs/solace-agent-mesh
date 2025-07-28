# Design Document: A2A Proxy Protocol Translation Layer

## 1. Objective

This document details the design for implementing a protocol translation layer within the `A2AProxyComponent`. The primary goal is to enable the proxy to act as a bridge between the legacy Solace Agent Mesh (SAM) A2A protocol and the modern, standardized A2A protocol defined by the `a2a-python` SDK. This will allow legacy SAM components to communicate with modern A2A agents via the proxy.

## 2. Core Design

The `A2AProxyComponent` will be enhanced to perform bidirectional protocol translation. It will have two "faces":

1.  **Legacy "Server" Face:** Listens on the Solace event mesh for requests from SAM components. It understands the legacy protocol (e.g., `tasks/sendSubscribe`).
2.  **Modern "Client" Face:** Communicates over HTTP with downstream agents. It speaks the modern A2A protocol (e.g., `message/stream`) using the `a2a-python` client library.

The core of this design involves creating stateless translation functions that convert request and response objects between the two protocol formats.

## 3. Component Responsibilities

### 3.1. `BaseProxyComponent` (`src/agent/proxies/base/component.py`)

The base class will be modified to orchestrate the translation flow.

-   **Request Handling (`_handle_a2a_request`):**
    -   This method will no longer attempt to validate the incoming payload against the modern `A2ARequest` schema directly.
    -   It will parse the incoming JSON to identify the legacy method name (e.g., `tasks/sendSubscribe`).
    -   It will call a new **inbound translation function** to convert the legacy SAM request object into a modern `a2a.types` request object.
    -   It will then pass this modern request object to the concrete `_forward_request` implementation.

-   **Response Handling (`_publish_status_update`, `_publish_final_response`):**
    -   These methods will be modified to accept modern `a2a.types` event objects (`TaskStatusUpdateEvent`, `Task`) from the concrete proxy implementation.
    -   Before publishing to Solace, they will call a new **outbound translation function** to convert the modern event object back into the legacy SAM `common.types` format.

### 3.2. `A2AProxyComponent` (`src/agent/proxies/a2a/component.py`)

The concrete implementation will focus solely on modern A2A communication.

-   **Forwarding (`_forward_request`):**
    -   This method will receive a *modern, already-translated* `a2a.types.A2ARequest` object from the base class.
    -   It will use its internal `a2a.client.A2AClient` to send this request to the downstream agent without needing any knowledge of the legacy protocol.
-   **Processing Responses (`_process_downstream_response`):**
    -   This method will receive modern `a2a.types` response objects from the `A2AClient`.
    -   It will pass these modern objects directly up to the base class's `_publish_*` methods for translation and publishing.

## 4. Translation Mapping Specification

This section defines the precise data transformations required.

### 4.1. Inbound Translation: SAM Request -> Modern A2A Request

A new function, e.g., `_translate_sam_to_modern_request`, will be created.

| Legacy SAM (`common.types`) | Modern A2A (`a2a.types`) | Transformation Logic |
| :--- | :--- | :--- |
| `SendTaskStreamingRequest` | `SendStreamingMessageRequest` | **Method:** `tasks/sendSubscribe` -> `message/stream`. |
| `SendTaskRequest` | `SendMessageRequest` | **Method:** `tasks/send` -> `message/send`. |
| `CancelTaskRequest` | `CancelTaskRequest` | No translation needed; structures are compatible. |
| `params` (`TaskSendParams`) | `params` (`MessageSendParams`) | The entire `params` object must be rebuilt. |
| `params.id` | `params.message.task_id` | Move task ID into the message object. |
| `params.sessionId` | `params.message.context_id` | Rename `sessionId` to `context_id` and move into the message. |
| `params.message` | `params.message` | The core message object is moved. A new `message_id` (UUID) **must be generated** and added, as it's required in the modern spec. |
| `params.pushNotification` | `params.configuration.push_notification_config` | The push config object is moved into a new `configuration` wrapper object. |
| `params.historyLength` | `params.configuration.history_length` | Moved into the `configuration` wrapper. |

### 4.2. Outbound Translation: Modern A2A Response -> SAM Response

A new function, e.g., `_translate_modern_to_sam_response`, will be created.

| Modern A2A (`a2a.types`) | Legacy SAM (`common.types`) | Transformation Logic |
| :--- | :--- | :--- |
| `Task` | `Task` | The `Task` object must be rebuilt. |
| `Task.context_id` | `Task.sessionId` | Rename `context_id` back to `sessionId`. |
| `Task.history` | `Task.history` | Translate each `Message` in the history list (recursively apply `context_id` -> `sessionId` mapping if present). |
| `TaskStatusUpdateEvent` | `TaskStatusUpdateEvent` | The event object must be rebuilt. |
| `TaskStatusUpdateEvent.context_id` | `TaskStatusUpdateEvent.id` | The modern event has `task_id` and `context_id`. The legacy event only has `id`. The modern `task_id` should be mapped to the legacy `id`. The `context_id` is lost in this translation, which is an acceptable limitation. |
| `TaskStatusUpdateEvent.status` | `TaskStatusUpdateEvent.status` | Translate the inner `TaskStatus` object (specifically its `message` field). |
| `TaskArtifactUpdateEvent` | `TaskArtifactUpdateEvent` | The event object must be rebuilt. |
| `TaskArtifactUpdateEvent.context_id` | `TaskArtifactUpdateEvent.id` | Same as `TaskStatusUpdateEvent`: map modern `task_id` to legacy `id`. |

## 5. Artifact Handling

The translation layer does not change the core artifact handling logic, but it must ensure that `FilePart` objects within translated messages are preserved correctly.

-   **Inbound:** When translating a legacy request to modern, any `FilePart` objects are passed through unmodified. The proxy's existing logic for resolving `artifact://` URIs will still run *before* translation.
-   **Outbound:** When translating a modern response to legacy, any `FilePart` objects are passed through. The proxy's logic for saving outbound artifacts and rewriting them to `artifact://` URIs will run *before* the response is passed to the outbound translator.

## 6. Error Handling

If an incoming legacy request cannot be successfully translated into a modern request (e.g., due to malformed data that doesn't fit either spec), the translation function will raise an exception. The `_handle_a2a_request` method will catch this, log the error, and publish a legacy `InternalError` or `InvalidRequestError` back to the original requester.
