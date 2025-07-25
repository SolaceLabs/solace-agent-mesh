# Implementation Checklist: Atomic Peer Task Handling

This checklist provides a granular, trackable set of tasks to implement the atomic peer task handling feature. It aligns directly with the steps outlined in the implementation plan.

## 2. Implementation Steps

### Step 1: Enhance `TaskExecutionContext` for Sub-Task Management

- [x] **1.1. File to modify**: `src/agent/sac/task_execution_context.py`
- [x] **1.2. Update State Attributes**:
    - [x] Add the new dictionary attribute: `self.active_peer_sub_tasks: Dict[str, Dict[str, Any]] = {}`.
    - [x] Remove the deprecated list attribute: `self.peer_sub_tasks`.
- [x] **1.3. Implement `register_peer_sub_task`**:
    - [x] Create the new method `register_peer_sub_task` to add correlation data to `active_peer_sub_tasks` under a lock.
- [x] **1.4. Implement `claim_sub_task_completion`**:
    - [x] Create the new method `claim_sub_task_completion` to atomically pop the sub-task data from `active_peer_sub_tasks` under a lock.
- [x] **1.5. Remove old `register_peer_sub_task`**:
    - [x] Ensure the old `register_peer_sub_task` method is fully removed or replaced.

### Step 2: Update `PeerAgentTool` to Use New Context Methods

- [x] **2.1. File to modify**: `src/agent/tools/peer_agent_tool.py`
- [x] **2.2. In `run_async` method**:
    - [x] **Update Sub-Task Registration**: Call the new `task_context_obj.register_peer_sub_task` method.
    - [x] **Update Cache Usage**: Modify the `cache_service.add_data` call to store `main_logical_task_id` as the value.
    - [x] **Remove old registration call**: Ensure the old call to `register_peer_sub_task` is removed.

### Step 3: Refactor `handle_a2a_response` for Atomic Claiming

- [ ] **3.1. File to modify**: `src/agent/protocol/event_handlers.py`
- [ ] **3.2. In `handle_a2a_response` method**:
    - [ ] Implement the new atomic workflow:
        - [ ] Call `component.cache_service.remove_data(sub_task_id)` to get `logical_task_id`.
        - [ ] If `logical_task_id` is `None`, log a warning and return.
        - [ ] Retrieve the `task_context` using `logical_task_id`.
        - [ ] Call `task_context.claim_sub_task_completion(sub_task_id)` to get `correlation_data`.
        - [ ] If `correlation_data` is `None`, log a warning and return.
        - [ ] Proceed with the rest of the response handling logic.

### Step 4: Refactor Timeout Handling in `SamAgentComponent`

- [ ] **4.1. File to modify**: `src/agent/sac/component.py`
- [ ] **4.2. In `handle_cache_expiry_event` method**:
    - [ ] Update logic to expect `logical_task_id` as the `expired_data`.
    - [ ] Retrieve the `task_context` using `logical_task_id`.
    - [ ] Call `task_context.claim_sub_task_completion(sub_task_id)` to get `correlation_data`.
    - [ ] If `correlation_data` is `None`, log that the response was processed first and return.
    - [ ] If `correlation_data` is present, call `self._handle_peer_timeout(sub_task_id, correlation_data)`.
- [ ] **4.3. In `_handle_peer_timeout` method**:
    - [ ] Simplify the method to directly use the `correlation_data` passed as a parameter.
    - [ ] Ensure it proceeds directly to sending the `CancelTaskRequest` and processing the timeout locally.

### Step 5: Update Task Cancellation Logic

- [ ] **5.1. File to modify**: `src/agent/adk/runner.py`
- [ ] **5.2. In `run_adk_async_task_thread_wrapper` method**:
    - [ ] In the `except TaskCancelledError` block, find the loop for cancelling sub-tasks.
    - [ ] Change the iteration to use `task_context.active_peer_sub_tasks.items()`.
    - [ ] Update the logic inside the loop to correctly extract `sub_task_id` and `peer_agent_name` from the new dictionary structure.

### Step 6: Final Review

- [ ] **6.1. Code Review**:
    - [ ] Review all modified files against the design document.
- [ ] **6.2. Manual Tracing**:
    - [ ] Trace the execution path for a successful response.
    - [ ] Trace the execution path for a timeout.
    - [ ] Trace the execution path for the race condition (response arrives just before timeout is processed).
