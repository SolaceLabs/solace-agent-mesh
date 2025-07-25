# Implementation Plan: Robust Peer Agent Task Timeout Handling

## 1. Introduction
This document outlines the step-by-step plan to implement the robust peer agent task timeout handling feature, as specified in the detailed design document. The implementation focuses on atomically handling sub-task completion to prevent race conditions and adding proactive task cancellation for timed-out peer requests.

## 2. Prerequisites
Before starting implementation, ensure the following is in place:
- The `BaseCacheService` interface and its implementations (e.g., `InMemoryCache`) must provide a method `remove_data(key: str) -> Optional[Any]` that atomically removes a key from the cache and returns its value. If the key does not exist, it should return `None`. This is critical for solving the race condition.

## 3. Implementation Steps

### Step 1: Augment Correlation Data
**Goal**: Provide the timeout handler with the necessary information to cancel the peer task.
1.  **File to modify**: `src/agent/tools/peer_agent_tool.py`
2.  **Method**: `run_async`
3.  **Action**: In the `correlation_data` dictionary, add a new key-value pair: `"peer_agent_name": self.target_agent_name`.

### Step 2: Implement Atomic Response Handling
**Goal**: Prevent the race condition between a late response and a timeout event by making the response handler "claim" the sub-task.
1.  **File to modify**: `src/agent/protocol/event_handlers.py`
2.  **Method**: `handle_a2a_response`
3.  **Action**:
    -   Change the line `correlation_data = component.cache_service.get_data(sub_task_id)` to `correlation_data = component.cache_service.remove_data(sub_task_id)`.
    -   Update the log message in the `if not correlation_data:` block to: `"%s No correlation data found for sub-task %s. The task may have timed out or already completed. Ignoring late response."`

### Step 3: Implement Proactive Task Cancellation on Timeout
**Goal**: When a timeout occurs, send a `CancelTaskRequest` to the peer agent.
1.  **File to modify**: `src/agent/sac/component.py`
2.  **Action 1: Add Imports**: At the top of the file, add the following import: `from ...common.types import CancelTaskRequest, TaskIdParams`.
3.  **Action 2: Modify `_handle_peer_timeout`**:
    -   The method signature is `async def _handle_peer_timeout(self, sub_task_id: str, correlation_data: Dict[str, Any]):`.
    -   Inside this method, before the existing logic that processes the timeout locally, add a new block to send the cancellation request.
    -   This new block should:
        a. Extract `peer_agent_name` from `correlation_data`.
        b. If `peer_agent_name` exists:
            i. Log the intent to send a cancellation request.
            ii. Construct the `CancelTaskRequest` payload. The `params` will be a `TaskIdParams` object where `id` is the `sub_task_id` (without the `CORRELATION_DATA_PREFIX`).
            iii. Construct the `user_properties` for the message.
            iv. Determine the peer's request topic using `self._get_agent_request_topic(peer_agent_name)`.
            v. Call `self._publish_a2a_message` to send the cancellation request.
        c. Wrap this entire block in a `try...except` statement to log any errors during cancellation without interrupting the local timeout processing.

### Step 4: Final Review and Testing
**Goal**: Ensure all changes work together as intended.
1.  **Review**: Manually review all modified files against the design and implementation plan.
2.  **Testing**:
    -   **Happy Path**: Verify that normal peer-to-peer tool calls complete successfully.
    -   **Timeout Path**:
        -   Create a test scenario where a peer agent is slow to respond, forcing a timeout.
        -   Verify that the calling agent logs the timeout, processes a synthetic error response, and continues its execution.
        -   Verify that the calling agent sends a `CancelTaskRequest` to the slow peer.
        -   Verify that the slow peer receives and processes the `CancelTaskRequest`.
    -   **Race Condition**:
        -   Create a test scenario where a peer responds just after the timeout period.
        -   Verify that the calling agent processes only the timeout and correctly ignores the late response with a warning log.
