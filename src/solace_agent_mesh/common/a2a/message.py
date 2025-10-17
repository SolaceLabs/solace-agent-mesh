"""
Helpers for creating and consuming A2A Message and Part objects.
"""

import base64
import uuid
from typing import Any, Dict, List, Optional, Union

from .types import ContentPart
from a2a.types import (
    DataPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
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
    part_metadata: Optional[Dict[str, Any]] = None,
) -> Message:
    """
    Creates a new agent message containing a single DataPart.

    Args:
        data: The structured data content of the message.
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.
        part_metadata: Optional metadata for the DataPart.

    Returns:
        A new `Message` object with role 'agent'.
    """
    data_part = DataPart(data=data, metadata=part_metadata)
    return Message(
        role=Role.agent,
        parts=[Part(root=data_part)],
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        kind="message",
    )


def create_agent_parts_message(
    parts: List[ContentPart],
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    message_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Message:
    """
    Creates a new agent message containing a list of Parts.

    Args:
        parts: The list of content `Part` objects (e.g. TextPart, DataPart).
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.
        metadata: Optional metadata for the message.

    Returns:
        A new `Message` object with role 'agent'.
    """
    wrapped_parts = [Part(root=p) for p in parts]
    return Message(
        role=Role.agent,
        parts=wrapped_parts,
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        metadata=metadata,
        kind="message",
    )


def create_user_message(
    parts: List[ContentPart],
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
    message_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Message:
    """
    Creates a new user message containing a list of Parts.

    Args:
        parts: The list of content `Part` objects (e.g. TextPart, DataPart).
        task_id: The task ID for the message.
        context_id: The context ID for the message.
        message_id: The message ID. If None, a new UUID is generated.
        metadata: Optional metadata for the message.

    Returns:
        A new `Message` object with role 'user'.
    """
    wrapped_parts = [Part(root=p) for p in parts]
    return Message(
        role=Role.user,
        parts=wrapped_parts,
        message_id=message_id or str(uuid.uuid4().hex),
        task_id=task_id,
        context_id=context_id,
        metadata=metadata,
        kind="message",
    )


def create_text_part(text: str, metadata: Optional[Dict[str, Any]] = None) -> TextPart:
    """Creates a TextPart object."""
    return TextPart(text=text, metadata=metadata)


def create_file_part_from_uri(
    uri: str,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> FilePart:
    """Creates a FilePart object from a URI."""
    file_content = FileWithUri(uri=uri, name=name, mime_type=mime_type)
    return FilePart(file=file_content, metadata=metadata)


def create_file_part_from_bytes(
    content_bytes: bytes,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> FilePart:
    """Creates a FilePart object from bytes."""
    encoded_bytes = base64.b64encode(content_bytes).decode("utf-8")
    file_content = FileWithBytes(bytes=encoded_bytes, name=name, mime_type=mime_type)
    return FilePart(file=file_content, metadata=metadata)


def create_data_part(
    data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
) -> DataPart:
    """Creates a DataPart object."""
    return DataPart(data=data, metadata=metadata)


def update_message_parts(message: Message, new_parts: List[ContentPart]) -> Message:
    """Returns a new Message with its parts replaced."""
    wrapped_parts = [Part(root=p) for p in new_parts]
    return message.model_copy(update={"parts": wrapped_parts})


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


def get_parts_from_message(message: Message) -> List[ContentPart]:
    """
    Extracts the raw, unwrapped Part objects (TextPart, DataPart, etc.) from a Message.

    Args:
        message: The `Message` object.

    Returns:
        A list of the unwrapped content parts.
    """
    return [part.root for part in message.parts]


def get_text_from_text_part(part: TextPart) -> str:
    """Safely retrieves the text from a TextPart object."""
    return part.text


def get_data_from_data_part(part: DataPart) -> Dict[str, Any]:
    """Safely retrieves the data dictionary from a DataPart object."""
    return part.data


def get_metadata_from_part(part: ContentPart) -> Optional[Dict[str, Any]]:
    """Safely retrieves the metadata from any Part object."""
    return part.metadata


def get_file_from_file_part(
    part: FilePart,
) -> Optional[Union[FileWithUri, FileWithBytes]]:
    """Safely retrieves the File object from a FilePart."""
    return part.file


def get_uri_from_file_part(part: FilePart) -> Optional[str]:
    """Safely retrieves the URI from a FilePart, if it exists."""
    if isinstance(part.file, FileWithUri):
        return part.file.uri
    return None


def get_bytes_from_file_part(part: FilePart) -> Optional[bytes]:
    """Safely retrieves and decodes the bytes from a FilePart, if they exist."""
    if isinstance(part.file, FileWithBytes) and part.file.bytes:
        try:
            return base64.b64decode(part.file.bytes)
        except (TypeError, ValueError):
            return None
    return None


def get_filename_from_file_part(part: FilePart) -> Optional[str]:
    """Safely retrieves the filename from a FilePart."""
    return part.file.name


def get_mimetype_from_file_part(part: FilePart) -> Optional[str]:
    """Safely retrieves the MIME type from a FilePart."""
    return part.file.mime_type


# --- Type Checking Helpers ---


def is_text_part(part: Part) -> bool:
    """
    Checks if a Part contains a TextPart.

    Args:
        part: The Part object to check.

    Returns:
        True if the part contains a TextPart, False otherwise.
    """
    return isinstance(part.root, TextPart)


def is_file_part(part: Part) -> bool:
    """
    Checks if a Part contains a FilePart.

    Args:
        part: The Part object to check.

    Returns:
        True if the part contains a FilePart, False otherwise.
    """
    return isinstance(part.root, FilePart)


def is_data_part(part: Part) -> bool:
    """
    Checks if a Part contains a DataPart.

    Args:
        part: The Part object to check.

    Returns:
        True if the part contains a DataPart, False otherwise.
    """
    return isinstance(part.root, DataPart)


def is_file_part_bytes(part: FilePart) -> bool:
    """
    Checks if a FilePart uses FileWithBytes (embedded content).

    Args:
        part: The FilePart object to check.

    Returns:
        True if the file content is embedded as bytes, False otherwise.
    """
    return isinstance(part.file, FileWithBytes)


def is_file_part_uri(part: FilePart) -> bool:
    """
    Checks if a FilePart uses FileWithUri (reference to external content).

    Args:
        part: The FilePart object to check.

    Returns:
        True if the file content is a URI reference, False otherwise.
    """
    return isinstance(part.file, FileWithUri)
