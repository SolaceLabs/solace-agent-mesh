# Implementation Checklist: Robust Peer Agent Task Timeout Handling

This checklist provides a granular, trackable set of tasks to implement the robust peer agent task timeout handling feature. It aligns directly with the steps outlined in the implementation plan.

## 2. Prerequisites

- [ ] **Verify Cache Interface**: Confirm that the `BaseCacheService` implementation provides an atomic `remove_data(key)` method that returns the removed value or `None`.

## 3. Implementation Steps

### Step 1: Augment Correlation Data

- [ ] **1. Modify `src/agent/tools/peer_agent_tool.py`**:
    - [ ] **1.1. In `run_async` method**:
        - [ ] Add the key-value pair `"peer_agent_name": self.target_agent_name` to the `correlation_data` dictionary.

### Step 2: Implement Atomic Response Handling

- [ ] **2. Modify `src/agent/protocol/event_handlers.py`**:
    - [ ] **2.1. In `handle_a2a_response` method**:
        - [ ] Change the call from `component.cache_service.get_data(sub_task_id)` to `component.cache_service.remove_data(sub_task_id)`.
        - [ ] Update the warning log message for the `if not correlation_data:` block to reflect that the task may have timed out.

### Step 3: Implement Proactive Task Cancellation on Timeout

- [ ] **3. Modify `src/agent/sac/component.py`**:
    - [ ] **3.1. Add Imports**:
        - [ ] Add `from ...common.types import CancelTaskRequest, TaskIdParams`.
    - [ ] **3.2. Modify `_handle_peer_timeout` method**:
        - [ ] **a. Log Timeout**: Add logging to indicate a peer timeout has been detected.
        - [ ] **b. Atomic Removal**: Change the logic to call `self.cache_service.remove_data(sub_task_id)` instead of just receiving `correlation_data` as a parameter. Add a check to gracefully exit if `remove_data` returns `None`.
        - [ ] **c. Send Cancellation**:
            - [ ] Extract `peer_agent_name` from the removed correlation data.
            - [ ] Construct the `CancelTaskRequest` payload.
            - [ ] Construct the peer's request topic.
            - [ ] Publish the cancellation message using `self._publish_a2a_message`.
            - [ ] Wrap the publishing logic in a `try...except` block.
        - [ ] **d. Process Locally**: Ensure the existing logic to process the timeout locally (calling `task_context.handle_peer_timeout` and `_retrigger_agent_with_peer_responses`) runs *after* the cancellation logic.

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
