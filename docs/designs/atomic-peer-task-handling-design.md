# Detailed Design: Atomic Peer Task Timeout Handling via Centralized State

## 1. Introduction

This document provides the detailed technical design for a significant architectural enhancement to the peer-to-peer agent communication framework. It supersedes the previous design and addresses a critical race condition that occurs when a peer task response and a timeout event are processed concurrently.

The root cause of the issue is that the state for an in-flight peer task (the `correlation_data`) is stored in a global cache, separate from the main task's state. This design proposes to **centralize all sub-task state within the parent `TaskExecutionContext` object**. This allows for true atomic operations on sub-task completion, completely eliminating the race condition.

## 2. Overview of Changes

This refactoring will touch four key areas to achieve a robust, state-centralized model:

1.  **`TaskExecutionContext`**: This class will become the single source of truth for all in-flight peer sub-tasks. It will be enhanced with new state and methods to manage the sub-task lifecycle atomically.
2.  **`PeerAgentTool`**: The tool will be updated to register sub-tasks directly with the `TaskExecutionContext` and will use the `CacheService` only for simple timeout tracking.
3.  **`event_handlers.py` (`handle_a2a_response`)**: The response handler will be rewritten to use the new atomic methods on `TaskExecutionContext` to claim a sub-task's completion upon receiving a response.
4.  **`SamAgentComponent` (`handle_cache_expiry_event` and `_handle_peer_timeout`)**: The timeout handling logic will be updated to use the same atomic methods, ensuring that only the first event (response or timeout) is processed.

## 3. Detailed Design

### 3.1. `src/agent/sac/task_execution_context.py`

This class will be modified to manage the state of its own peer sub-tasks.

-   **New State Attribute**:
    -   A new dictionary will be added: `self.active_peer_sub_tasks: Dict[str, Dict[str, Any]] = {}`.
    -   This dictionary will store the full `correlation_data` for each active sub-task, keyed by its unique `sub_task_id`.

-   **Deprecated State Attribute**:
    -   The existing list `self.peer_sub_tasks` will be deprecated and removed, as its functionality is fully replaced by the new dictionary.

-   **New Method: `register_peer_sub_task`**:
    -   **Signature**: `def register_peer_sub_task(self, sub_task_id: str, correlation_data: Dict[str, Any]) -> None:`
    -   **Logic**: This method will acquire the context's lock and add the `correlation_data` to the `self.active_peer_sub_tasks` dictionary, keyed by `sub_task_id`.

-   **New Method: `claim_sub_task_completion`**:
    -   **Signature**: `def claim_sub_task_completion(self, sub_task_id: str) -> Optional[Dict[str, Any]]:`
    -   **Logic**: This is the core atomic operation.
        1.  Acquire the context's lock (`self.lock`).
        2.  Use `self.active_peer_sub_tasks.pop(sub_task_id, None)` to atomically remove and retrieve the `correlation_data`.
        3.  If data was popped, return it.
        4.  If `None` was returned (because the key didn't exist), it means the sub-task was already claimed. Return `None`.

### 3.2. `src/agent/tools/peer_agent_tool.py`

The peer tool will be updated to use the new `TaskExecutionContext` methods.

-   **Method**: `run_async`
-   **Changes**:
    1.  The `correlation_data` dictionary will be created as before (including `peer_agent_name`).
    2.  After retrieving the `task_context_obj`, it will call the new registration method: `task_context_obj.register_peer_sub_task(sub_task_id, correlation_data)`.
    3.  The call to `self.host_component.cache_service.add_data` will be modified. Instead of storing the entire `correlation_data` dictionary, it will store a simple mapping to the parent task's ID.
        -   **New Cache Entry**: `key=sub_task_id`, `value=main_logical_task_id`, `expiry=timeout_sec`.

### 3.3. `src/agent/protocol/event_handlers.py`

The response handler will be significantly refactored to use the new atomic workflow.

-   **Method**: `handle_a2a_response`
-   **New Logic**:
    1.  Extract `sub_task_id` from the incoming message topic.
    2.  **Atomically claim the response**: Call `component.cache_service.remove_data(sub_task_id)` to get the `logical_task_id`. This also prevents the timeout handler from processing this sub-task if the response is processed first.
    3.  If `remove_data` returns `None`, it means the task has already timed out. Log a warning and ignore the message.
    4.  If a `logical_task_id` is returned, retrieve the `TaskExecutionContext` from `component.active_tasks`.
    5.  If the `task_context` exists, call `correlation_data = task_context.claim_sub_task_completion(sub_task_id)`.
    6.  If `claim_sub_task_completion` returns `None`, it means the timeout handler claimed the task between the cache removal and this call. Log this specific race condition and ignore the message.
    7.  If `correlation_data` is successfully retrieved, proceed with the existing logic to process the peer response, update the parallel counters, and re-trigger the agent.

### 3.4. `src/agent/sac/component.py`

The component's timeout handling logic will be updated to use the new atomic workflow.

-   **Method**: `handle_cache_expiry_event`
-   **New Logic**:
    1.  The `cache_data` from the event will now contain `key=sub_task_id` and `expired_data=logical_task_id`.
    2.  Retrieve the `TaskExecutionContext` using the `logical_task_id`.
    3.  If the `task_context` exists, call `correlation_data = task_context.claim_sub_task_completion(sub_task_id)`.
    4.  If `claim_sub_task_completion` returns `None`, it means the response was processed first. Log this and exit gracefully.
    5.  If `correlation_data` is successfully claimed, proceed to call `self._handle_peer_timeout(sub_task_id, correlation_data)`.

-   **Method**: `_handle_peer_timeout`
-   **Changes**: This method's responsibility is now simplified, as the "claim" has already happened.
    1.  It receives the `correlation_data` as a parameter.
    2.  It proceeds directly to sending the `CancelTaskRequest` to the peer agent.
    3.  It then calls `task_context.handle_peer_timeout(...)` to generate the synthetic error for local processing.
    4.  Finally, it calls `_retrigger_agent_with_peer_responses` if all parallel calls for the invocation are complete.

## 4. Data Structures Summary

-   **`TaskExecutionContext.active_peer_sub_tasks`**: `Dict[str, Dict[str, Any]]`
    -   Example: `{"a2a_subtask_...": {"adk_function_call_id": ..., "peer_agent_name": ...}}`
-   **`CacheService` Entry**:
    -   `key`: `sub_task_id` (e.g., `"a2a_subtask_..."`)
    -   `value`: `logical_task_id` (e.g., `"task-12345"`)
    -   `expiry`: Timeout in seconds.

## 5. Conclusion

This design centralizes all in-flight task state within the `TaskExecutionContext`, enabling true atomic completion of sub-tasks. It eliminates the identified race condition, simplifies the global cache's role, and makes the entire peer-to-peer communication process more robust and easier to debug.
