---
title: A2A Technical Migration Map
sidebar_position: 20
---

This document provides a comprehensive, technical mapping for migrating Agent Mesh components from the legacy A2A implementation to the new `a2a-sdk`-based protocol. It is designed to be used as a reference for automated or semi-automated code refactoring.

## Core Concept Changes

-   **Session vs. Context:** The concept of a session, previously `Task.sessionId`, is now attached to the `Message` via `Message.contextId`. The `Task` also has a `contextId`, but it's primarily for grouping. Code that relied on `Task.sessionId` for conversation history must now use `Message.contextId`.
-   **Request/Response Structure:** The structure of JSON-RPC requests and responses is now strictly defined by the SDK's Pydantic models (e.g., `SendMessageRequest`, `JSONRPCResponse` as a discriminated union). Direct dictionary manipulation is replaced by model instantiation and validation.
-   **Status Signaling:** The practice of embedding custom status signals (e.g., `tool_invocation_start`) in the `metadata` field of a message is deprecated. The new standard is to use a dedicated, structured `DataPart` within a multi-part `Message`.

## Import and Type Mapping

### Import Paths

| Old Import Path | New Import Path(s) | Notes |
| :--- | :--- | :--- |
| `solace_agent_mesh.common.types` | `a2a.types`, `solace_agent_mesh.common.a2a`, `solace_agent_mesh.common.a2a.types` | Legacy types are removed. Use SDK types and the `a2a` helper layer. |
| `solace_agent_mesh.common.a2a_protocol` | `solace_agent_mesh.common.a2a` | Protocol helpers (topic builders, etc.) are now in the main `a2a` helper package. |

### Type Hints

| Old Type Hint | New Type Hint | Notes |
| :--- | :--- | :--- |
| `A2APart` | `ContentPart` | `ContentPart` is an alias for `Union[TextPart, DataPart, FilePart]`. |
| `List[A2APart]` | `List[ContentPart]` | Standard type hint for a list of message parts. |
| `FileContent` | `Union[FileWithBytes, FileWithUri]` | The `file` attribute of a `FilePart` is now a discriminated union. |

## Object Creation and Property Access Mapping

This table maps common legacy patterns to their new equivalents using the `a2a` helper layer.

| Action | Old Pattern (Legacy) | New Pattern (a2a-sdk + Helpers) |
| :--- | :--- | :--- |
| **Part Creation** | | |
| Create Text Part | `TextPart(text=...)` | `a2a.create_text_part(text=...)` |
| Create File Part (URI) | `FilePart(file=FileContent(name=..., uri=...))` | `a2a.create_file_part_from_uri(uri=..., name=...)` |
| Create File Part (Bytes) | `FilePart(file=FileContent(bytes=...))` | `a2a.create_file_part_from_bytes(content_bytes=...)` |
| Create Data Part | `DataPart(data=...)` | `a2a.create_data_part(data=...)` |
| **Task/Event Access** | | |
| Get Task ID | `task.id` | `a2a.get_task_id(task)` |
| Get Task Status | `task.status.state` | `a2a.get_task_status(task)` |
| Get Task Context ID | `task.sessionId` | `a2a.get_task_context_id(task)` |
| Get Event's Task ID | `event.id` | `event.task_id` |
| **Message Access** | | |
| Get Message Parts | `message.parts` | `a2a.get_parts_from_message(message)` |
| Get Text from Message | (manual loop over parts) | `a2a.get_text_from_message(message)` |
| Get Data Parts | (manual loop over parts) | `a2a.get_data_parts_from_message(message)` |
| **Error Access** | | |
| Get Error Message | `error.message` | `a2a.get_error_message(error)` |
| Get Error Code | `error.code` | `a2a.get_error_code(error)` |
| Get Error Data | `error.data` | `a2a.get_error_data(error)` |
| **Protocol/RPC** | | |
| Create RPC Success | `JSONRPCResponse(id=..., result=...)` | `a2a.create_success_response(result=..., request_id=...)` |
| Create RPC Error | `JSONRPCResponse(id=..., error=...)` | `a2a.create_error_response(error=..., request_id=...)` |
| Validate RPC Payload | `JSONRPCResponse(**payload)` | `JSONRPCResponse.model_validate(payload)` |
| Topic Matching | `_topic_matches_subscription(...)` | `a2a.topic_matches_subscription(...)` |
| Extract Task ID from Topic | `_extract_task_id_from_topic(...)` | `a2a.extract_task_id_from_topic(...)` |

