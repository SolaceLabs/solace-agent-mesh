# Implementation Checklist: Atomic Peer Task Handling (v2)

This checklist provides a granular, trackable set of tasks to implement the revised atomic peer task handling feature. It aligns directly with the steps outlined in the v2 implementation plan.

## 2. Implementation Steps

### Step 1: Implement the Non-Destructive State Reader

- [x] **1.1. File to modify**: `src/agent/sac/component.py`
- [x] **1.2. Action: Create `_get_correlation_data_for_sub_task`**:
    - [x] Define a new `async` method: `_get_correlation_data_for_sub_task(self, sub_task_id: str) -> Optional[Dict[str, Any]]:`.
    - [x] Implement the logic to non-destructively read correlation data.

### Step 2: Implement the Destructive State Claimer

- [ ] **2.1. File to modify**: `src/agent/sac/component.py`
- [ ] **2.2. Action: Create `_claim_peer_sub_task_completion`**:
    - [ ] Define a new `async` method: `_claim_peer_sub_task_completion(self, sub_task_id: str) -> Optional[Dict[str, Any]]:`.
    - [ ] Implement the logic to atomically claim and remove sub-task state.

### Step 3: Refactor `handle_a2a_response` to Use New Helpers

- [ ] **3.1. File to modify**: `src/agent/protocol/event_handlers.py`
- [ ] **3.2. In `handle_a2a_response` method**:
    - [ ] **Update Intermediate Signal Handling**: Replace direct cache access with a call to `_get_correlation_data_for_sub_task`.
    - [ ] **Update Final Response Handling**: Replace state retrieval logic with a call to `_claim_peer_sub_task_completion`.

### Step 4: Refactor Timeout Handling to Use New Claimer

- [ ] **4.1. File to modify**: `src/agent/sac/component.py`
- [ ] **4.2. In `handle_cache_expiry_event` method**:
    - [ ] Replace state retrieval logic with a call to `_claim_peer_sub_task_completion`.
    - [ ] If successful, proceed to call `_handle_peer_timeout`.

### Step 5: Final Review

- [ ] **5.1. Code Review**:
    - [ ] Review all modified files against the v2 design document.
- [ ] **5.2. Manual Tracing**:
    - [ ] Trace execution paths for intermediate signals, final responses, and timeouts.
    - [ ] Verify race conditions are handled correctly.
