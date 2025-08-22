# A2A Helper Abstraction Layer: Detailed Design

## 1. Introduction

This document provides the detailed design for the A2A Helper Abstraction Layer. This layer will serve as a comprehensive facade between the Solace Agent Mesh (SAM) application logic and the `a2a-sdk`. Its purpose is to centralize and simplify all interactions with A2A protocol objects, thereby increasing maintainability, improving code clarity, and insulating the codebase from future changes in the A2A specification.

## 2. Guiding Principles

The design and implementation of this layer will adhere to the following core principles:

*   **Comprehensive Facade:** The helper layer will be the *only* part of the SAM application that directly interacts with the fields and methods of `a2a.types` objects. All other application code MUST use these helpers.
*   **Official Types as Data Carriers:** The helpers will operate on and return official `a2a.types` Pydantic models (e.g., `Message`, `Task`). We will not create "shadow types" that duplicate the SDK's models. This preserves type safety and leverages the validation provided by the SDK.
*   **No Leaky Abstractions:** Helper functions will be responsible for handling the internal structure of the SDK's types, such as accessing the `.root` attribute of a `RootModel`. The calling code will remain completely ignorant of these implementation details.
*   **Clear and Organized Structure:** The helpers will be organized into a dedicated Python package with modules grouped by their area of concern (e.g., `message`, `task`, `protocol`). This promotes high cohesion and discoverability.
*   **Leverage SDK Utilities:** The helpers will use the existing utilities provided by the `a2a-sdk` (e.g., `a2a.utils.message`) where appropriate, rather than reinventing low-level logic.

## 3. Package Structure

A new package will be created at `src/solace_agent_mesh/common/a2a/` to house the abstraction layer. This structure separates concerns and provides a clean, organized home for all A2A-related helper functions.

```
src/solace_agent_mesh/common/
└── a2a/
    ├── __init__.py           # Exposes the public API of the helper layer.
    ├── protocol.py         # Helpers for protocol-level concerns (topics, requests, responses).
    ├── message.py          # Helpers for creating and consuming Message and Part objects.
    ├── task.py             # Helpers for creating and consuming Task objects.
    ├── artifact.py         # Helpers for creating and consuming Artifact objects.
    ├── events.py           # Helpers for creating and consuming event objects (e.g., TaskStatusUpdateEvent).
    └── translation.py      # Helpers for translating between A2A and other domains (e.g., ADK).
```

## 4. Module-by-Module Design

### 4.1. `a2a.protocol`

This module will handle the "envelope" and "transport" aspects of the A2A protocol.

*   **Purpose:**
    *   Constructing Solace topics for A2A communication.
    *   Parsing incoming JSON-RPC requests and responses into their high-level `a2a.types` objects.
    *   Extracting data from the JSON-RPC envelope (e.g., request ID, method name, result).
*   **Key Functions:**
    *   `get_agent_request_topic(namespace: str, agent_name: str) -> str`
    *   `get_discovery_topic(namespace: str) -> str`
    *   `(All other topic construction functions)`
    *   `get_request_id(request: A2ARequest) -> str | int`
    *   `get_request_method(request: A2ARequest) -> str`
    *   `get_message_from_send_request(request: A2ARequest) -> Message | None`
    *   `get_task_id_from_cancel_request(request: A2ARequest) -> str | None`
    *   `get_response_result(response: JSONRPCResponse) -> Any | None`
    *   `get_response_error(response: JSONRPCResponse) -> JSONRPCError | None`

### 4.2. `a2a.message`

This module is focused on the `Message` object, which is the core unit of conversational content.

*   **Purpose:**
    *   Creating new `Message` objects for various scenarios (text, data, multi-part).
    *   Extracting specific `Part` types from a `Message`.
