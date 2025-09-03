# Design Document: Declarative Test A2A Agent Server

## 1. Objective

This document outlines the design for a new test infrastructure component: the **Declarative Test A2A Agent Server**. The primary goal of this component is to provide a controllable, in-process, A2A-compliant agent that can act as a downstream peer for integration testing, particularly for the `A2AProxyComponent`.

This test agent will not contain any real "intelligence." Instead, its behavior will be dictated entirely by declarative instructions provided within the test case itself, mirroring the successful pattern established by the `TestLLMServer`. This ensures that tests are predictable, repeatable, and can cover a wide range of complex interaction scenarios without relying on a real, stateful agent.

## 2. Core Concepts

The test agent's design is based on three core principles:

1.  **Declarative Control:** The agent's entire response sequence for a given task is defined within the initial request from the test. This eliminates variability and allows for precise testing of specific behaviors.
2.  **Stateful, Turn-Based Interaction:** The agent maintains a state cache keyed by a `test_case_id`. It uses the conversation history to determine the current "turn" and delivers the pre-configured response for that turn, enabling multi-step interaction tests.
3.  **A2A Protocol Compliance:** The agent runs as a standard A2A server over HTTP, exposing a JSON-RPC endpoint. It consumes and produces standard A2A event types (`Task`, `TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`), allowing it to act as a realistic downstream peer for the `A2AProxyComponent`.

## 3. System Components

The test infrastructure will consist of three main parts:

### 3.1. `TestA2AAgentServer`

This class is the main test fixture, responsible for the lifecycle of the test agent. It is analogous to the existing `TestLLMServer`.

**Responsibilities:**

*   **Hosting:** Runs a `uvicorn` server in a background thread to host a FastAPI application.
*   **A2A Application:** Instantiates and configures an `A2AFastAPIApplication` to handle incoming JSON-RPC requests.
*   **State Management:** Maintains a `_stateful_responses_cache`, a dictionary that maps a `test_case_id` to a pre-configured sequence of responses for that test.
*   **Request Capture:** Includes an HTTP middleware to capture all incoming requests for post-test validation.
*   **Lifecycle Management:** Provides `start()`, `stop()`, and `clear_...()` methods for use in pytest fixtures.

### 3.2. `DeclarativeAgentExecutor`

This class implements the `AgentExecutor` interface and contains the core logic for the test agent. It replaces the simple `EchoAgentExecutor`.

**Responsibilities:**

1.  **Directive Parsing:** Upon receiving a request, it inspects the incoming message content for two directives:
    *   `[test_case_id=...]`: A unique identifier for the test scenario.
    *   `[responses_json=...]`: A Base64-encoded JSON string defining the response sequence.
