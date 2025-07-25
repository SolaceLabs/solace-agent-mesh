# Implementation Checklist: Robust Peer Agent Task Timeout Handling

This checklist provides a granular, trackable set of tasks to implement the robust peer agent task timeout handling feature. It aligns directly with the steps outlined in the implementation plan.

## 2. Prerequisites

- [ ] **Verify Cache Interface**: Confirm that the `BaseCacheService` implementation provides an atomic `remove_data(key)` method that returns the removed value or `None`.

## 3. Implementation Steps

### Step 1: Augment Correlation Data

- [x] **1. Modify `src/agent/tools/peer_agent_tool.py`**:
    - [x] **1.1. In `run_async` method**:
        - [x] Add the key-value pair `"peer_agent_name": self.target_agent_name` to the `correlation_data` dictionary.

### Step 2: Implement Atomic Response Handling

- [x] **2. Modify `src/agent/protocol/event_handlers.py`**:
    - [x] **2.1. In `handle_a2a_response` method**:
        - [x] Change the call from `component.cache_service.get_data(sub_task_id)` to `component.cache_service.remove_data(sub_task_id)`.
        - [x] Update the warning log message for the `if not correlation_data:` block to reflect that the task may have timed out.

### Step 3: Implement Proactive Task Cancellation on Timeout

- [x] **3. Modify `src/agent/sac/component.py`**:
    - [x] **3.1. Add Imports**:
        - [x] Add `from ...common.types import CancelTaskRequest, TaskIdParams`.
    - [x] **3.2. Modify `_handle_peer_timeout` method**:
        - [x] **a. Log Timeout**: Existing logging is sufficient.
        - [x] **b. Atomic Removal**: This is handled by the combination of `handle_a2a_response` using `remove_data` and the cache service deleting on expiry. No change needed here.
        - [x] **c. Send Cancellation**:
            - [x] Extract `peer_agent_name` from the correlation data.
            - [x] Construct the `CancelTaskRequest` payload.
            - [x] Construct the peer's request topic.
            - [x] Publish the cancellation message using `self._publish_a2a_message`.
            - [x] Wrap the publishing logic in a `try...except` block.
        - [x] **d. Process Locally**: The existing logic to process the timeout locally runs after the new cancellation logic.

### Step 4: Final Review and Testing

- [ ] **4.1. Code Review**:
    - [ ] Review all modified files against the design document to ensure all requirements have been met.
- [ ] **4.2. Testing**:
    - [ ] **Happy Path**: Execute a peer tool call that completes successfully and verify correct behavior.
    - [ ] **Timeout Path**:
        - [ ] Simulate a slow peer agent to trigger a timeout.
        - [ ] Verify the calling agent logs the timeout and continues execution with a synthetic error.
        - [ ] Verify a `CancelTaskRequest` is sent to the peer.
        - [ ] Verify the peer agent receives and acts on the cancellation.
    - [ ] **Race Condition**:
        - [ ] Simulate a peer responding immediately after a timeout has been processed.
        - [ ] Verify the calling agent logs a warning and ignores the late response.
