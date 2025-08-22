"""
Helpers for creating and consuming A2A asynchronous event objects, such as
TaskStatusUpdateEvent and TaskArtifactUpdateEvent.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from a2a.types import (
    Artifact,
    DataPart,
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

from . import message as message_helpers


# --- Creation Helpers ---


def create_status_update(
    task_id: str,
    context_id: str,
    message: Message,
    is_final: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
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
    task_status = TaskStatus(
        state=TaskState.working,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
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
