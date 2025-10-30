"""
Unit tests for common/a2a/message.py
Tests helpers for creating and consuming A2A Message and Part objects.
"""

import pytest
from a2a.types import Message, TextPart, FilePart, DataPart, FileWithBytes, FileWithUri

from solace_agent_mesh.common.a2a.message import (
    create_agent_text_message,
    create_agent_data_message,
    create_agent_parts_message,
    create_user_message,
    create_text_part,
    create_file_part_from_uri,
    create_file_part_from_bytes,
    create_data_part,
    update_message_parts,
    get_text_from_message,
    get_data_parts_from_message,
    get_file_parts_from_message,
    get_message_id,
    get_context_id,
    get_task_id,
    get_parts_from_message,
    get_text_from_text_part,
    get_data_from_data_part,
    get_metadata_from_part,
    get_file_from_file_part,
    get_uri_from_file_part,
    get_bytes_from_file_part,
    get_filename_from_file_part,
    get_mimetype_from_file_part,
)


class TestCreateMessages:
    """Test message creation functions."""

    def test_create_agent_text_message_basic(self):
        """Test creating a basic agent text message."""
        message = create_agent_text_message("Hello, world!")
        
        assert message.role == "agent"
        assert len(message.parts) == 1
        assert message.parts[0].root.kind == "text"
        assert message.parts[0].root.text == "Hello, world!"
        assert message.message_id is not None

    def test_create_agent_text_message_with_ids(self):
        """Test creating agent text message with task and context IDs."""
        message = create_agent_text_message(
            "Test message",
            task_id="task-123",
            context_id="context-456",
            message_id="msg-789",
        )
        
        assert message.task_id == "task-123"
        assert message.context_id == "context-456"
        assert message.message_id == "msg-789"

    def test_create_agent_data_message_basic(self):
        """Test creating a basic agent data message."""
        data = {"key": "value", "number": 42}
        message = create_agent_data_message(data)
        
        assert message.role == "agent"
        assert len(message.parts) == 1
        assert message.parts[0].root.kind == "data"
        assert message.parts[0].root.data == data

    def test_create_agent_data_message_with_metadata(self):
        """Test creating agent data message with part metadata."""
        data = {"result": "success"}
        metadata = {"source": "test", "version": 1}
        message = create_agent_data_message(
            data,
            part_metadata=metadata,
        )
        
        assert message.parts[0].root.metadata == metadata

    def test_create_agent_parts_message(self):
        """Test creating agent message with multiple parts."""
        parts = [
            create_text_part("First part"),
            create_text_part("Second part"),
            create_data_part({"data": "value"}),
        ]
        message = create_agent_parts_message(parts)
        
        assert message.role == "agent"
        assert len(message.parts) == 3
        assert message.parts[0].root.text == "First part"
        assert message.parts[1].root.text == "Second part"
        assert message.parts[2].root.data == {"data": "value"}

    def test_create_agent_parts_message_with_metadata(self):
        """Test creating agent parts message with message metadata."""
        parts = [create_text_part("Test")]
        metadata = {"priority": "high"}
        message = create_agent_parts_message(parts, metadata=metadata)
        
        assert message.metadata == metadata

    def test_create_user_message(self):
        """Test creating a user message."""
        parts = [create_text_part("User input")]
        message = create_user_message(parts)
        
        assert message.role == "user"
        assert len(message.parts) == 1
        assert message.parts[0].root.text == "User input"

    def test_create_user_message_with_ids(self):
        """Test creating user message with IDs."""
        parts = [create_text_part("Test")]
        message = create_user_message(
            parts,
            task_id="task-abc",
            context_id="context-def",
            message_id="msg-ghi",
        )
        
        assert message.task_id == "task-abc"
        assert message.context_id == "context-def"
        assert message.message_id == "msg-ghi"


