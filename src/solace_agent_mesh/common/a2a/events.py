"""
Helpers for creating and consuming A2A asynchronous event objects, such as
TaskStatusUpdateEvent and TaskArtifactUpdateEvent.
"""

from typing import Any, Dict, List, Optional

from a2a.types import (
    Artifact,
    DataPart,
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from . import message as message_helpers
from . import task as task_helpers
from ...common.data_parts import SignalData


# --- Creation Helpers ---


def create_data_signal_event(
    task_id: str,
    context_id: str,
    signal_data: SignalData,
    agent_name: str,
    part_metadata: Optional[Dict[str, Any]] = None,
) -> TaskStatusUpdateEvent:
    """
    Creates a TaskStatusUpdateEvent from a specific signal data model.

    This is a generalized helper that takes any of the defined SignalData
    types and wraps it in the full A2A event structure.

    Args:
        task_id: The ID of the task being updated.
        context_id: The context ID for the task.
        signal_data: The Pydantic model for the signal (e.g., ToolInvocationStartData).
        agent_name: The name of the agent sending the signal.
        part_metadata: Optional metadata for the DataPart.

    Returns:
        A new `TaskStatusUpdateEvent` object containing the signal.
    """
    a2a_message = message_helpers.create_agent_data_message(
        data=signal_data.model_dump(),
        task_id=task_id,
        context_id=context_id,
        part_metadata=part_metadata,
    )
    return create_status_update(
        task_id=task_id,
        context_id=context_id,
        message=a2a_message,
        is_final=False,
        metadata={"agent_name": agent_name},
    )


def create_status_update(
    task_id: str,
    context_id: str,
    message: Message,
    is_final: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    state: TaskState = TaskState.working,
) -> TaskStatusUpdateEvent:
    """
    Creates a new TaskStatusUpdateEvent.

    Args:
        task_id: The ID of the task being updated.
        context_id: The context ID for the task.
        message: The A2AMessage object containing the status details.
        is_final: Whether this is the final update for the task.
        metadata: Optional metadata for the event.

    Returns:
        A new `TaskStatusUpdateEvent` object.
    """
    task_status = task_helpers.create_task_status(
        state=state,
        message=message,
    )
    return TaskStatusUpdateEvent(
        task_id=task_id,
        context_id=context_id,
        status=task_status,
        final=is_final,
        metadata=metadata,
        kind="status-update",
    )


def create_artifact_update(
    task_id: str,
    context_id: str,
    artifact: Artifact,
    append: bool = False,
    last_chunk: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> TaskArtifactUpdateEvent:
    """
    Creates a new TaskArtifactUpdateEvent.

    Args:
        task_id: The ID of the task this artifact belongs to.
        context_id: The context ID for the task.
        artifact: The Artifact object being sent.
        append: If true, the content should be appended to a previous artifact.
        last_chunk: If true, this is the final chunk of the artifact.
        metadata: Optional metadata for the event.

    Returns:
        A new `TaskArtifactUpdateEvent` object.
    """
    return TaskArtifactUpdateEvent(
        task_id=task_id,
        context_id=context_id,
        artifact=artifact,
        append=append,
        last_chunk=last_chunk,
        metadata=metadata,
        kind="artifact-update",
    )


# --- Consumption Helpers ---


def get_message_from_status_update(
    event: TaskStatusUpdateEvent,
) -> Optional[Message]:
    """
    Safely extracts the Message object from a TaskStatusUpdateEvent.

    Args:
        event: The TaskStatusUpdateEvent object.

    Returns:
        The `Message` object if present, otherwise None.
    """
    if event and event.status:
        return event.status.message
    return None


def get_data_parts_from_status_update(
    event: TaskStatusUpdateEvent,
) -> List[DataPart]:
    """
    Safely extracts all DataPart objects from a TaskStatusUpdateEvent's message.

    Args:
        event: The TaskStatusUpdateEvent object.

    Returns:
        A list of `DataPart` objects found, or an empty list.
    """
    message = get_message_from_status_update(event)
    if not message:
        return []

    return message_helpers.get_data_parts_from_message(message)


def get_artifact_from_artifact_update(
    event: TaskArtifactUpdateEvent,
) -> Optional[Artifact]:
    """
    Safely extracts the Artifact object from a TaskArtifactUpdateEvent.

    Args:
        event: The TaskArtifactUpdateEvent object.

    Returns:
        The `Artifact` object if present, otherwise None.
    """
    if event:
        return event.artifact
    return None


# --- Type Checking Helpers ---


def is_task_status_update(obj: Any) -> bool:
    """
    Checks if an object is a TaskStatusUpdateEvent.

    Args:
        obj: The object to check.

    Returns:
        True if the object is a TaskStatusUpdateEvent, False otherwise.
    """
    return isinstance(obj, TaskStatusUpdateEvent)


def is_task_artifact_update(obj: Any) -> bool:
    """
    Checks if an object is a TaskArtifactUpdateEvent.

    Args:
        obj: The object to check.

    Returns:
        True if the object is a TaskArtifactUpdateEvent, False otherwise.
    """
    return isinstance(obj, TaskArtifactUpdateEvent)
