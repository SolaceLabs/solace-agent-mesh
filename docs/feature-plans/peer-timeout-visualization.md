# Peer Timeout Visualization Implementation Plan

## 1. Overview

The goal is to correctly visualize a sub-agent (peer) timeout event in the frontend flow chart. Currently, a timeout can cause subsequent LLM calls to be misattributed because the parent agent's "wakeup" to handle the timeout is not represented by a new node.

This plan addresses the issue by treating a timeout as a specific type of "tool result" event, which allows us to reuse existing logic for creating new parent agent nodes and ensures correct visual attribution.

## 2. Implementation Steps

### Phase 1: Backend - Send Status Event on Timeout

Create and send a dedicated status event when a sub-agent (peer) call times out. This signal will contain all necessary details for the frontend to correctly visualize the timeout.

**File:** `src/solace_agent_mesh/agent/sac/component.py`

1.  **Create `_publish_peer_timeout_status` method:**
    *   This new asynchronous method will be responsible for constructing and publishing the `peer_task_timeout` status update.
    *   It will construct a `DataPart` containing all the details the frontend needs: `a2a_signal_type`, `error_message`, `peer_agent_name`, `sub_task_id`, `function_call_id`, and `parent_agent_name`.
    *   It will wrap this in a `TaskStatusUpdateEvent` and publish it using the `_publish_status_update_with_buffer_flush` helper, ensuring any buffered text is sent first.

    ```python
    # Method to be added to SamAgentComponent
    async def _publish_peer_timeout_status(
        self, sub_task_id: str, correlation_data: Dict[str, Any]
    ):
        """
        Publishes an intermediate status update indicating a peer tool call has timed out.
        """
        logical_task_id = correlation_data.get("logical_task_id")
        peer_agent_name = correlation_data.get("peer_agent_name")
        adk_function_call_id = correlation_data.get("adk_function_call_id")
        a2a_context = correlation_data.get("original_task_context")

        if not all([logical_task_id, peer_agent_name, a2a_context]):
            return

        timeout_value = self.inter_agent_communication_config.get(
            "request_timeout_seconds", DEFAULT_COMMUNICATION_TIMEOUT
        )
        error_message = f"Request to peer agent '{peer_agent_name}' timed out after {timeout_value} seconds."

        try:
            timeout_data_part = DataPart(
                data={
                    "a2a_signal_type": "peer_task_timeout",
                    "error_message": error_message,
                    "peer_agent_name": peer_agent_name,
                    "sub_task_id": sub_task_id,
                    "function_call_id": adk_function_call_id,
                    "parent_agent_name": self.get_config("agent_name"),
                }
            )

            status_message = A2AMessage(role="agent", parts=[timeout_data_part])
            intermediate_status = TaskStatus(
                state=TaskState.WORKING,
                message=status_message,
                timestamp=datetime.now(timezone.utc),
            )

            status_update_event = TaskStatusUpdateEvent(
                id=logical_task_id,
                status=intermediate_status,
                final=False,
                metadata={"agent_name": self.get_config("agent_name")},
            )

            await self._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=False,
            )
        except Exception as e:
            log.error("Failed to publish peer timeout status: %s", e)
    ```

2.  **Call the new method from `_handle_peer_timeout`:**
    *   In the existing `_handle_peer_timeout` method, add a call to `await self._publish_peer_timeout_status(...)` at the beginning. This ensures the status event is sent immediately upon timeout detection, before any other recovery logic is executed.

    ```python
    # Inside _handle_peer_timeout
    async def _handle_peer_timeout(
        self,
        sub_task_id: str,
        correlation_data: Dict[str, Any],
    ):
        ...
        log.warning(...)

        await self._publish_peer_timeout_status(sub_task_id, correlation_data) # This line needs to be added

        # Proactively send a cancellation request to the peer agent.
        ...
    ```

### Phase 2: Frontend - Process Timeout Signal

The frontend needs to recognize the new timeout signal and transform it into a standard `AGENT_TOOL_EXECUTION_RESULT` visualizer step.

**File:** `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts`

1.  **Update `processTaskForVisualization`:**
    *   Inside the main event processing loop, detect status updates that contain a `DataPart` with `a2a_signal_type: "peer_task_timeout"`.
    *   When this signal is found, create a `VisualizerStep` with `type: "AGENT_TOOL_EXECUTION_RESULT"`.
    *   Populate the `data.toolResult` field using information from the signal:
        *   `toolName`: Construct from `peer_agent_name` (e.g., `peer_AgentB`).
        *   `functionCallId`: Use from the signal.
        *   `resultData`: Create an error object (e.g., `{ "error": "timeout message..." }`).
        *   `isPeerResponse`: Set to `true`.
        *   `isTimeout`: Add this new flag and set it to `true`.

### Phase 3: Frontend - Visualize the Timeout

The visualization logic will now receive the timeout as a standard tool result, allowing us to leverage existing code while adding specific styling for the timeout case.

**File:** `client/webui/frontend/src/lib/components/activities/FlowChart/taskToFlowData.ts`

1.  **Update `handleToolExecutionResult`:**
    *   The existing logic will correctly create a new node for the parent agent, solving the node attribution problem.
    *   Add a check for the `step.data.toolResult.isTimeout` flag.
    *   If `isTimeout` is true, call a new helper function `createErrorEdge(...)` instead of `createTimelineEdge(...)`.
    *   Also in this function, add the sub-task ID to a new set in the `TimelineLayoutManager` called `timedOutSubTaskIds`.

2.  **Update `handleTaskFailed`:**
    *   Refactor this function to also use the new `createErrorEdge` helper for consistency in rendering failure/error paths.

### Phase 4: Frontend - Final Touches and State Management

This involves creating the new edge helper and managing the state of timed-out tasks to prevent late events from appearing.

**File:** `client/webui/frontend/src/lib/components/activities/FlowChart/taskToFlowData.helpers.ts`

1.  **Create `createErrorEdge` function:**
    *   This function will be a copy of `createTimelineEdge`.
    *   It will set `isError: true` in the edge's `data` payload, which the `GenericFlowEdge` component can use to render a visually distinct (e.g., red, dashed) edge.
    *   It will also set the edge `label` to "Timeout" or "Error".

**File:** `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts`

1.  **Add `timedOutSubTaskIds` to `TimelineLayoutManager`:**
    *   This will be a `Set<string>` to hold the IDs of tasks that have timed out.

2.  **Update `processTaskForVisualization`:**
    *   At the very beginning of the event processing loop, add a check: if an event's `owningTaskId` is present in the `timedOutSubTaskIds` set, `continue` to the next event, effectively ignoring it. This prevents late-arriving status updates or results from a timed-out sub-agent from cluttering the final visualization.
