"""
Workflow execution context and state management.
"""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowExecutionState(BaseModel):
    """State stored in ADK session for workflow execution."""

    # Identification
    workflow_name: str
    execution_id: str
    start_time: datetime

    # Current execution status
    current_node_id: Optional[str] = None
    completed_nodes: Dict[str, str] = Field(
        default_factory=dict
    )  # node_id -> artifact_name
    pending_nodes: List[str] = Field(default_factory=list)

    # Implicit parallel branch tracking
    # Maps parallel_group_id -> list of (node_id, branch_index) tuples
    # Used to track which nodes are in which branch of an implicit parallel group
    parallel_branch_assignments: Dict[str, Dict[str, int]] = Field(
        default_factory=dict
    )  # parallel_group_id -> {node_id: branch_index}

    # Map node tracking (for dynamic fan-out)
    active_branches: Dict[str, List[Dict]] = Field(
        default_factory=dict
    )  # map_node_id -> branch info

    # LoopNode iteration tracking
    # loop_node_id -> current iteration count
    loop_iterations: Dict[str, int] = Field(default_factory=dict)

    # Retry tracking
    # node_id -> current retry attempt count
    retry_counts: Dict[str, int] = Field(default_factory=dict)

    # Skipped nodes (by conditional/when clause)
    # node_id -> reason for skip
    skipped_nodes: Dict[str, str] = Field(default_factory=dict)

    # Error tracking
    error_state: Optional[Dict[str, Any]] = None

    # Cached node outputs for value resolution
    node_outputs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict
    )  # node_id -> {"output": data}

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class WorkflowExecutionContext:
    """Context for tracking a workflow execution."""

    def __init__(self, workflow_task_id: str, a2a_context: Dict):
        self.workflow_task_id = workflow_task_id
        self.a2a_context = a2a_context
        self.workflow_state: Optional[WorkflowExecutionState] = None

        # Sub-task tracking
        self.sub_task_to_node: Dict[str, str] = {}  # sub_task_id -> node_id
        self.node_to_sub_task: Dict[str, str] = {}  # node_id -> sub_task_id
        self.lock = threading.Lock()
        self.cancellation_event = threading.Event()

        # Original Solace message for ACK/NACK operations
        # Stored here instead of a2a_context to avoid serialization issues
        self._original_solace_message: Optional[Any] = None

    def track_agent_call(self, node_id: str, sub_task_id: str):
        """Track correlation between node and sub-task."""
        with self.lock:
            self.sub_task_to_node[sub_task_id] = node_id
            self.node_to_sub_task[node_id] = sub_task_id

    def get_node_id_for_sub_task(self, sub_task_id: str) -> Optional[str]:
        """Get node ID for a sub-task."""
        with self.lock:
            return self.sub_task_to_node.get(sub_task_id)

    def get_sub_task_for_node(self, node_id: str) -> Optional[str]:
        """Get sub-task ID for a node."""
        with self.lock:
            return self.node_to_sub_task.get(node_id)

    def get_all_sub_task_ids(self) -> List[str]:
        """Get all tracked sub-task IDs."""
        with self.lock:
            return list(self.sub_task_to_node.keys())

    def cancel(self):
        """Signal cancellation."""
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self.cancellation_event.is_set()

    def set_original_solace_message(self, message: Any):
        """Store the original Solace message for ACK operations."""
        self._original_solace_message = message

    def get_original_solace_message(self) -> Optional[Any]:
        """Retrieve the original Solace message."""
        return self._original_solace_message
