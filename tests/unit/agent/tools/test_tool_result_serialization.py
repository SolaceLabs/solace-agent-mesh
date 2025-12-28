"""
Unit tests for ToolResult serialization/deserialization.

Tests the round-trip behavior of serializing ToolResult and DataObject
for transmission over remote executors (Lambda, HTTP).
"""

import pytest

from solace_agent_mesh.agent.tools.tool_result import (
    ToolResult,
    DataObject,
    DataDisposition,
    TOOL_RESULT_SCHEMA_VERSION,
)


class TestDataObjectSerialization:
    """Test DataObject serialization round-trips."""

    def test_round_trip_text_content(self):
        """Text content survives serialize/deserialize unchanged."""
        original = DataObject(
            name="test.txt",
            content="Hello, World!",
            mime_type="text/plain",
        )

        serialized = original.to_serializable()
        restored = DataObject.from_serialized(serialized)

        assert restored.name == original.name
        assert restored.content == original.content
        assert restored.mime_type == original.mime_type

    def test_round_trip_binary_content(self):
        """Binary (bytes) content survives round-trip via base64 encoding."""
        binary_data = b"\x00\x01\x02\xff\xfe\xfd"
        original = DataObject(
            name="test.bin",
            content=binary_data,
            mime_type="application/octet-stream",
        )

        serialized = original.to_serializable()

        # Verify binary is base64 encoded in serialized form
        assert serialized["is_binary"] is True
        assert isinstance(serialized["content"], str)

        # Verify it restores to bytes
        restored = DataObject.from_serialized(serialized)
        assert restored.content == binary_data
        assert isinstance(restored.content, bytes)

    def test_round_trip_preserves_all_fields(self):
        """All DataObject fields are preserved through serialization."""
        original = DataObject(
            name="report.json",
            content='{"key": "value"}',
            mime_type="application/json",
            disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
            description="A test report",
            preview='{"key": "..."}',
            metadata={"author": "test", "version": 1},
        )

        serialized = original.to_serializable()
        restored = DataObject.from_serialized(serialized)

        assert restored.name == original.name
        assert restored.content == original.content
        assert restored.mime_type == original.mime_type
        assert restored.disposition == original.disposition
        assert restored.description == original.description
        assert restored.preview == original.preview
        assert restored.metadata == original.metadata


class TestToolResultSerialization:
    """Test ToolResult serialization round-trips."""

    def test_serialized_format_has_schema_markers(self):
        """Serialized ToolResult includes _schema and _schema_version."""
        result = ToolResult.ok("Test message")
        serialized = result.to_serializable()

        assert serialized["_schema"] == "ToolResult"
        assert serialized["_schema_version"] == TOOL_RESULT_SCHEMA_VERSION

    def test_round_trip_success_result(self):
        """Success result survives serialization round-trip."""
        original = ToolResult.ok(
            "Operation completed",
            data={"count": 42, "items": ["a", "b", "c"]},
        )

        serialized = original.to_serializable()
        restored = ToolResult.from_serialized(serialized)

        assert restored.status == "success"
        assert restored.message == original.message
        assert restored.data == original.data
        assert restored.error_code is None

    def test_round_trip_error_result(self):
        """Error result with error_code survives serialization."""
        original = ToolResult.error(
            "File not found",
            code="FILE_NOT_FOUND",
            data={"path": "/missing/file.txt"},
        )

        serialized = original.to_serializable()
        restored = ToolResult.from_serialized(serialized)

        assert restored.status == "error"
        assert restored.message == original.message
        assert restored.error_code == "FILE_NOT_FOUND"
        assert restored.data == original.data

    def test_round_trip_with_data_objects(self):
        """DataObjects survive serialization inside ToolResult."""
        original = ToolResult.ok(
            "Generated files",
            data_objects=[
                DataObject(
                    name="output1.txt",
                    content="Content 1",
                    description="First output",
                ),
                DataObject(
                    name="output2.json",
                    content='{"result": true}',
                    mime_type="application/json",
                ),
            ],
        )

        serialized = original.to_serializable()
        restored = ToolResult.from_serialized(serialized)

        assert len(restored.data_objects) == 2
        assert restored.data_objects[0].name == "output1.txt"
        assert restored.data_objects[0].content == "Content 1"
        assert restored.data_objects[1].name == "output2.json"
        assert restored.data_objects[1].content == '{"result": true}'

    def test_round_trip_with_binary_data_objects(self):
        """Binary DataObjects survive serialization inside ToolResult."""
        binary_content = b"\x89PNG\r\n\x1a\n"  # PNG header bytes
        original = ToolResult.ok(
            "Generated image",
            data_objects=[
                DataObject(
                    name="image.png",
                    content=binary_content,
                    mime_type="image/png",
                    disposition=DataDisposition.ARTIFACT,
                ),
            ],
        )

        serialized = original.to_serializable()
        restored = ToolResult.from_serialized(serialized)

        assert len(restored.data_objects) == 1
        assert restored.data_objects[0].name == "image.png"
        assert restored.data_objects[0].content == binary_content
        assert isinstance(restored.data_objects[0].content, bytes)

    def test_is_serialized_tool_result_detection(self):
        """is_serialized_tool_result correctly identifies valid/invalid formats."""
        # Valid serialized ToolResult
        valid = {"_schema": "ToolResult", "_schema_version": "1.0", "status": "success"}
        assert ToolResult.is_serialized_tool_result(valid) is True

        # Missing _schema
        missing_schema = {"status": "success", "message": "test"}
        assert ToolResult.is_serialized_tool_result(missing_schema) is False

        # Wrong _schema value
        wrong_schema = {"_schema": "SomethingElse", "status": "success"}
        assert ToolResult.is_serialized_tool_result(wrong_schema) is False

        # Non-dict values
        assert ToolResult.is_serialized_tool_result("not a dict") is False
        assert ToolResult.is_serialized_tool_result(None) is False
        assert ToolResult.is_serialized_tool_result([]) is False

    def test_from_serialized_rejects_invalid_schema(self):
        """from_serialized raises ValueError for invalid schema marker."""
        invalid = {"status": "success", "message": "test"}

        with pytest.raises(ValueError, match="Invalid schema marker"):
            ToolResult.from_serialized(invalid)

    def test_round_trip_partial_result(self):
        """Partial success result survives serialization."""
        original = ToolResult.partial(
            "2 of 3 items processed",
            data={"processed": 2, "failed": 1},
            error_code="PARTIAL_FAILURE",
            data_objects=[
                DataObject(name="success.txt", content="OK"),
            ],
        )

        serialized = original.to_serializable()
        restored = ToolResult.from_serialized(serialized)

        assert restored.status == "partial"
        assert restored.message == original.message
        assert restored.data == original.data
        assert restored.error_code == "PARTIAL_FAILURE"
        assert len(restored.data_objects) == 1
