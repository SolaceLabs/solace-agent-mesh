"""
Unit tests for message translation functions in GenericGatewayComponent.

These tests verify the pure data transformation functions that convert between
SAM adapter types and A2A protocol types. No mocking is required as these are
pure functions with no side effects.
"""

import pytest
from a2a.types import (
    DataPart as A2ADataPart,
    FilePart,
    JSONRPCError,
    TaskState,
    TextPart,
)

from solace_agent_mesh.common import a2a
from solace_agent_mesh.gateway.adapter.types import (
    SamDataPart,
    SamError,
    SamFilePart,
    SamTextPart,
)
from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent


# --- Test Fixture ---


class TestableGenericGatewayComponent:
    """
    Wrapper to expose private conversion methods for testing.

    We create a minimal instance just to access the conversion methods,
    which are pure functions that don't depend on component state.
    """

    def __init__(self):
        # Create a minimal config that allows component instantiation
        self.config = {
            "namespace": "test",
            "gateway_adapter": "solace_agent_mesh.gateway.slack.adapter.SlackAdapter",
            "adapter_config": {
                "slack_bot_token": "xoxb-test",
                "slack_app_token": "xapp-test",
            },
        }
        # We won't actually initialize the component, just create it to access methods
        # The conversion methods don't use any instance state

    def sam_parts_to_a2a_parts(self, sam_parts):
        """Expose _sam_parts_to_a2a_parts for testing"""
        component = GenericGatewayComponent.__new__(GenericGatewayComponent)
        return component._sam_parts_to_a2a_parts(sam_parts)

    def a2a_parts_to_sam_parts(self, a2a_parts):
        """Expose _a2a_parts_to_sam_parts for testing"""
        component = GenericGatewayComponent.__new__(GenericGatewayComponent)
        return component._a2a_parts_to_sam_parts(a2a_parts)

    def a2a_error_to_sam_error(self, error):
        """Expose _a2a_error_to_sam_error for testing"""
        component = GenericGatewayComponent.__new__(GenericGatewayComponent)
        return component._a2a_error_to_sam_error(error)


@pytest.fixture
def component():
    """Provides access to the conversion methods"""
    return TestableGenericGatewayComponent()


# --- Tests for _sam_parts_to_a2a_parts ---


def test_sam_text_part_to_a2a(component):
    """Convert a simple SamTextPart to A2A TextPart"""
    # Arrange
    sam_parts = [SamTextPart(text="Hello, world!")]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 1
    assert isinstance(a2a_parts[0], TextPart)
    assert a2a_parts[0].text == "Hello, world!"


def test_sam_file_part_bytes_to_a2a(component):
    """Convert SamFilePart with inline bytes to A2A FilePart"""
    # Arrange
    test_bytes = b"test file content"
    sam_parts = [
        SamFilePart(
            name="test.txt",
            content_bytes=test_bytes,
            mime_type="text/plain",
        )
    ]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 1
    assert isinstance(a2a_parts[0], FilePart)

    # Use a2a helpers to extract values
    assert a2a.get_filename_from_file_part(a2a_parts[0]) == "test.txt"
    assert a2a.get_bytes_from_file_part(a2a_parts[0]) == test_bytes
    assert a2a.get_mimetype_from_file_part(a2a_parts[0]) == "text/plain"


def test_sam_file_part_uri_to_a2a(component):
    """Convert SamFilePart with URI to A2A FilePart"""
    # Arrange
    sam_parts = [
        SamFilePart(
            name="remote.jpg",
            uri="https://example.com/image.jpg",
            mime_type="image/jpeg",
        )
    ]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 1
    assert isinstance(a2a_parts[0], FilePart)

    assert a2a.get_filename_from_file_part(a2a_parts[0]) == "remote.jpg"
    assert a2a.get_uri_from_file_part(a2a_parts[0]) == "https://example.com/image.jpg"
    assert a2a.get_mimetype_from_file_part(a2a_parts[0]) == "image/jpeg"


def test_sam_file_part_without_mime_type(component):
    """Convert SamFilePart without mime_type (should work)"""
    # Arrange
    sam_parts = [
        SamFilePart(
            name="unknown.bin",
            content_bytes=b"binary data",
            mime_type=None,
        )
    ]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 1
    assert isinstance(a2a_parts[0], FilePart)
    assert a2a.get_filename_from_file_part(a2a_parts[0]) == "unknown.bin"


def test_sam_data_part_to_a2a(component):
    """Convert SamDataPart to A2A DataPart"""
    # Arrange
    test_data = {"key": "value", "count": 42, "nested": {"item": "data"}}
    sam_parts = [SamDataPart(data=test_data)]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 1
    assert isinstance(a2a_parts[0], A2ADataPart)

    extracted_data = a2a.get_data_from_data_part(a2a_parts[0])
    assert extracted_data == test_data


