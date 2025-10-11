# Implementation Plan: Migrate A2A Proxy from Deprecated A2AClient to Modern ClientFactory

## Overview
This document outlines the step-by-step implementation plan to migrate the A2A proxy component from the deprecated `A2AClient` to the modern `ClientFactory` pattern, while ensuring all code uses the `common/a2a/` facade layer to avoid direct SDK access.

---

## Phase 1: Extend the Facade Layer

### 1.1 Add Part Type Checking Helpers to `message.py`

**File**: `src/solace_agent_mesh/common/a2a/message.py`

Add the following helper functions after the existing consumption helpers:

- `is_text_part(part: Part) -> bool` - Check if a Part contains a TextPart
- `is_file_part(part: Part) -> bool` - Check if a Part contains a FilePart  
- `is_data_part(part: Part) -> bool` - Check if a Part contains a DataPart
- `is_file_part_bytes(part: FilePart) -> bool` - Check if FilePart uses FileWithBytes
- `is_file_part_uri(part: FilePart) -> bool` - Check if FilePart uses FileWithUri

Implementation approach:
- Use `isinstance(part.root, TextPart)` internally to hide `.root` access
- Return boolean values
- Add docstrings explaining the purpose

### 1.2 Add Event Type Checking Helpers to `events.py`

**File**: `src/solace_agent_mesh/common/a2a/events.py`

Add the following helper functions in a new "Type Checking Helpers" section:

- `is_task_status_update(obj: Any) -> bool` - Check if object is TaskStatusUpdateEvent
- `is_task_artifact_update(obj: Any) -> bool` - Check if object is TaskArtifactUpdateEvent

Implementation approach:
- Use `isinstance()` checks internally
- Return boolean values
- Add type hints with `Any` for input to handle unknown types

### 1.3 Add Client Event Helpers to `protocol.py`

**File**: `src/solace_agent_mesh/common/a2a/protocol.py`

Add the following helper functions in a new "Client Event Helpers" section:

- `is_client_event(obj: Any) -> bool` - Check if object is a ClientEvent tuple
- `is_message_object(obj: Any) -> bool` - Check if object is a Message
- `unpack_client_event(event: tuple) -> Tuple[Task, Optional[Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]]]` - Safely unpack a ClientEvent tuple

Implementation approach:
- `is_client_event()`: Check if object is a tuple with 2 elements where first is Task
- `is_message_object()`: Use `isinstance(obj, Message)`
- `unpack_client_event()`: Return the tuple elements with proper typing
- Add proper imports for `Task`, `TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`

### 1.4 Add Artifact Content Helpers to `artifact.py`

**File**: `src/solace_agent_mesh/common/a2a/artifact.py`

Add the following helper functions:

- `is_text_only_artifact(artifact: Artifact) -> bool` - Check if artifact contains only TextParts
- `get_text_content_from_artifact(artifact: Artifact) -> List[str]` - Extract all text from TextParts in artifact

Implementation approach:
- `is_text_only_artifact()`: Iterate through parts, check each with `isinstance(part.root, TextPart)`
- `get_text_content_from_artifact()`: Extract text from all TextParts, return as list
- Return empty list if no text parts found

### 1.5 Update `__init__.py` Exports

**File**: `src/solace_agent_mesh/common/a2a/__init__.py`

Add all new helper functions to the `__all__` list and import statements:

From `message.py`:
- `is_text_part`
- `is_file_part`
- `is_data_part`
- `is_file_part_bytes`
- `is_file_part_uri`

From `events.py`:
- `is_task_status_update`
- `is_task_artifact_update`

From `protocol.py`:
- `is_client_event`
- `is_message_object`
- `unpack_client_event`

From `artifact.py`:
- `is_text_only_artifact`
- `get_text_content_from_artifact`

---

## Phase 2: Refactor Existing Proxy Code to Use Facade

### 2.1 Update Imports in `component.py`

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Changes needed:
- Remove direct imports of A2A SDK types that are accessed via `.root` (TextPart, FilePart, DataPart, FileWithBytes, FileWithUri)
- Keep imports of top-level types (Message, Task, etc.) that are used for type hints
- Ensure `from ....common import a2a` import is present

### 2.2 Refactor `_handle_outbound_artifacts` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Replace all direct SDK access with facade calls:

**Current problematic patterns:**
```python
isinstance(part.root, TextPart)
part.root.text
isinstance(part.root, FilePart)
isinstance(part.file, FileWithBytes)
part.file.bytes
```