class TestCreateParts:
    """Test part creation functions."""

    def test_create_text_part_basic(self):
        """Test creating a basic text part."""
        part = create_text_part("Hello")
        
        assert part.kind == "text"
        assert part.text == "Hello"
        assert part.metadata is None

    def test_create_text_part_with_metadata(self):
        """Test creating text part with metadata."""
        metadata = {"language": "en", "confidence": 0.95}
        part = create_text_part("Hello", metadata=metadata)
        
        assert part.metadata == metadata

    def test_create_text_part_empty_string(self):
        """Test creating text part with empty string."""
        part = create_text_part("")
        assert part.text == ""

    def test_create_file_part_from_uri(self):
        """Test creating file part from URI."""
        part = create_file_part_from_uri(
            "https://example.com/file.pdf",
            name="document.pdf",
            mime_type="application/pdf",
        )
        
        assert part.kind == "file"
        assert isinstance(part.file, FileWithUri)
        assert part.file.uri == "https://example.com/file.pdf"
        assert part.file.name == "document.pdf"
        assert part.file.mime_type == "application/pdf"

    def test_create_file_part_from_uri_minimal(self):
        """Test creating file part from URI with minimal parameters."""
        part = create_file_part_from_uri("https://example.com/file.txt")
        
        assert part.file.uri == "https://example.com/file.txt"
        assert part.file.name is None
        assert part.file.mime_type is None

    def test_create_file_part_from_bytes(self):
        """Test creating file part from bytes."""
        content = b"Hello, world!"
        part = create_file_part_from_bytes(
            content,
            name="test.txt",
            mime_type="text/plain",
        )
        
        assert part.kind == "file"
        assert isinstance(part.file, FileWithBytes)
        assert part.file.name == "test.txt"
        assert part.file.mime_type == "text/plain"
        # Bytes are base64 encoded
        assert part.file.bytes is not None

    def test_create_file_part_from_bytes_minimal(self):
        """Test creating file part from bytes with minimal parameters."""
        content = b"test"
        part = create_file_part_from_bytes(content)
        
        assert isinstance(part.file, FileWithBytes)
        assert part.file.bytes is not None

    def test_create_data_part_basic(self):
        """Test creating a basic data part."""
        data = {"key": "value", "list": [1, 2, 3]}
        part = create_data_part(data)
        
        assert part.kind == "data"
        assert part.data == data
        assert part.metadata is None

    def test_create_data_part_with_metadata(self):
        """Test creating data part with metadata."""
        data = {"result": "ok"}
        metadata = {"schema_version": "1.0"}
        part = create_data_part(data, metadata=metadata)
        
        assert part.metadata == metadata

    def test_create_data_part_empty_dict(self):
        """Test creating data part with empty dictionary."""
        part = create_data_part({})
        assert part.data == {}


class TestMessageOperations:
    """Test message manipulation functions."""

    def test_update_message_parts(self):
        """Test updating message parts."""
        original = create_agent_text_message("Original")
        new_parts = [
            create_text_part("Updated"),
            create_data_part({"new": "data"}),
        ]
        
        updated = update_message_parts(original, new_parts)
        
        assert len(updated.parts) == 2
        assert updated.parts[0].root.text == "Updated"
        assert updated.parts[1].root.data == {"new": "data"}
        # Original message should be unchanged
        assert len(original.parts) == 1

    def test_update_message_parts_preserves_metadata(self):
        """Test that updating parts preserves message metadata."""
        original = create_agent_parts_message(
            [create_text_part("Test")],
            metadata={"important": True},
        )
        new_parts = [create_text_part("New")]
        
        updated = update_message_parts(original, new_parts)
        
        assert updated.metadata == {"important": True}


