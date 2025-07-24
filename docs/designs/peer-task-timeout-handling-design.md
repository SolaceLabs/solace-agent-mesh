# Detailed Design: Robust Peer Agent Task Timeout Handling

## 1. Introduction

This document provides the detailed technical design for implementing robust timeout handling for peer-to-peer agent communication. It builds upon the approved feature proposal (`docs/proposals/peer-task-timeout-handling.md`) and specifies the exact code modifications required to fix the identified race condition and resource leak.

## 2. Overview of Changes

The implementation will modify three key areas of the A2A agent framework:

1.  **Peer Tool (`peer_agent_tool.py`)**: The `correlation_data` stored in the cache for a peer task will be augmented to include the target agent's name.
2.  **Agent Component (`component.py`)**: The `_handle_peer_timeout` method will be significantly enhanced to atomically handle the timeout, send a cancellation request to the peer, and then process the timeout locally.
3.  **Event Handlers (`event_handlers.py`)**: The logging in the A2A response handler will be improved to provide clearer information when ignoring late responses from timed-out tasks.

## 3. Detailed Design

### 3.1. `src/agent/tools/peer_agent_tool.py`

-   **File**: `src/agent/tools/peer_agent_tool.py`
-   **Method**: `run_async`
-   **Change**: The `correlation_data` dictionary will be updated to include the `target_agent_name`. This is essential for the timeout handler to know which agent to send a cancellation request to.

    -   **Current `correlation_data`**:
        ```python
        correlation_data = {
            "adk_function_call_id": tool_context.function_call_id,
            "original_task_context": original_task_context,
            "peer_tool_name": self.name,
            "logical_task_id": main_logical_task_id,
            "invocation_id": invocation_id,
        }
        ```
    -   **New `correlation_data`**:
        ```python
        correlation_data = {
            "adk_function_call_id": tool_context.function_call_id,
            "original_task_context": original_task_context,
            "peer_tool_name": self.name,
            "peer_agent_name": self.target_agent_name, # <-- ADD THIS
            "logical_task_id": main_logical_task_id,
            "invocation_id": invocation_id,
        }
        ```

### 3.2. `src/agent/sac/component.py`

-   **File**: `src/agent/sac/component.py`
-   **Method**: `_handle_peer_timeout`
-   **Change**: This method will be rewritten to orchestrate the new timeout logic. The existing logic for local processing will be preserved but will be executed after the new cancellation steps.

    -   **New Method Logic**:
        1.  **Log the Timeout**: Log the timeout event with the `sub_task_id`.
        2.  **Atomically Remove Correlation Data**:
            -   Call `self.cache_service.remove_data(sub_task_id)` to immediately invalidate the sub-task. This is the critical step to prevent a late response from being processed. The `remove_data` method should return the value that was removed.
            -   If `remove_data` returns `None`, it means the task was already processed (e.g., a response arrived just before the timeout event). In this case, log this race condition and exit the handler gracefully.
        3.  **Send `CancelTaskRequest` to Peer**:
            -   Extract `peer_agent_name` from the (now removed) `correlation_data`.
            -   If `peer_agent_name` is present, construct a `CancelTaskRequest` payload.
            -   The `params` will be a `TaskIdParams` object containing the `sub_task_id` (after stripping the `CORRELATION_DATA_PREFIX`).
            -   Publish this request to the peer agent's request topic using `self._publish_a2a_message`. The topic can be constructed using `self._get_agent_request_topic(peer_agent_name)`.
            -   Wrap this step in a `try...except` block to handle potential publishing errors gracefully.
        4.  **Process Timeout Locally**:
            -   This part reuses the existing logic.
            -   Extract `logical_task_id` and `invocation_id` from the `correlation_data`.
            -   Find the `TaskExecutionContext` for the `logical_task_id`.
            -   Call `task_context.handle_peer_timeout(...)` to generate the synthetic error response.
            -   If `handle_peer_timeout` indicates all parallel calls are complete, call `self._retrigger_agent_with_peer_responses(...)` to continue the agent's execution.

-   **Imports**: Add the following imports to the top of `src/agent/sac/component.py`:
    ```python
    from ...common.types import CancelTaskRequest, TaskIdParams
    ```

### 3.3. `src/agent/protocol/event_handlers.py`

-   **File**: `src/agent/protocol/event_handlers.py`
-   **Method**: `handle_a2a_response`
-   **Change**: The existing logic for handling missing correlation data is correct. The change is to improve the log message to make it clearer that a timeout is the likely cause.

    -   **Current Logic Snippet**:
        ```python
        correlation_data = component.cache_service.get_data(sub_task_id)
        if not correlation_data:
            log.warning(
                "%s No correlation data found for sub-task %s. Cannot process response. Ignoring.",
                component.log_identifier,
                sub_task_id,
            )
            message.call_acknowledgements()
            return
        ```
    -   **Proposed Change**: Modify the log message.
        ```python
        correlation_data = component.cache_service.get_data(sub_task_id)
        if not correlation_data:
            log.warning(
                "%s No correlation data found for sub-task %s. The task may have timed out or already completed. Ignoring late response.", # <-- MODIFIED LOG
                component.log_identifier,
                sub_task_id,
            )
            message.call_acknowledgements()
            return
        ```

## 4. Data Structures

The `correlation_data` dictionary stored in the cache by `PeerAgentTool` will be modified to include one new key:

-   `peer_agent_name` (str): The name of the target agent for the delegated task.

## 5. Error Handling

-   **Late Peer Response**: Handled by `handle_a2a_response`. The removal of correlation data on timeout ensures the late response is safely ignored with a warning log.
-   **Cancellation Publish Failure**: The attempt to send a `CancelTaskRequest` in `_handle_peer_timeout` will be wrapped in a `try...except` block. A failure to send the cancellation will be logged as an error, but it will not prevent the calling agent from processing the timeout locally. The primary goal of correctness in the calling agent is maintained.
-   **Peer Fails to Cancel**: The A2A protocol does not guarantee task cancellation. The peer agent will attempt to cancel, but if it fails, it will continue processing. However, its final response will be ignored by the calling agent, so the system state remains correct.

## 6. Out of Scope

-   This design does not introduce a guaranteed-delivery mechanism for `CancelTaskRequest` messages. It is a "best-effort" notification.
-   This design does not change the core ADK runner logic, only the A2A hosting layer around it.
