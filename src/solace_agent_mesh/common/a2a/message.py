"""
Helpers for creating and consuming A2A Message and Part objects.
"""
import uuid
from typing import Any, List, Optional

from a2a.types import (
    DataPart,
    FilePart,
    Message,
    Part,
    Role,
    TextPart,
)
from a2a.utils import message as message_sdk_utils


# --- Creation Helpers ---


def create_agent_text_message(
    text: str,
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> Message:
    """
    Creates a new agent message containing a single TextPart.

    Args:
        text: The text content of the message.
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.

    Returns:
        A new `Message` object with role 'agent'.
    """
    return Message(
        role=Role.agent,
        parts=[Part(root=TextPart(text=text))],
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        kind="message",
    )


def create_agent_data_message(
    data: dict[str, Any],
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> Message:
    """
    Creates a new agent message containing a single DataPart.

    Args:
        data: The structured data content of the message.
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.

    Returns:
        A new `Message` object with role 'agent'.
    """
    data_part = DataPart(data=data)
    return Message(
        role=Role.agent,
        parts=[Part(root=data_part)],
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        kind="message",
    )


def create_user_message(
    parts: List[Part],
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> Message:
    """
    Creates a new user message containing a list of Parts.

    Args:
        parts: The list of `Part` objects for the message content.
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.

    Returns:
        A new `Message` object with role 'user'.
    """
    return Message(
        role=Role.user,
        parts=parts,
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        kind="message",
    )


# --- Consumption Helpers ---


def get_text_from_message(message: Message, delimiter: str = "\n") -> str:
    """
    Extracts and joins all text content from a Message's parts.

    Args:
        message: The `Message` object.
        delimiter: The string to use when joining text from multiple TextParts.

    Returns:
        A single string containing all text content, or an empty string if no text parts are found.
    """
    return message_sdk_utils.get_message_text(message, delimiter=delimiter)


def get_data_parts_from_message(message: Message) -> List[DataPart]:
    """
    Extracts DataPart objects from a Message's parts.

    Args:
        message: The `Message` object.

    Returns:
        A list of `DataPart` objects found.
    """
    return [part.root for part in message.parts if isinstance(part.root, DataPart)]


def get_file_parts_from_message(message: Message) -> List[FilePart]:
    """
    Extracts FilePart objects from a Message's parts.

    Args:
        message: The `Message` object.

    Returns:
        A list of `FilePart` objects found.
    """
    return [part.root for part in message.parts if isinstance(part.root, FilePart)]


def get_message_id(message: Message) -> str:
    """Safely retrieves the ID from a Message object."""
    return message.message_id


def get_context_id(message: Message) -> Optional[str]:
    """Safely retrieves the context ID from a Message object."""
    return message.context_id


def get_task_id(message: Message) -> Optional[str]:
    """Safely retrieves the task ID from a Message object."""
    return message.task_id