class TestGetMessageContent:
    """Test functions for extracting content from messages."""

    def test_get_text_from_message_single_part(self):
        """Test getting text from message with single text part."""
        message = create_agent_text_message("Hello")
        text = get_text_from_message(message)
        
        assert text == "Hello"

    def test_get_text_from_message_multiple_parts(self):
        """Test getting text from message with multiple text parts."""
        parts = [
            create_text_part("First"),
            create_text_part("Second"),
            create_text_part("Third"),
        ]
        message = create_agent_parts_message(parts)
        text = get_text_from_message(message)
        
        assert text == "First\nSecond\nThird"

    def test_get_text_from_message_custom_delimiter(self):
        """Test getting text with custom delimiter."""
        parts = [create_text_part("A"), create_text_part("B")]
        message = create_agent_parts_message(parts)
        text = get_text_from_message(message, delimiter=" | ")
        
        assert text == "A | B"

    def test_get_text_from_message_mixed_parts(self):
        """Test getting text from message with mixed part types."""
        parts = [
            create_text_part("Text1"),
            create_data_part({"data": "value"}),
            create_text_part("Text2"),
        ]
        message = create_agent_parts_message(parts)
        text = get_text_from_message(message)
        
        assert text == "Text1\nText2"

    def test_get_text_from_message_no_text_parts(self):
        """Test getting text from message with no text parts."""
        parts = [create_data_part({"data": "value"})]
        message = create_agent_parts_message(parts)
        text = get_text_from_message(message)
        
        assert text == ""

    def test_get_data_parts_from_message(self):
        """Test getting data parts from message."""
        parts = [
            create_text_part("Text"),
            create_data_part({"data1": "value1"}),
            create_data_part({"data2": "value2"}),
        ]
        message = create_agent_parts_message(parts)
        data_parts = get_data_parts_from_message(message)
        
        assert len(data_parts) == 2
        assert data_parts[0].data == {"data1": "value1"}
        assert data_parts[1].data == {"data2": "value2"}

    def test_get_data_parts_from_message_no_data(self):
        """Test getting data parts when there are none."""
        message = create_agent_text_message("Only text")
        data_parts = get_data_parts_from_message(message)
        
        assert data_parts == []

    def test_get_file_parts_from_message(self):
        """Test getting file parts from message."""
        parts = [
            create_text_part("Text"),
            create_file_part_from_uri("https://example.com/file1.pdf"),
            create_file_part_from_uri("https://example.com/file2.pdf"),
        ]
        message = create_agent_parts_message(parts)
        file_parts = get_file_parts_from_message(message)
        
        assert len(file_parts) == 2
        assert file_parts[0].file.uri == "https://example.com/file1.pdf"
        assert file_parts[1].file.uri == "https://example.com/file2.pdf"

    def test_get_file_parts_from_message_no_files(self):
        """Test getting file parts when there are none."""
        message = create_agent_text_message("Only text")
        file_parts = get_file_parts_from_message(message)
        
        assert file_parts == []


class TestGetMessageMetadata:
    """Test functions for extracting message metadata."""

    def test_get_message_id(self):
        """Test getting message ID."""
        message = create_agent_text_message("Test", message_id="msg-123")
        msg_id = get_message_id(message)
        
        assert msg_id == "msg-123"

    def test_get_context_id(self):
        """Test getting context ID."""
        message = create_agent_text_message("Test", context_id="ctx-456")
        ctx_id = get_context_id(message)
        
        assert ctx_id == "ctx-456"

    def test_get_context_id_none(self):
        """Test getting context ID when not set."""
        message = create_agent_text_message("Test")
        ctx_id = get_context_id(message)
        
        assert ctx_id is None

    def test_get_task_id(self):
        """Test getting task ID."""
        message = create_agent_text_message("Test", task_id="task-789")
        task_id = get_task_id(message)
        
        assert task_id == "task-789"

    def test_get_task_id_none(self):
        """Test getting task ID when not set."""
        message = create_agent_text_message("Test")
        task_id = get_task_id(message)
        
        assert task_id is None

    def test_get_parts_from_message(self):
        """Test getting unwrapped parts from message."""
        parts = [
            create_text_part("Text"),
            create_data_part({"data": "value"}),
        ]
        message = create_agent_parts_message(parts)
        extracted_parts = get_parts_from_message(message)
        
        assert len(extracted_parts) == 2
        assert extracted_parts[0].kind == "text"
        assert extracted_parts[1].kind == "data"


