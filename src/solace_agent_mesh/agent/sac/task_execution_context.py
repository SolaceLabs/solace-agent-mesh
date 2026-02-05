"""
Encapsulates the runtime state for a single, in-flight agent task.
"""

import asyncio
import threading
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from solace_ai_connector.common.message import Message as SolaceMessage


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
        self.is_paused: bool = False  # Track if task is paused waiting for peer/auth

        # Token usage tracking
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cached_input_tokens: int = 0
        self.token_usage_by_model: Dict[str, Dict[str, int]] = {}
        self.token_usage_by_source: Dict[str, Dict[str, int]] = {}

        # Generic flags storage for task-level state
        self._flags: Dict[str, Any] = {}

        # Generic security storage (enterprise use only)
        self._security_context: Dict[str, Any] = {}

        # Original Solace message for ACK/NACK operations
        # Stored here instead of a2a_context to avoid serialization issues
        self._original_solace_message: Optional["SolaceMessage"] = None

        # Turn tracking for proper spacing between LLM turns
        self._current_invocation_id: Optional[str] = None
        self._first_text_seen_in_turn: bool = False
        self._need_spacing_before_next_text: bool = False

    def cancel(self) -> None:
        """Signals that the task should be cancelled."""
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        """Checks if the cancellation event has been set."""
        return self.cancellation_event.is_set()

    def set_paused(self, paused: bool) -> None:
        """
        Marks the task as paused (waiting for peer response or user input).

        Args:
            paused: True if task is paused, False if resuming.
        """
        with self.lock:
            self.is_paused = paused

    def get_is_paused(self) -> bool:
        """
        Checks if the task is currently paused.

        Returns:
            True if task is paused (waiting for peer/auth), False otherwise.
        """
        with self.lock:
            return self.is_paused

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

    def record_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        source: str = "agent",
        tool_name: Optional[str] = None,
        cached_input_tokens: int = 0,
    ) -> None:
        """
        Records token usage for an LLM call.
        
        Args:
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.
            model: Model identifier used for this call.
            source: Source of the LLM call ("agent" or "tool").
            tool_name: Tool name if source is "tool".
            cached_input_tokens: Number of cached input tokens (optional).
        """
        with self.lock:
            # Update totals
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cached_input_tokens += cached_input_tokens
            
            # Track by model
            if model not in self.token_usage_by_model:
                self.token_usage_by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cached_input_tokens": 0,
                }
            self.token_usage_by_model[model]["input_tokens"] += input_tokens
            self.token_usage_by_model[model]["output_tokens"] += output_tokens
            self.token_usage_by_model[model]["cached_input_tokens"] += cached_input_tokens
            
            # Track by source
            source_key = f"{source}:{tool_name}" if tool_name else source
            if source_key not in self.token_usage_by_source:
                self.token_usage_by_source[source_key] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cached_input_tokens": 0,
                }
            self.token_usage_by_source[source_key]["input_tokens"] += input_tokens
            self.token_usage_by_source[source_key]["output_tokens"] += output_tokens
            self.token_usage_by_source[source_key]["cached_input_tokens"] += cached_input_tokens

    def get_token_usage_summary(self) -> Dict[str, Any]:
        """
        Returns a summary of all token usage for this task.
        
        Returns:
            Dictionary containing total token counts and breakdowns by model and source.
        """
        with self.lock:
            return {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cached_input_tokens": self.total_cached_input_tokens,
                "total_tokens": self.total_input_tokens + self.total_output_tokens,
                "by_model": dict(self.token_usage_by_model),
                "by_source": dict(self.token_usage_by_source),
            }
    
    def set_security_data(self, key: str, value: Any) -> None:
        """
        Store opaque security data (enterprise use only).
        
        This method provides a secure storage mechanism for enterprise security features
        such as authentication tokens. The stored data is isolated per task and
        automatically cleaned up when the task completes.
        
        Args:
            key: Storage key for the security data
            value: Security data to store (opaque to open source code)
        """
        with self.lock:
            self._security_context[key] = value
    
    def get_security_data(self, key: str, default: Any = None) -> Any:
        """
        Retrieve opaque security data (enterprise use only).
        
        This method retrieves security data that was previously stored using
        set_security_data(). The data is opaque to open source code.
        
        Args:
            key: Storage key for the security data
            default: Default value to return if key not found
            
        Returns:
            The stored security data, or default if not found
        """
        with self.lock:
            return self._security_context.get(key, default)
    
    def clear_security_data(self) -> None:
        """
        Clear all security data.

        This method is provided for completeness but is not explicitly called.
        Security data is automatically cleaned up when the TaskExecutionContext
        is removed from active_tasks and garbage collected.
        """
        with self.lock:
            self._security_context.clear()

    def set_original_solace_message(self, message: Optional["SolaceMessage"]) -> None:
        """
        Store the original Solace message for this task.

        This message is used for ACK/NACK operations when the task completes.
        Stored separately from a2a_context to avoid serialization issues when
        the context is persisted to the ADK session state.

        Args:
            message: The Solace message that initiated this task, or None
        """
        with self.lock:
            self._original_solace_message = message

    def get_original_solace_message(self) -> Optional["SolaceMessage"]:
        """
        Retrieve the original Solace message for this task.

        Returns:
            The Solace message that initiated this task, or None if not available
        """
        with self.lock:
            return self._original_solace_message

    def check_and_update_invocation(self, new_invocation_id: str) -> bool:
        """
        Check if this is a new turn (different invocation_id) and update tracking.

        Args:
            new_invocation_id: The invocation_id from the current ADK event

        Returns:
            True if this is a new turn (invocation_id changed), False otherwise
        """
        with self.lock:
            is_new_turn = (
                self._current_invocation_id is not None
                and self._current_invocation_id != new_invocation_id
            )

            if is_new_turn:
                # Mark that we need spacing before the next text
                self._need_spacing_before_next_text = True

            if is_new_turn or self._current_invocation_id is None:
                self._current_invocation_id = new_invocation_id
                self._first_text_seen_in_turn = False

            return is_new_turn

    def is_first_text_in_turn(self) -> bool:
        """
        Check if this is the first text we're seeing in the current turn,
        and mark it as seen.

        Returns:
            True if this is the first text in the turn, False otherwise
        """
        with self.lock:
            if not self._first_text_seen_in_turn:
                self._first_text_seen_in_turn = True
                return True
            return False

    def should_add_turn_spacing(self) -> bool:
        """
        Check if we need to add spacing before the next text (because it's a new turn).
        This flag is set when a new invocation starts and cleared after spacing is added.

        Returns:
            True if spacing should be added, False otherwise
        """
        with self.lock:
            if self._need_spacing_before_next_text:
                self._need_spacing_before_next_text = False
                return True
            return False

    def set_flag(self, key: str, value: Any) -> None:
        """
        Set a task-level flag.

        This method provides a generic mechanism for storing task-level state
        that needs to persist across different parts of the task execution.

        Args:
            key: The flag name
            value: The flag value
        """
        with self.lock:
            self._flags[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        """
        Get a task-level flag.

        Args:
            key: The flag name
            default: Default value to return if flag not found

        Returns:
            The flag value, or default if not found
        """
        with self.lock:
            return self._flags.get(key, default)