*   **Key Functions:**
    *   `create_agent_text_message(text: str, ...) -> Message`
    *   `create_agent_data_message(data: dict, ...) -> Message`
    *   `create_user_message(parts: list[Part], ...) -> Message`
    *   `get_text_from_message(message: Message) -> str`
    *   `get_data_parts_from_message(message: Message) -> list[DataPart]`
    *   `get_file_parts_from_message(message: Message) -> list[FilePart]`
    *   `get_message_id(message: Message) -> str`
    *   `get_context_id(message: Message) -> str | None`

### 4.3. `a2a.task`

This module handles the `Task` object, which represents the stateful, long-running unit of work.

*   **Purpose:**
    *   Creating new `Task` objects.
    *   Extracting top-level information from a `Task`.
*   **Key Functions:**
    *   `create_initial_task(request: SendMessageRequest) -> Task`
    *   `create_final_task(status: TaskState, ...) -> Task`
    *   `get_task_id(task: Task) -> str`
    *   `get_task_status(task: Task) -> TaskState`
    *   `get_task_history(task: Task) -> list[Message]`
    *   `get_task_artifacts(task: Task) -> list[Artifact]`

### 4.4. `a2a.artifact`

This module is dedicated to `Artifact` objects, which represent durable outputs.

*   **Purpose:**
    *   Creating new `Artifact` objects.
    *   Extracting information from an `Artifact`.
*   **Key Functions:**
    *   `create_text_artifact(name: str, text: str, ...) -> Artifact`
    *   `create_data_artifact(name: str, data: dict, ...) -> Artifact`
    *   `get_artifact_id(artifact: Artifact) -> str`
    *   `get_parts_from_artifact(artifact: Artifact) -> list[Part]`

### 4.5. `a2a.events`

This module handles the creation and consumption of asynchronous event objects used in streaming and push notification models.

*   **Purpose:**
    *   Creating `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` objects.
    *   Extracting data from these event objects.
*   **Key Functions:**
    *   `create_status_update(task_id: str, context_id: str, message: Message, ...) -> TaskStatusUpdateEvent`
    *   `create_artifact_update(task_id: str, context_id: str, artifact: Artifact, ...) -> TaskArtifactUpdateEvent`
    *   `get_message_from_status_update(event: TaskStatusUpdateEvent) -> Message | None`
    *   `get_data_parts_from_status_update(event: TaskStatusUpdateEvent) -> list[DataPart]`
    *   `get_artifact_from_artifact_update(event: TaskArtifactUpdateEvent) -> Artifact | None`

### 4.6. `a2a.translation`

This module isolates the logic for converting between A2A objects and other data formats, such as the Google ADK.

*   **Purpose:**
    *   Translate an `A2AMessage` to an `adk_types.Content` object.
    *   Translate an `ADKEvent` to an A2A `TaskStatusUpdateEvent`.
*   **Key Functions:**
    *   `translate_a2a_to_adk_content(a2a_message: A2AMessage) -> adk_types.Content`
    *   `format_adk_event_as_a2a_status_update(adk_event: ADKEvent, ...) -> TaskStatusUpdateEvent`

## 5. Usage Pattern Example

This design will transform complex, low-level code into simple, high-level calls.

### Before (Direct Access)

```python
# From an event handler
if isinstance(a2a_response.root.result, TaskStatusUpdateEvent):
    status_event = a2a_response.root.result
    if (
        status_event.status
        and status_event.status.message
        and status_event.status.message.parts
    ):
        for part_from_peer in status_event.status.message.parts:
            if isinstance(part_from_peer.root, DataPart):
                # ... logic to handle the DataPart ...
```

### After (Using Helper Layer)

```python
# From an event handler
from ...common.a2a import protocol, events

result = protocol.get_response_result(a2a_response)
data_parts = events.get_data_parts_from_status_update(result)

if data_parts:
    for data_part in data_parts:
        # ... logic to handle the DataPart ...
```

This new approach is significantly cleaner, more readable, and completely insulates the event handler from the internal structure of the `TaskStatusUpdateEvent`.