def test_sam_mixed_parts_to_a2a(component):
    """Convert a list with multiple different part types"""
    # Arrange
    sam_parts = [
        SamTextPart(text="Introduction"),
        SamFilePart(name="doc.pdf", content_bytes=b"pdf content", mime_type="application/pdf"),
        SamDataPart(data={"status": "complete"}),
        SamTextPart(text="Conclusion"),
    ]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert len(a2a_parts) == 4
    assert isinstance(a2a_parts[0], TextPart)
    assert isinstance(a2a_parts[1], FilePart)
    assert isinstance(a2a_parts[2], A2ADataPart)
    assert isinstance(a2a_parts[3], TextPart)


def test_sam_empty_list_to_a2a(component):
    """Convert empty list (edge case)"""
    # Arrange
    sam_parts = []

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(sam_parts)

    # Assert
    assert a2a_parts == []


# --- Tests for _a2a_parts_to_sam_parts ---


def test_a2a_text_part_to_sam(component):
    """Convert A2A TextPart to SamTextPart"""
    # Arrange
    a2a_parts = [a2a.create_text_part("Response text")]

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(sam_parts) == 1
    assert isinstance(sam_parts[0], SamTextPart)
    assert sam_parts[0].text == "Response text"


def test_a2a_file_part_bytes_to_sam(component):
    """Convert A2A FilePart with bytes to SamFilePart"""
    # Arrange
    test_content = b"file contents here"
    a2a_parts = [
        a2a.create_file_part_from_bytes(
            content_bytes=test_content,
            name="result.csv",
            mime_type="text/csv",
        )
    ]

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(sam_parts) == 1
    assert isinstance(sam_parts[0], SamFilePart)
    assert sam_parts[0].name == "result.csv"
    assert sam_parts[0].content_bytes == test_content
    assert sam_parts[0].mime_type == "text/csv"
    assert sam_parts[0].uri is None


def test_a2a_file_part_uri_to_sam(component):
    """Convert A2A FilePart with URI to SamFilePart"""
    # Arrange
    a2a_parts = [
        a2a.create_file_part_from_uri(
            uri="https://storage.example.com/file.zip",
            name="archive.zip",
            mime_type="application/zip",
        )
    ]

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(sam_parts) == 1
    assert isinstance(sam_parts[0], SamFilePart)
    assert sam_parts[0].name == "archive.zip"
    assert sam_parts[0].uri == "https://storage.example.com/file.zip"
    assert sam_parts[0].mime_type == "application/zip"
    assert sam_parts[0].content_bytes is None


def test_a2a_data_part_to_sam(component):
    """Convert A2A DataPart to SamDataPart"""
    # Arrange
    test_data = {"result": "success", "items": [1, 2, 3]}
    a2a_parts = [a2a.create_data_part(test_data)]

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(sam_parts) == 1
    assert isinstance(sam_parts[0], SamDataPart)
    assert sam_parts[0].data == test_data


def test_a2a_data_part_with_metadata_to_sam(component):
    """Convert A2A DataPart with metadata to SamDataPart"""
    # Arrange
    test_data = {"value": 123}
    # Create a DataPart and manually add metadata (using a2a SDK)
    data_part = a2a.create_data_part(test_data)
    # Note: Metadata handling depends on the a2a SDK implementation
    # This test verifies the extraction works

    # Act
    sam_parts = component.a2a_parts_to_sam_parts([data_part])

    # Assert
    assert len(sam_parts) == 1
    assert isinstance(sam_parts[0], SamDataPart)
    assert sam_parts[0].data == test_data
    # Metadata field exists even if None
    assert hasattr(sam_parts[0], "metadata")


def test_a2a_mixed_parts_to_sam(component):
    """Convert a list with multiple different A2A part types"""
    # Arrange
    a2a_parts = [
        a2a.create_text_part("Header"),
        a2a.create_file_part_from_bytes(b"data", "file.bin", "application/octet-stream"),
        a2a.create_data_part({"info": "metadata"}),
        a2a.create_file_part_from_uri("https://cdn.example.com/image.png", "image.png"),
        a2a.create_text_part("Footer"),
    ]

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(sam_parts) == 5
    assert isinstance(sam_parts[0], SamTextPart)
    assert isinstance(sam_parts[1], SamFilePart)
    assert sam_parts[1].content_bytes == b"data"
    assert isinstance(sam_parts[2], SamDataPart)
    assert isinstance(sam_parts[3], SamFilePart)
    assert sam_parts[3].uri == "https://cdn.example.com/image.png"
    assert isinstance(sam_parts[4], SamTextPart)


