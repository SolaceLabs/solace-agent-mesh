# Implementation Plan: Atomic Peer Task Handling via Centralized State

## 1. Introduction
This document outlines the step-by-step plan to implement the architecturally improved design for robust peer agent task timeout handling. The core of this plan is to refactor the system to centralize all sub-task state within the `TaskExecutionContext`, thereby enabling true atomic operations and eliminating race conditions.

## 2. Implementation Steps

### Step 1: Enhance `TaskExecutionContext` for Sub-Task Management
**Goal**: Make `TaskExecutionContext` the single source of truth for its in-flight peer sub-tasks.

1.  **File to modify**: `src/agent/sac/task_execution_context.py`
2.  **Action: Update State Attributes**:
    -   Add the new dictionary attribute: `self.active_peer_sub_tasks: Dict[str, Dict[str, Any]] = {}`.
    -   Remove the now-deprecated list attribute: `self.peer_sub_tasks`.
3.  **Action: Implement `register_peer_sub_task`**:
    -   Create a new method: `def register_peer_sub_task(self, sub_task_id: str, correlation_data: Dict[str, Any]) -> None:`.
    -   Inside a `with self.lock:` block, add the `correlation_data` to the `self.active_peer_sub_tasks` dictionary, using `sub_task_id` as the key.
4.  **Action: Implement `claim_sub_task_completion`**:
    -   Create a new method: `def claim_sub_task_completion(self, sub_task_id: str) -> Optional[Dict[str, Any]]:`.
    -   Inside a `with self.lock:` block, use `self.active_peer_sub_tasks.pop(sub_task_id, None)` to atomically retrieve and remove the sub-task's correlation data.
    -   Return the result of the `.pop()` call.
5.  **Action: Remove old `register_peer_sub_task`**:
    -   The existing `register_peer_sub_task` method will be replaced by the new one defined above.

### Step 2: Update `PeerAgentTool` to Use New Context Methods
**Goal**: Adapt the peer tool to register sub-tasks with the `TaskExecutionContext` and use the cache only for timeout tracking.

1.  **File to modify**: `src/agent/tools/peer_agent_tool.py`
2.  **Method**: `run_async`
3.  **Action: Update Sub-Task Registration**:
    -   After creating the `correlation_data` dictionary, call the new registration method: `task_context_obj.register_peer_sub_task(sub_task_id, correlation_data)`.
4.  **Action: Update Cache Usage**:
    -   Modify the call to `self.host_component.cache_service.add_data`.
    -   The `value` argument should now be `main_logical_task_id`, not the full `correlation_data` dictionary.
5.  **Action: Remove old registration call**:
    -   Remove the call to the old `register_peer_sub_task` method.

### Step 3: Refactor `handle_a2a_response` for Atomic Claiming
**Goal**: Rewrite the response handler to use the new atomic workflow.

1.  **File to modify**: `src/agent/protocol/event_handlers.py`
2.  **Method**: `handle_a2a_response`
3.  **Action: Implement New Atomic Workflow**:
    -   Extract `sub_task_id` from the topic as before.
    -   Call `logical_task_id = component.cache_service.remove_data(sub_task_id)`. This action serves as the first part of the atomic claim, preventing a timeout from being processed if the response is handled first.
    -   If `logical_task_id` is `None`, log a warning that the task likely timed out and `return`.
    -   Retrieve the `task_context` using the `logical_task_id`.
    -   Call `correlation_data = task_context.claim_sub_task_completion(sub_task_id)`.
    -   If `correlation_data` is `None`, log a warning about the race condition (the timeout event was processed first) and `return`.
    -   If `correlation_data` is successfully retrieved, proceed with the existing logic for handling the peer response.

### Step 4: Refactor Timeout Handling in `SamAgentComponent`
**Goal**: Update the component's timeout handler to use the new atomic workflow.

1.  **File to modify**: `src/agent/sac/component.py`
2.  **Method**: `handle_cache_expiry_event`
3.  **Action: Update Event Handling Logic**:
    -   The `expired_data` from the `cache_data` event will now be the `logical_task_id`.
    -   Retrieve the `task_context` using this `logical_task_id`.
    -   Call `correlation_data = task_context.claim_sub_task_completion(sub_task_id)`.
    -   If `correlation_data` is `None`, log that the response was processed first and `return`.
    -   If `correlation_data` is successfully claimed, call `self._handle_peer_timeout(sub_task_id, correlation_data)`.
4.  **Method**: `_handle_peer_timeout`
5.  **Action: Simplify Method**:
    -   This method now receives the `correlation_data` directly.
    -   Remove any logic that retrieves data from the cache or task context.
    -   The method should now directly proceed with sending the `CancelTaskRequest` and then processing the timeout locally.

### Step 5: Update Task Cancellation Logic
**Goal**: Ensure that task cancellation correctly propagates to all active peer sub-tasks.

1.  **File to modify**: `src/agent/adk/runner.py`
2.  **Method**: `run_adk_async_task_thread_wrapper`
3.  **Action: Update Sub-Task Iteration**:
    -   In the `except TaskCancelledError` block, find the loop that iterates over sub-tasks to cancel.
    -   Change the iteration from `for sub_task_info in task_context.peer_sub_tasks:` to `for sub_task_id, sub_task_info in task_context.active_peer_sub_tasks.items():`.
    -   Update the logic inside the loop to correctly extract `sub_task_id` and `peer_agent_name` from the new structure.

### Step 6: Final Review
**Goal**: Ensure all refactored parts integrate correctly.
1.  **Action**: Perform a final code review of all modified files to check for consistency and correctness according to the new design.
2.  **Action**: Manually trace the execution path for both a successful response and a timeout to confirm that the new atomic logic holds.