2.  **State Caching:** If it's the first turn for a `test_case_id`, it decodes the `responses_json` and stores the response sequence in the `TestA2AAgentServer`'s state cache.
3.  **Turn-Based Event Playback:** It determines the current turn index (based on the length of the task's history). It retrieves the corresponding list of events for that turn from the state cache.
4.  **Event Enqueueing:** It iterates through the list of pre-defined A2A event objects for the current turn and enqueues them into the `EventQueue` provided by the `DefaultRequestHandler`. This simulates a real agent producing status updates, artifacts, and final results.
5.  **Task Finalization:** After enqueueing all events for a turn, it closes the event queue to signal the completion of its work for that interaction.

### 3.3. `conftest.py` Integration

A new session-scoped pytest fixture, `test_a2a_agent_server`, will be created to manage the lifecycle of the `TestA2AAgentServer`. This fixture will be injected into the `shared_solace_connector` fixture, which will configure an `A2AProxyApp` instance to point to the test agent's URL.

## 4. Declarative Control Flow and Schema

The entire test flow is controlled from the declarative YAML test file.

### 4.1. Control Directives

The `gateway_input.prompt.text` field in the YAML will contain the control directives:

```yaml
gateway_input:
  prompt:
    parts:
      - text: >
          This is the user prompt.
          [test_case_id=proxy_artifact_test_001]
          [responses_json=BASE64_ENCODED_JSON_HERE]
```

### 4.2. `responses_json` Schema

The `responses_json` directive, once decoded, will be a JSON array where each element represents a **turn**. Each turn is an array of **A2A event objects** to be emitted in sequence.

**Decoded JSON Structure:**

```json
[
  // Turn 0: Response to the first message from the proxy
  [
    {
      "kind": "status-update",
      "final": false,
      "status": { "state": "working", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Starting work..."}] } }
    },
    {
      "kind": "artifact-update",
      "artifact": {
        "artifactId": "generated-file-1",
        "name": "report.csv",
        "parts": [{
          "kind": "file",
          "file": {
            "name": "report.csv",
            "mimeType": "text/csv",
            "bytes": "bmFtZSx2YWx1ZQphbHBoYSwxMApiZXRhLDIw" // base64 of "name,value\nalpha,10\nbeta,20"
          }
        }]
      }
    },
    {
      "kind": "task",
      "status": { "state": "completed", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Task complete."}] } }
    }
  ],

  // Turn 1: Response if the proxy sends a second message to the same task
  [
    {
      "kind": "status-update",
      "final": false,
      "status": { "state": "working", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Processing follow-up."}] } }
    },
    {
      "kind": "task",
      "status": { "state": "completed", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Follow-up complete."}] } }
    }
  ]
]
```

*Note: The `taskId` and `contextId` fields will be dynamically injected by the `DeclarativeAgentExecutor` at runtime to match the current task, so they don't need to be specified in the YAML.*

## 5. Artifact Handling Workflow

This design provides a robust, verifiable workflow for testing artifact handling through the proxy.

1.  **Artifacts Sent TO the Test Agent:**
    *   A test YAML uses `setup_artifacts` to place a file (e.g., `input.txt`) into the shared `TestInMemoryArtifactService`.
    *   The `gateway_input` prompt includes a reference: `Please process artifact://.../input.txt`.
    *   The `A2AProxyComponent` is responsible for resolving this URI, loading the artifact's bytes, and embedding them in the `FilePart` of the `SendMessageRequest` it forwards to the downstream test agent.
    *   The test can validate that the proxy performed this action by inspecting the captured requests on the `TestA2AAgentServer`.

2.  **Artifacts Received FROM the Test Agent:**
    *   The `responses_json` in the test YAML defines a `TaskArtifactUpdateEvent` containing the desired artifact content (as base64-encoded bytes).
    *   The `DeclarativeAgentExecutor` plays back this event.
    *   The `A2AProxyComponent` receives this event. Its `_handle_outbound_artifacts` logic must intercept the `FilePart`, save the bytes to the shared `TestInMemoryArtifactService`, and rewrite the `FilePart` to be an `artifact://` URI reference before forwarding the event to the gateway.
    *   The test's `expected_artifacts` block asserts that the file (`report.csv` in the example) now exists in the artifact service with the correct content, proving the proxy handled the outbound artifact correctly.

## 6. Example Declarative Test

This example demonstrates how the components work together in a single test case.

```yaml
test_case_id: "a2a_proxy_with_artifacts_001"
description: "Tests proxy forwarding of a request and handling of a returned artifact."

gateway_input:
  target_agent_name: "ProxiedDownstreamAgent"
  user_identity: "proxy_tester@example.com"
  prompt:
    parts:
      - text: >
          Please process this request.
          [test_case_id=a2a_proxy_with_artifacts_001]
          [responses_json=BASE64_ENCODED_JSON_OF_THE_SCHEMA_BELOW]

# The JSON to be base64-encoded for the directive above:
# [
#   [
#     {
#       "kind": "status-update", "final": false,
#       "status": { "state": "working", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Work in progress..."}] } }
#     },
#     {
#       "kind": "artifact-update",
#       "artifact": {
#         "artifactId": "abc-123", "name": "result.txt",
#         "parts": [{"kind": "file", "file": {"name": "result.txt", "mimeType": "text/plain", "bytes": "UHJveHkgdGVzdCBzdWNjZXNzZnVsIQ=="}}]
#       }
#     },
#     {
#       "kind": "task",
#       "status": { "state": "completed", "message": { "role": "agent", "parts": [{"kind": "text", "text": "Done."}] } }
#     }
#   ]
# ]

# The proxy itself does not interact with the LLM.
llm_interactions: []

# Assertions against the events received by the TestGatewayComponent
expected_gateway_output:
  - type: "status_update"
    event_purpose: "generic_text_update"
    content_parts:
      - type: "text"
        text_contains: "Work in progress..."
  - type: "artifact_update"
    expected_artifact_name_contains: "result.txt"
    # The proxy should have converted the bytes to a reference
    assert_part_is_uri_reference: true
  - type: "final_response"
    task_state: "completed"
    content_parts:
      - type: "text"
        text_contains: "Done."

# Assertions against the final state of the artifact service
expected_artifacts:
  - filename: "result.txt"
    version: 1 # Or "latest"
    mime_type: "text/plain"
    text_exact: "Proxy test successful!"
```

## 7. Conclusion

This design provides a powerful, flexible, and consistent framework for testing the `A2AProxyComponent`. By leveraging declarative control and mirroring existing test patterns, it enables the creation of comprehensive integration tests that can validate complex interaction flows, including stateful conversations and end-to-end artifact handling, in a fully predictable and automated manner.