## Full Method Examples

These examples provide larger, "before and after" contexts for the refactoring patterns.

### Example 1: `_translate_external_input`

**Before:**
```python
from solace_agent_mesh.common.types import Part as A2APart, TextPart, FilePart, FileContent

async def _translate_external_input(self, external_event: Any) -> Tuple[str, List[A2APart], Dict[str, Any]]:
    # ...
    a2a_parts: List[A2APart] = []
    # ...
    artifact_uri = f"artifact://{self.gateway_id}/{user_id}/{a2a_session_id}/{filename}?version={version}"
    file_content_a2a = FileContent(name=filename, mimeType=mime_type, uri=artifact_uri)
    a2a_parts.append(FilePart(file=file_content_a2a))
    # ...
    a2a_parts.append(TextPart(text=processed_text_for_a2a))
    return "agent_name", a2a_parts, {}
```

**After:**
```python
from solace_agent_mesh.common import a2a
from solace_agent_mesh.common.a2a import ContentPart

async def _translate_external_input(self, external_event: Any) -> Tuple[str, List[ContentPart], Dict[str, Any]]:
    # ...
    a2a_parts: List[ContentPart] = []
    # ...
    artifact_uri = f"artifact://{self.gateway_id}/{user_id}/{a2a_session_id}/{filename}?version={version}"
    file_part = a2a.create_file_part_from_uri(uri=artifact_uri, name=filename, mime_type=mime_type)
    a2a_parts.append(file_part)
    # ...
    text_part = a2a.create_text_part(text=processed_text_for_a2a)
    a2a_parts.append(text_part)
    return "agent_name", a2a_parts, {}
```

### Example 2: `_send_update_to_external`

**Before:**
```python
from solace_agent_mesh.common.types import TaskStatusUpdateEvent, TextPart, DataPart

async def _send_update_to_external(self, context: Dict, event_data: TaskStatusUpdateEvent, is_final: bool) -> None:
    task_id = event_data.id
    # ...
    if event_data.status and event_data.status.message and event_data.status.message.parts:
        for part in event_data.status.message.parts:
            if isinstance(part, TextPart):
                # process part.text
            elif isinstance(part, DataPart):
                # process part.data
```

**After:**
```python
from a2a.types import TaskStatusUpdateEvent, TextPart, DataPart
from solace_agent_mesh.common import a2a

async def _send_update_to_external(self, context: Dict, event_data: TaskStatusUpdateEvent, is_final: bool) -> None:
    task_id = event_data.task_id
    # ...
    message = a2a.get_message_from_status_update(event_data)
    if message:
        parts = a2a.get_parts_from_message(message)
        for part in parts:
            if isinstance(part, TextPart):
                # process part.text
            elif isinstance(part, DataPart):
                # process part.data
```

### Example 3: `_send_final_response_to_external`

**Before:**
```python
from solace_agent_mesh.common.types import Task, TaskState

async def _send_final_response_to_external(self, context: Dict, task_data: Task) -> None:
    task_id = task_data.id
    if task_data.status.state == TaskState.FAILED:
        # ...
```

**After:**
```python
from a2a.types import Task, TaskState
from solace_agent_mesh.common import a2a

async def _send_final_response_to_external(self, context: Dict, task_data: Task) -> None:
    task_id = a2a.get_task_id(task_data)
    task_status = a2a.get_task_status(task_data)
    if task_status == TaskState.failed:
        # ...
```

### Example 4: `_send_error_to_external`

**Before:**
```python
from solace_agent_mesh.common.types import JSONRPCError

async def _send_error_to_external(self, context: Dict, error_data: JSONRPCError) -> None:
    error_text = f"Error: {error_data.message} (Code: {error_data.code})"
    if error_data.data:
        # process error_data.data
```

**After:**
```python
from a2a.types import JSONRPCError
from solace_agent_mesh.common import a2a

async def _send_error_to_external(self, context: Dict, error_data: JSONRPCError) -> None:
    error_message = a2a.get_error_message(error_data)
    error_code = a2a.get_error_code(error_data)
    error_details = a2a.get_error_data(error_data)
    error_text = f"Error: {error_message} (Code: {error_code})"
    if error_details:
        # process error_details
```
