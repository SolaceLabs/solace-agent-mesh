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

    # Fork/join tracking
    active_branches: Dict[str, List[Dict]] = Field(
        default_factory=dict
    )  # fork_id -> branch info

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

    def track_persona_call(self, node_id: str, sub_task_id: str):
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

    def cancel(self):
        """Signal cancellation."""
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self.cancellation_event.is_set()
