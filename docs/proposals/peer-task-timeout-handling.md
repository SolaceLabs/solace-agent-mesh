# Feature Proposal: Robust Peer Agent Task Timeout Handling

## 1. Summary

This document proposes enhancements to the Agent-to-Agent (A2A) communication protocol to handle peer task timeouts more robustly. Currently, when a calling agent's request to a peer agent times out, a race condition can occur where both the timeout event and a subsequent late response from the peer are processed, leading to state corruption and incorrect behavior in the calling agent. Furthermore, the peer agent is not notified of the timeout and continues to expend resources on a task that has already been abandoned by the caller.

This proposal outlines a solution to address these two issues by:
1.  Ensuring that a timed-out task is definitively finalized in the calling agent, preventing late responses from being processed.
2.  Introducing a mechanism for the calling agent to proactively send a cancellation request to the peer agent upon a timeout.

## 2. Goals

-   **Correctness**: Guarantee that a delegated peer task results in exactly one tool response within the calling agent's context (be it success, failure, or timeout). This will prevent duplicate or conflicting LLM re-triggers.
-   **Efficiency**: Proactively cancel timed-out tasks on peer agents to free up system resources (e.g., LLM calls, tool execution) and prevent orphaned processes.
-   **Resilience**: Make the A2A communication protocol more robust and predictable in environments with network latency or slow-responding agents.
-   **Observability**: Improve logging to provide a clear, traceable audit trail for timed-out and cancelled distributed tasks, which is critical for debugging.

## 3. Requirements

### Functional Requirements

1.  **Calling Agent Timeout Behavior**: When a delegated task to a peer agent times out, the calling agent **MUST**:
    a. Immediately generate a synthetic "timeout error" tool response for its internal processing.
    b. Invalidate the original sub-task ID to ensure any subsequent late response from the peer is ignored.
    c. Re-trigger its internal LLM loop with the synthetic timeout response.
    d. Send a `CancelTaskRequest` message to the peer agent for the corresponding sub-task ID.

2.  **Peer Agent Cancellation**: A peer agent **MUST** correctly handle an incoming `CancelTaskRequest` and attempt to gracefully terminate the specified task.

3.  **Late Response Handling**: The calling agent **MUST** silently discard any response from a peer agent that corresponds to a sub-task ID that has already timed out and been invalidated.

### Non-Functional Requirements

1.  **State Management**: The process of handling a timeout (generating a local response and invalidating the sub-task ID) must be atomic to prevent race conditions.
2.  **Logging**: The system must produce clear, warning-level logs for timeout events, cancellation requests sent to peers, and ignored late responses.
3.  **Performance**: The proposed changes must not introduce significant performance overhead to the standard (non-timeout) task execution path.

## 4. Decisions

1.  **State Invalidation Strategy**
    -   **Decision**: The primary mechanism for invalidating a timed-out sub-task will be the **explicit and immediate removal of its correlation data from the cache**.
    -   **Reasoning**: The cache is the source of truth for mapping a `sub_task_id` back to the calling agent's context. Removing this data upon timeout is the most direct and effective way to ensure a late response cannot be processed. This is a clean, state-driven approach that avoids complex logic in the response handler.

2.  **Cancellation Responsibility**
    -   **Decision**: The **calling agent's `SamAgentComponent`** is responsible for initiating the `CancelTaskRequest` upon detecting a timeout via a cache expiry event.
    -   **Reasoning**: The calling agent is the component that manages the timeout timer (via the cache) and holds all the necessary context for the peer task (target agent name, sub-task ID). It is the only component with enough information to initiate the cancellation correctly.

3.  **Handling of Late Responses**
    -   **Decision**: Late responses for which the correlation data has been removed will be **acknowledged and silently ignored**. A warning-level log message will be generated to aid in debugging, but no error will be thrown and the message will not be NACKed.
    -   **Reasoning**: The task has already been finalized (as a timeout) on the calling agent's side. Processing the late response would violate the "single completion" principle. NACKing the message could cause unnecessary redelivery attempts for a message that is no longer relevant. Acknowledging it and logging a warning is the cleanest way to discard it permanently.
