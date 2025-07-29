"""
Encapsulates the runtime state for a single, in-flight agent task.
"""

import asyncio
import threading
from typing import Any, Dict, List, Optional


class TaskExecutionContext:
    """
    A class to hold all runtime state and control mechanisms for a single agent task.
    This object is created when a task is initiated and destroyed when it completes,
    ensuring that all state is properly encapsulated and cleaned up.
    """

    def __init__(self, task_id: str, a2a_context: Dict[str, Any]):
        """
        Initializes the TaskExecutionContext.

        Args:
            task_id: The unique logical ID of the task.
            a2a_context: The original, rich context dictionary from the A2A request.
        """
        self.task_id: str = task_id
        self.a2a_context: Dict[str, Any] = a2a_context
        self.cancellation_event: asyncio.Event = asyncio.Event()
        self.streaming_buffer: str = ""
        self.run_based_response_buffer: str = ""
        self.active_peer_sub_tasks: Dict[str, Dict[str, Any]] = {}
        self.parallel_tool_calls: Dict[str, Dict[str, Any]] = {}
        self.produced_artifacts: List[Dict[str, Any]] = []
        self.artifact_signals_to_return: List[Dict[str, Any]] = []
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.lock: threading.Lock = threading.Lock()

    def cancel(self) -> None:
        """Signals that the task should be cancelled."""
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        """Checks if the cancellation event has been set."""
        return self.cancellation_event.is_set()

    def append_to_streaming_buffer(self, text: str) -> None:
        """Appends a chunk of text to the main streaming buffer."""
        with self.lock:
            self.streaming_buffer += text

    def flush_streaming_buffer(self) -> str:
        """Returns the entire content of the streaming buffer and clears it."""
        with self.lock:
            content = self.streaming_buffer
            self.streaming_buffer = ""
            return content

    def get_streaming_buffer_content(self) -> str:
        """Returns the current buffer content without clearing it."""
        with self.lock:
            return self.streaming_buffer

    def append_to_run_based_buffer(self, text: str) -> None:
        """Appends a chunk of processed text to the run-based response buffer."""
        with self.lock:
            self.run_based_response_buffer += text

    def register_peer_sub_task(
        self, sub_task_id: str, correlation_data: Dict[str, Any]
    ) -> None:
        """Adds a new peer sub-task's correlation data to the tracking dictionary."""
        with self.lock:
            self.active_peer_sub_tasks[sub_task_id] = correlation_data

    def claim_sub_task_completion(self, sub_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Atomically retrieves and removes a sub-task's correlation data.
        This is the core atomic operation to prevent race conditions.
        Returns the correlation data if the claim is successful, otherwise None.
        """
        with self.lock:
            return self.active_peer_sub_tasks.pop(sub_task_id, None)

    def register_parallel_call_sent(self, invocation_id: str) -> None:
        """
        Registers that a new parallel tool call has been sent for a specific invocation.
        Initializes the tracking dictionary for the invocation if it's the first call,
        otherwise increments the total.
        """
        with self.lock:
            if invocation_id not in self.parallel_tool_calls:
                self.parallel_tool_calls[invocation_id] = {
                    "total": 1,
                    "completed": 0,
                    "results": [],
                }
            else:
                self.parallel_tool_calls[invocation_id]["total"] += 1

    def handle_peer_timeout(
        self,
        sub_task_id: str,
        correlation_data: Dict,
        timeout_sec: int,
        invocation_id: str,
    ) -> bool:
        """
        Handles a timeout for a specific peer sub-task for a given invocation.

        Updates the parallel call tracker with a formatted error message and returns
        True if all peer calls for that invocation are now complete.

        Args:
            sub_task_id: The ID of the sub-task that timed out.
            correlation_data: The correlation data associated with the sub-task.
            timeout_sec: The timeout duration in seconds.
            invocation_id: The ID of the invocation that initiated the parallel calls.

        Returns:
            A boolean indicating if all parallel calls for the invocation are now complete.
        """
        peer_tool_name = correlation_data.get("peer_tool_name", "unknown_tool")
        timeout_message = f"Request to peer agent tool '{peer_tool_name}' timed out after {timeout_sec} seconds."

        # The payload must be a dictionary with a 'result' key containing the simple string.
        # This ensures the ADK framework presents it to the LLM as a simple text response.
        simple_error_payload = {"result": timeout_message}

        current_result = {
            "adk_function_call_id": correlation_data.get("adk_function_call_id"),
            "peer_tool_name": peer_tool_name,
            "payload": simple_error_payload,
        }
        return self.record_parallel_result(current_result, invocation_id)

    def record_parallel_result(self, result: Dict, invocation_id: str) -> bool:
        """
        Records a result for a parallel tool call for a specific invocation
        and returns True if all calls for that invocation are now complete.
        """
        with self.lock:
            invocation_state = self.parallel_tool_calls.get(invocation_id)
            if not invocation_state:
                # This can happen if a response arrives after a timeout has cleaned up.
                return False

            invocation_state["results"].append(result)
            invocation_state["completed"] += 1
            return invocation_state["completed"] >= invocation_state["total"]

    def clear_parallel_invocation_state(self, invocation_id: str) -> None:
        """
        Removes the state for a completed parallel tool call invocation.
        """
        with self.lock:
            if invocation_id in self.parallel_tool_calls:
                del self.parallel_tool_calls[invocation_id]

    def register_produced_artifact(self, filename: str, version: int) -> None:
        """Adds a newly created artifact to the tracking list."""
        with self.lock:
            self.produced_artifacts.append({"filename": filename, "version": version})

    def add_artifact_signal(self, signal: Dict[str, Any]) -> None:
        """Adds an artifact return signal to the list in a thread-safe manner."""
        with self.lock:
            self.artifact_signals_to_return.append(signal)

    def get_and_clear_artifact_signals(self) -> List[Dict[str, Any]]:
        """
        Retrieves all pending artifact signals and clears the list atomically.
        """
        with self.lock:
            signals = list(self.artifact_signals_to_return)  # Create a copy
            self.artifact_signals_to_return.clear()
            return signals

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Stores a reference to the task's event loop."""
        with self.lock:
            self.event_loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Retrieves the stored event loop."""
        with self.lock:
            return self.event_loop
