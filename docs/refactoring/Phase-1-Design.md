# A2A SDK Migration: Phase 1 Detailed Design

## 1. Objective

The objective of Phase 1 is to refactor the core backend components of the Solace Agent Mesh (SAM) to be fully compliant with the latest A2A specification, using the `a2a-sdk` for its type system. This phase will focus on modifying the agent's request handling, status update generation, and peer delegation logic. The success of this phase will be validated by making the existing integration test suite pass using a refactored `TestGatewayComponent` as the reference client.

## 2. Scope

This phase is strictly limited to the backend components and the test infrastructure necessary to validate them.

### In Scope:
-   **Agent Request Handling:** `src/solace_agent_mesh/agent/protocol/event_handlers.py`
-   **Agent Status Generation:** `src/solace_agent_mesh/agent/adk/callbacks.py`
-   **Agent-to-Agent Delegation:** `src/solace_agent_mesh/agent/tools/peer_agent_tool.py`
-   **Task State Management:** `src/solace_agent_mesh/agent/sac/task_execution_context.py` (minor changes to support new IDs)
-   **Test Client:** `sam_test_infrastructure/gateway_interface/component.py` (`TestGatewayComponent`)
-   **Integration Tests:** All tests that rely on the `TestGatewayComponent` and validate A2A message flows.
-   **Test Fixtures:** All fixtures in `tests/integration/conftest.py` that produce mock A2A data.

### Out of Scope:
-   Any production gateways (`http_sse`, `slack`, `webhook`).
-   The Web UI frontend.
-   Major refactoring of the internal agent logic beyond what is necessary for protocol compliance.
-   Implementing new features.

---

## 3. Core Design Changes

### 3.1. Type System Migration

All A2A-related data structures will be migrated from the legacy models in `src/solace_agent_mesh/common/types.py` to the official models in the `a2a.types` module provided by the `a2a-sdk`. This is the foundational change that will drive all other refactoring efforts in this phase.

### 3.2. Agent Request Handling (`event_handlers.py`)

The `handle_a2a_request` function will be redesigned to act as a compliant A2A server endpoint.

-   **Request Parsing:** The function will no longer use the legacy `A2ARequest.validate_python`. It will now parse the incoming message payload into the `a2a.types.A2ARequest` discriminated union. This will provide strong typing for all incoming request types (`SendMessageRequest`, `CancelTaskRequest`, etc.).
-   **Task ID Generation:** The server (agent) is now responsible for creating the `taskId`. Upon receiving a `SendMessageRequest`, the handler will generate a new, unique `taskId` (e.g., using `uuid.uuid4()`). This `taskId` will be the primary identifier for the unit of work.
-   **Context Propagation:** The handler will extract the `contextId` and `messageId` from the incoming `a2a.types.Message`.
    -   The `contextId` (the new `sessionId`) will be passed into the `TaskExecutionContext` to track the conversation.
    -   The `taskId` (newly generated) will also be stored in the context.
    -   The `messageId` will be logged for traceability.

### 3.3. Status Update Generation (`callbacks.py`)

This is the most significant design change, moving from informal `metadata` to structured `DataPart` objects for non-visible status updates.

-   **New Message Structure:** All status updates will be sent via a `TaskStatusUpdateEvent`. The event's `status` field will contain a `TaskStatus` object, which in turn contains a `Message`. This `Message` will have a `parts` array that can hold multiple `Part` objects.
-   **`DataPart` for Structured Data:** All machine-readable status signals will be encapsulated in a `a2a.types.DataPart`. The `data` field of this part will be a dictionary conforming to a defined JSON schema.
-   **Example Flow (`notify_tool_invocation_start_callback`):**
    1.  The callback will be triggered.
    2.  It will create a dictionary payload for the tool invocation start event (e.g., `{"type": "tool_invocation_start", "tool_name": "...", ...}`).
    3.  This dictionary will be placed inside a `DataPart(data=...)`.
    4.  A new `Message` will be created with its `parts` array containing this `DataPart`.
    5.  This `Message` will be wrapped in a `TaskStatus` and then a `TaskStatusUpdateEvent`, which is then published.
-   **Human-Readable Text:** If a status update needs to include human-readable text for logging or a simple UI, a `TextPart` can be included in the *same* `Message.parts` array alongside the `DataPart`.

### 3.4. Peer Agent Delegation (`peer_agent_tool.py`)

The `PeerAgentTool` will be updated to act as a compliant A2A client.

-   **Request Creation:** The `run_async` method will instantiate an `a2a.types.SendMessageRequest` object.
-   **ID Management:**
    -   It will generate a new, unique `messageId` for the request.
    -   It will propagate the `contextId` from the parent task to the `message.contextId` of the sub-task request, ensuring the conversational context is maintained.
-   **Correlation:** The tool's internal correlation logic (which currently relies on a client-generated task ID) will be adapted. It will now need to wait for the first response from the peer agent to learn the server-generated `taskId` for the sub-task and use that for tracking subsequent events.

### 3.5. Error Handling

For Phase 1, the design is to keep error handling simple and compliant. All internal exceptions caught during task execution will be mapped to the generic `a2a.types.InternalError` model before being published as the `error` field in a `JSONRPCResponse`.

---

## 4. `DataPart` Schema Definitions

To ensure consistency and provide a clear contract for consumers (like the frontend), we will define JSON schemas for our non-visible status messages. These schemas will be stored in a new directory: `src/solace_agent_mesh/common/a2a_spec/schemas/`.

The following schemas will be created in Phase 1:

1.  **`tool_invocation_start.json`**:
    -   `type`: (string, const) "tool_invocation_start"
    -   `tool_name`: (string) The name of the tool being called.
    -   `tool_args`: (object) The arguments passed to the tool.
    -   `function_call_id`: (string) The ID from the LLM's function call.
2.  **`llm_invocation.json`**:
    -   `type`: (string, const) "llm_invocation"
    -   `request`: (object) A sanitized representation of the `LlmRequest` object sent to the model.
3.  **`agent_progress_update.json`**:
    -   `type`: (string, const) "agent_progress_update"
    -   `status_text`: (string) A human-readable progress message (e.g., "Analyzing the report...").
4.  **`artifact_creation_progress.json`**:
    -   `type`: (string, const) "artifact_creation_progress"
    -   `filename`: (string) The name of the artifact being created.
    -   `bytes_saved`: (integer) The number of bytes saved so far.

These schemas will be used to generate Pydantic models for backend validation and can be used to generate TypeScript interfaces for the frontend in a later phase.