def test_a2a_empty_list_to_sam(component):
    """Convert empty list (edge case)"""
    # Arrange
    a2a_parts = []

    # Act
    sam_parts = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert sam_parts == []


# --- Round-trip tests ---


def test_sam_to_a2a_to_sam_roundtrip_text(component):
    """Verify text parts survive a round-trip conversion"""
    # Arrange
    original = [SamTextPart(text="Round trip test")]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(original)
    result = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(result) == 1
    assert result[0].text == original[0].text


def test_sam_to_a2a_to_sam_roundtrip_file_bytes(component):
    """Verify file parts with bytes survive a round-trip conversion"""
    # Arrange
    original = [
        SamFilePart(
            name="test.dat",
            content_bytes=b"important data",
            mime_type="application/octet-stream",
        )
    ]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(original)
    result = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(result) == 1
    assert result[0].name == original[0].name
    assert result[0].content_bytes == original[0].content_bytes
    assert result[0].mime_type == original[0].mime_type


def test_sam_to_a2a_to_sam_roundtrip_data(component):
    """Verify data parts survive a round-trip conversion"""
    # Arrange
    original = [SamDataPart(data={"key": "value", "nested": {"item": 42}})]

    # Act
    a2a_parts = component.sam_parts_to_a2a_parts(original)
    result = component.a2a_parts_to_sam_parts(a2a_parts)

    # Assert
    assert len(result) == 1
    assert result[0].data == original[0].data


# --- Tests for _a2a_error_to_sam_error ---


def test_a2a_error_with_failed_task_state(component):
    """Convert A2A error with failed task status"""
    # Arrange
    a2a_error = JSONRPCError(
        code=-32000,
        message="Task execution failed",
        data={"taskStatus": TaskState.failed, "details": "Agent crashed"},
    )

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    assert isinstance(sam_error, SamError)
    assert sam_error.code == -32000
    assert sam_error.message == "Task execution failed"
    assert sam_error.category == "FAILED"


def test_a2a_error_with_canceled_task_state(component):
    """Convert A2A error with canceled task status"""
    # Arrange
    a2a_error = JSONRPCError(
        code=-32001,
        message="Task was canceled by user",
        data={"taskStatus": TaskState.canceled},
    )

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    assert sam_error.code == -32001
    assert sam_error.message == "Task was canceled by user"
    assert sam_error.category == "CANCELED"


def test_a2a_error_without_task_status(component):
    """Convert A2A error without taskStatus field defaults to PROTOCOL_ERROR"""
    # Arrange
    a2a_error = JSONRPCError(
        code=-32600,
        message="Invalid request format",
        data={"other_field": "some value"},
    )

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    assert sam_error.category == "PROTOCOL_ERROR"
    assert sam_error.code == -32600
    assert sam_error.message == "Invalid request format"


def test_a2a_error_with_non_dict_data(component):
    """Convert A2A error with non-dict data defaults to PROTOCOL_ERROR"""
    # Arrange
    a2a_error = JSONRPCError(
        code=-32700,
        message="Parse error",
        data="string data instead of dict",
    )

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    assert sam_error.category == "PROTOCOL_ERROR"
    assert sam_error.code == -32700
    assert sam_error.message == "Parse error"


def test_a2a_error_with_completed_task_state(component):
    """Convert A2A error with completed status (unusual but should handle)"""
    # Arrange
    a2a_error = JSONRPCError(
        code=-32002,
        message="Unexpected error after completion",
        data={"taskStatus": TaskState.completed},
    )

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    # completed is not failed or canceled, so defaults to PROTOCOL_ERROR
    assert sam_error.category == "PROTOCOL_ERROR"
    assert sam_error.code == -32002


@pytest.mark.parametrize(
    "code,message,task_state,expected_category",
    [
        (-32000, "Failed", TaskState.failed, "FAILED"),
        (-32001, "Canceled", TaskState.canceled, "CANCELED"),
        (-32002, "Working", TaskState.working, "PROTOCOL_ERROR"),
        (-32003, "Timeout", None, "PROTOCOL_ERROR"),
    ],
)
def test_a2a_error_category_mapping_parametrized(
    component, code, message, task_state, expected_category
):
    """Test various error code and task state combinations"""
    # Arrange
    data = {"taskStatus": task_state} if task_state else {}
    a2a_error = JSONRPCError(code=code, message=message, data=data)

    # Act
    sam_error = component.a2a_error_to_sam_error(a2a_error)

    # Assert
    assert sam_error.category == expected_category
    assert sam_error.code == code
    assert sam_error.message == message
