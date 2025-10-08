"""
Helpers for creating and consuming A2A Task objects.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from a2a.types import (
    Artifact,
    Message,
    Task,
    TaskState,
    TaskStatus,
)


# --- Creation Helpers ---


def create_initial_task(
    task_id: str,
    context_id: str,
    agent_name: str,
) -> Task:
    """
    Creates an initial Task object, typically for returning to a client
    after a task has been submitted.

    Args:
        task_id: The unique ID for the task.
        context_id: The context/session ID for the task.
        agent_name: The name of the agent handling the task.

    Returns:
        A new `Task` object with 'submitted' status.
    """
    initial_status = TaskStatus(state=TaskState.submitted)
    return Task(
        id=task_id,
        context_id=context_id,
        status=initial_status,
        kind="task",
        metadata={"agent_name": agent_name},
    )


def create_task_status(
    state: TaskState,
    message: Optional[Message] = None,
) -> TaskStatus:
    """
    Creates a TaskStatus object.

    Args:
        state: The state of the task.
        message: An optional message providing more details.

    Returns:
        A new `TaskStatus` object with a current timestamp.
    """
    return TaskStatus(
        state=state,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def create_final_task(
    task_id: str,
    context_id: str,
    final_status: TaskStatus,
    artifacts: Optional[List[Artifact]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Task:
    """
    Creates a final Task object, typically for sending as a final response.

    Args:
        task_id: The unique ID for the task.
        context_id: The context/session ID for the task.
        final_status: The final status of the task (e.g., completed, failed).
        artifacts: A list of artifacts produced by the task.
        metadata: Optional metadata to include in the task.

    Returns:
        A new `Task` object representing the final state.
    """
    return Task(
        id=task_id,
        context_id=context_id,
        status=final_status,
        artifacts=artifacts,
        metadata=metadata,
        kind="task",
    )


# --- Consumption Helpers ---


def get_task_id(task: Task) -> str:
    """Safely retrieves the ID from a Task object."""
    return task.id


def get_task_context_id(task: Task) -> str:
    """Safely retrieves the context ID from a Task object."""
    return task.context_id


def get_task_status(task: Task) -> TaskState:
    """Safely retrieves the state from a Task's status."""
    return task.status.state


def get_task_history(task: Task) -> Optional[List[Message]]:
    """Safely retrieves the history from a Task object."""
    return task.history


def get_task_artifacts(task: Task) -> Optional[List[Artifact]]:
    """Safely retrieves the artifacts from a Task object."""
    return task.artifacts


def get_task_metadata(task: Task) -> Optional[Dict[str, Any]]:
    """Safely retrieves the metadata from a Task object."""
    return task.metadata