**Replace with facade calls:**
```python
a2a.is_text_part(part)
a2a.get_text_from_text_part(part.root)  # or add wrapper that takes Part
a2a.is_file_part(part)
a2a.is_file_part_bytes(part.root)
a2a.get_bytes_from_file_part(part.root)
```

Specific changes:
1. Replace TextPart type check and text extraction in the loop that builds `contextual_description`
2. Replace FilePart type check in the loop that processes file parts
3. Replace FileWithBytes type check when determining if file has byte content
4. Use facade helpers for all file content access

### 2.3 Refactor `_process_downstream_response` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Replace artifact processing logic:

**Current problematic pattern:**
```python
for artifact in event_payload.artifacts:
    is_text_only = True
    for part in artifact.parts:
        if isinstance(part.root, TextPart):
            artifact_text_parts.append(part.root.text)
        elif isinstance(part.root, (FilePart, DataPart)):
            is_text_only = False
```

**Replace with facade calls:**
```python
for artifact in event_payload.artifacts:
    if a2a.is_text_only_artifact(artifact):
        text_only_artifacts_content.extend(a2a.get_text_content_from_artifact(artifact))
    else:
        remaining_artifacts.append(artifact)
```

This simplifies the logic significantly by using the new artifact helpers.

---

## Phase 3: Migrate to Modern Client API

### 3.1 Update Imports in `component.py`

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Changes:
- Remove: `from a2a.client import A2AClient, A2ACardResolver, A2AClientHTTPError, AuthInterceptor, InMemoryContextCredentialStore`
- Add: `from a2a.client import Client, ClientFactory, ClientConfig, ClientEvent, A2ACardResolver, A2AClientHTTPError, A2AClientJSONRPCError, AuthInterceptor, InMemoryContextCredentialStore`
- Add: `from a2a.types import TransportProtocol`

### 3.2 Update Type Hints

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Change the `_a2a_clients` dictionary type hint:
- From: `Dict[Tuple[str, str], A2AClient]`
- To: `Dict[Tuple[str, str], Client]`

### 3.3 Refactor `_get_or_create_a2a_client` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Major changes to client creation logic:

1. **Keep existing logic** for:
   - Cache key checking
   - Agent config retrieval
   - Agent card retrieval
   - Timeout resolution
   - httpx client creation
   - Authentication setup (OAuth, static tokens)

2. **Replace client instantiation**:
   - Remove: `client = A2AClient(httpx_client=..., agent_card=..., interceptors=...)`
   - Add: Create `ClientConfig` object with:
     - `streaming=True`
     - `polling=False`
     - `httpx_client=httpx_client_for_agent`
     - `supported_transports=[TransportProtocol.jsonrpc]` (or empty list for default)
     - `accepted_output_modes=[]`
   - Add: `factory = ClientFactory(config)`
   - Add: `client = factory.create(agent_card, consumers=None, interceptors=[self._auth_interceptor])`

3. **Update return type** hint from `A2AClient` to `Client`

### 3.4 Refactor `_forward_request` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Major changes to request forwarding and response handling:

1. **Update method signature**:
   - Keep existing parameters
   - Update type hints to use `Client` instead of `A2AClient`

2. **Change request invocation**:
   - Current: `response = await client.send_message(request, context=call_context)`
   - New: `response_iterator = client.send_message(request.params.message, context=call_context)`
   - Note: Pass `request.params.message` (the Message object) instead of the full request

3. **Handle streaming vs non-streaming**:
   - Remove: `if isinstance(request, SendStreamingMessageRequest)` check
   - New: Always iterate over the async iterator returned by `send_message()`
   - The modern client returns an iterator for both streaming and non-streaming

4. **Update iteration logic**:
   - Current: `async for response in client.send_message_streaming(request, context=call_context)`
   - New: `async for event in client.send_message(request.params.message, context=call_context)`

5. **Update response processing call**:
   - Change parameter from `response` to `event`
   - The event is now either a `ClientEvent` tuple or a `Message` object

6. **Update error handling**:
   - Wrap client calls in try/except
   - Add: `except A2AClientJSONRPCError as e:` to catch JSON-RPC errors
   - Keep existing `A2AClientHTTPError` handling for 401 retry logic
   - Remove any response wrapper error checking (no more `.root.error`)

### 3.5 Refactor `_process_downstream_response` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Major changes to response processing:

1. **Update method signature**:
   - Change parameter type from `Union[SendMessageResponse, SendStreamingMessageResponse, Task, TaskStatusUpdateEvent]`
   - To: `Union[ClientEvent, Message]`
   - Update `client` parameter type from `A2AClient` to `Client`

2. **Replace response unwrapping logic**:
   - Remove: All code that checks `isinstance(response, (SendMessageResponse, SendStreamingMessageResponse))`
   - Remove: All code that extracts `.root.result` or checks `.root.error`
   - Add: Use facade helpers to determine event type:
     ```python
     if a2a.is_client_event(event):
         task, update_event = a2a.unpack_client_event(event)
         event_payload = task
     elif a2a.is_message_object(event):
         event_payload = event  # Direct Message response
     else:
         # Log warning about unexpected type
     ```

3. **Update event payload handling**:
   - The `event_payload` is now directly a `Task`, `Message`, or update event
   - No need to extract from response wrappers
   - Keep all existing artifact handling, metadata addition, and publishing logic

4. **Simplify Message wrapping logic**:
   - When `event_payload` is a `Message`, wrap it in a completed Task (existing logic)
   - This case now happens when `is_message_object(event)` is true

### 3.6 Update `_handle_auth_error` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Minor changes:
- Update log messages to reference `Client` instead of `A2AClient`
- Update comments to reference modern client
- Logic remains the same (invalidate token, remove cached client)

### 3.7 Update `cleanup` Method

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Change client cleanup:
- Remove: `if client._client and not client._client.is_closed: await client._client.aclose()`
- Add: `await client.close()`
- This uses the public API instead of accessing internal `_client` attribute

---

## Phase 4: Update Error Handling Throughout

### 4.1 Add JSON-RPC Error Handling

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

In `_forward_request` method, update the try/except block:

1. **Add new exception handler**:
   ```python
   except A2AClientJSONRPCError as e:
       log.error("%s JSON-RPC error from agent: %s", log_identifier, e.error)
       # Publish error response to Solace
       # Do not retry - this is a protocol-level error
   ```

2. **Keep existing HTTP error handler** but update for new client:
   - The 401 detection logic stays the same
   - The retry mechanism stays the same
   - Update to catch exceptions instead of checking response codes

3. **Add generic exception handler** at the end:
   ```python
   except Exception as e:
       log.exception("%s Unexpected error forwarding request: %s", log_identifier, e)
       # Let base class exception handler in _handle_a2a_request catch this
       raise
   ```

---

## Phase 5: Verify All Direct SDK Access is Removed

### 5.1 Search and Replace Patterns

**File**: `src/solace_agent_mesh/agent/proxies/a2a/component.py`

Verify no instances of these patterns remain:
- `.root` access (except in facade layer)
- `isinstance(part.root, ...)` (should use facade helpers)
- `isinstance(file, FileWithBytes)` (should use facade helpers)
- Direct access to `part.root.text`, `part.root.data`, etc. (should use facade getters)

### 5.2 Update Type Hints

Ensure all type hints reference:
- `Client` instead of `A2AClient`
- Top-level A2A types (Message, Task, etc.) for parameters
- Facade return types where applicable

---

## Summary of File Changes

### Files to Modify:
1. `src/solace_agent_mesh/common/a2a/message.py` - Add part type checking helpers
2. `src/solace_agent_mesh/common/a2a/events.py` - Add event type checking helpers
3. `src/solace_agent_mesh/common/a2a/protocol.py` - Add client event helpers
4. `src/solace_agent_mesh/common/a2a/artifact.py` - Add artifact content helpers
5. `src/solace_agent_mesh/common/a2a/__init__.py` - Export new helpers
6. `src/solace_agent_mesh/agent/proxies/a2a/component.py`  - Main migration work

### No New Files Required

### Key Principles:
- All direct SDK access goes through `common/a2a/` facade
- No `.root` access in business logic
- Use modern `ClientFactory` + `Client` pattern
- Handle errors via exceptions, not response wrappers
- Maintain all existing functionality

---

## Implementation Order

1. **Phase 1**: Extend facade layer (all helper functions)
2. **Phase 2**: Refactor existing code to use facade (eliminate `.root`)
3. **Phase 3**: Migrate to modern client API
4. **Phase 4**: Update error handling
5. **Phase 5**: Final verification and cleanup

This order ensures each phase builds on the previous one and can be tested incrementally.