class TestGetPartContent:
    """Test functions for extracting content from parts."""

    def test_get_text_from_text_part(self):
        """Test getting text from text part."""
        part = create_text_part("Hello, world!")
        text = get_text_from_text_part(part)
        
        assert text == "Hello, world!"

    def test_get_data_from_data_part(self):
        """Test getting data from data part."""
        data = {"key": "value", "number": 42}
        part = create_data_part(data)
        extracted_data = get_data_from_data_part(part)
        
        assert extracted_data == data

    def test_get_metadata_from_part_text(self):
        """Test getting metadata from text part."""
        metadata = {"source": "test"}
        part = create_text_part("Test", metadata=metadata)
        extracted_metadata = get_metadata_from_part(part)
        
        assert extracted_metadata == metadata

    def test_get_metadata_from_part_none(self):
        """Test getting metadata when not set."""
        part = create_text_part("Test")
        metadata = get_metadata_from_part(part)
        
        assert metadata is None

    def test_get_file_from_file_part_uri(self):
        """Test getting file object from file part with URI."""
        part = create_file_part_from_uri("https://example.com/file.pdf")
        file_obj = get_file_from_file_part(part)
        
        assert file_obj is not None
        assert isinstance(file_obj, FileWithUri)
        assert file_obj.uri == "https://example.com/file.pdf"

    def test_get_file_from_file_part_bytes(self):
        """Test getting file object from file part with bytes."""
        part = create_file_part_from_bytes(b"content")
        file_obj = get_file_from_file_part(part)
        
        assert file_obj is not None
        assert isinstance(file_obj, FileWithBytes)

    def test_get_uri_from_file_part(self):
        """Test getting URI from file part."""
        part = create_file_part_from_uri("https://example.com/doc.pdf")
        uri = get_uri_from_file_part(part)
        
        assert uri == "https://example.com/doc.pdf"

    def test_get_uri_from_file_part_bytes(self):
        """Test getting URI from file part with bytes (should be None)."""
        part = create_file_part_from_bytes(b"content")
        uri = get_uri_from_file_part(part)
        
        assert uri is None

    def test_get_bytes_from_file_part(self):
        """Test getting decoded bytes from file part."""
        content = b"Hello, world!"
        part = create_file_part_from_bytes(content)
        decoded_bytes = get_bytes_from_file_part(part)
        
        assert decoded_bytes == content

    def test_get_bytes_from_file_part_uri(self):
        """Test getting bytes from file part with URI (should be None)."""
        part = create_file_part_from_uri("https://example.com/file.pdf")
        decoded_bytes = get_bytes_from_file_part(part)
        
        assert decoded_bytes is None

    def test_get_filename_from_file_part(self):
        """Test getting filename from file part."""
        part = create_file_part_from_uri(
            "https://example.com/file.pdf",
            name="document.pdf",
        )
        filename = get_filename_from_file_part(part)
        
        assert filename == "document.pdf"

    def test_get_filename_from_file_part_none(self):
        """Test getting filename when not set."""
        part = create_file_part_from_uri("https://example.com/file.pdf")
        filename = get_filename_from_file_part(part)
        
        assert filename is None

    def test_get_mimetype_from_file_part(self):
        """Test getting MIME type from file part."""
        part = create_file_part_from_bytes(
            b"content",
            mime_type="application/pdf",
        )
        mime_type = get_mimetype_from_file_part(part)
        
        assert mime_type == "application/pdf"

    def test_get_mimetype_from_file_part_none(self):
        """Test getting MIME type when not set."""
        part = create_file_part_from_bytes(b"content")
        mime_type = get_mimetype_from_file_part(part)
        
        assert mime_type is None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_message_parts(self):
        """Test creating message with empty parts list."""
        message = create_agent_parts_message([])
        
        assert len(message.parts) == 0
        assert message.role == "agent"

    def test_get_text_from_empty_message(self):
        """Test getting text from message with no parts."""
        message = create_agent_parts_message([])
        text = get_text_from_message(message)
        
        assert text == ""

    def test_large_text_content(self):
        """Test handling large text content."""
        large_text = "A" * 100000
        message = create_agent_text_message(large_text)
        
        assert len(message.parts[0].root.text) == 100000

    def test_complex_nested_data(self):
        """Test handling complex nested data structures."""
        complex_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "list": [1, 2, 3],
                        "dict": {"key": "value"},
                    }
                }
            },
            "array": [{"item": i} for i in range(10)],
        }
        message = create_agent_data_message(complex_data)
        
        assert message.parts[0].root.data == complex_data

    def test_unicode_text_content(self):
        """Test handling Unicode text content."""
        unicode_text = "Hello 世界 🌍 مرحبا"
        message = create_agent_text_message(unicode_text)
        
        assert message.parts[0].root.text == unicode_text

    def test_message_with_all_part_types(self):
        """Test message containing all part types."""
        parts = [
            create_text_part("Text content"),
            create_file_part_from_uri("https://example.com/file.pdf"),
            create_data_part({"data": "value"}),
        ]
        message = create_agent_parts_message(parts)
        
        assert len(message.parts) == 3
        assert message.parts[0].root.kind == "text"
        assert message.parts[1].root.kind == "file"
        assert message.parts[2].root.kind == "data"

    def test_multiple_file_parts_different_types(self):
        """Test message with both URI and bytes file parts."""
        parts = [
            create_file_part_from_uri("https://example.com/file1.pdf"),
            create_file_part_from_bytes(b"content"),
        ]
        message = create_agent_parts_message(parts)
        file_parts = get_file_parts_from_message(message)
        
        assert len(file_parts) == 2
        assert isinstance(file_parts[0].file, FileWithUri)
        assert isinstance(file_parts[1].file, FileWithBytes)