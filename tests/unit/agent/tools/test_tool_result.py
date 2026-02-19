"""
Unit tests for tool_result.py

Tests for the ToolResult abstraction including DataObject and DataDisposition.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.agent.tools.tool_result import (
    ToolResult,
    DataObject,
    DataDisposition,
)


class TestDataDisposition:
    """Test cases for DataDisposition enum."""

    def test_enum_values_exist(self):
        """All expected enum values should exist."""
        assert DataDisposition.AUTO == "auto"
        assert DataDisposition.ARTIFACT == "artifact"
        assert DataDisposition.INLINE == "inline"
        assert DataDisposition.ARTIFACT_WITH_PREVIEW == "artifact_with_preview"

    def test_enum_is_string(self):
        """DataDisposition should be a string enum."""
        assert isinstance(DataDisposition.AUTO, str)
        assert DataDisposition.AUTO == "auto"

    def test_all_values(self):
        """All enum members should be accessible."""
        all_values = [d.value for d in DataDisposition]
        assert "auto" in all_values
        assert "artifact" in all_values
        assert "inline" in all_values
        assert "artifact_with_preview" in all_values
        assert len(all_values) == 4


class TestDataObject:
    """Test cases for DataObject class."""

    def test_create_with_string_content(self):
        """DataObject should accept string content."""
        obj = DataObject(
            name="test.txt",
            content="Hello, World!",
            mime_type="text/plain",
        )
        assert obj.name == "test.txt"
        assert obj.content == "Hello, World!"
        assert obj.mime_type == "text/plain"

    def test_create_with_bytes_content(self):
        """DataObject should accept bytes content."""
        obj = DataObject(
            name="test.bin",
            content=b"\x00\x01\x02\x03",
            mime_type="application/octet-stream",
        )
        assert obj.name == "test.bin"
        assert obj.content == b"\x00\x01\x02\x03"
        assert obj.mime_type == "application/octet-stream"

    def test_disposition_defaults_to_auto(self):
        """DataObject disposition should default to AUTO."""
        obj = DataObject(name="test.txt", content="content")
        assert obj.disposition == DataDisposition.AUTO
        # Also check that it serializes to string value
        assert obj.model_dump()["disposition"] == "auto"

    def test_all_disposition_values(self):
        """DataObject should accept all disposition values."""
        for disposition in DataDisposition:
            obj = DataObject(
                name="test.txt",
                content="content",
                disposition=disposition,
            )
            assert obj.disposition == disposition

    def test_with_description(self):
        """DataObject should store description."""
        obj = DataObject(
            name="test.txt",
            content="content",
            description="This is a test file",
        )
        assert obj.description == "This is a test file"

    def test_with_preview(self):
        """DataObject should store preview."""
        obj = DataObject(
            name="test.txt",
            content="full content here...",
            preview="preview text",
            disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
        )
        assert obj.preview == "preview text"

    def test_with_metadata(self):
        """DataObject should store custom metadata."""
        obj = DataObject(
            name="test.txt",
            content="content",
            metadata={"key1": "value1", "key2": 42},
        )
        assert obj.metadata == {"key1": "value1", "key2": 42}

    def test_default_mime_type(self):
        """DataObject should default to text/plain mime type."""
        obj = DataObject(name="test", content="content")
        assert obj.mime_type == "text/plain"

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        obj = DataObject(name="test", content="content")
        assert obj.description is None
        assert obj.preview is None
        assert obj.metadata is None

    def test_name_required(self):
        """DataObject should require name field."""
        with pytest.raises(ValidationError):
            DataObject(content="content")  # type: ignore

    def test_content_required(self):
        """DataObject should require content field."""
        with pytest.raises(ValidationError):
            DataObject(name="test")  # type: ignore

    def test_model_dump(self):
        """DataObject should serialize to dict correctly."""
        obj = DataObject(
            name="test.json",
            content='{"key": "value"}',
            mime_type="application/json",
            disposition=DataDisposition.ARTIFACT,
            description="Test JSON file",
        )
        data = obj.model_dump()
        assert data["name"] == "test.json"
        assert data["content"] == '{"key": "value"}'
        assert data["mime_type"] == "application/json"
        assert data["disposition"] == "artifact"  # Enum serialized as string
        assert data["description"] == "Test JSON file"


class TestToolResult:
    """Test cases for ToolResult class."""

    def test_create_success_result(self):
        """ToolResult should create with default success status."""
        result = ToolResult(message="Operation completed")
        assert result.status == "success"
        assert result.message == "Operation completed"

    def test_create_with_data(self):
        """ToolResult should accept inline data."""
        result = ToolResult(
            message="Done",
            data={"count": 42, "items": ["a", "b"]},
        )
        assert result.data == {"count": 42, "items": ["a", "b"]}

    def test_create_with_data_objects(self):
        """ToolResult should accept data objects list."""
        data_obj = DataObject(name="result.txt", content="result data")
        result = ToolResult(
            message="Done",
            data_objects=[data_obj],
        )
        assert len(result.data_objects) == 1
        assert result.data_objects[0].name == "result.txt"

    def test_data_objects_defaults_to_empty_list(self):
        """ToolResult data_objects should default to empty list."""
        result = ToolResult(message="Done")
        assert result.data_objects == []

    def test_ok_class_method(self):
        """ToolResult.ok() should create success result."""
        result = ToolResult.ok("Success", data={"key": "value"})
        assert result.status == "success"
        assert result.message == "Success"
        assert result.data == {"key": "value"}
        assert result.data_objects == []

    def test_ok_with_data_objects(self):
        """ToolResult.ok() should accept data_objects."""
        data_obj = DataObject(name="output.txt", content="output")
        result = ToolResult.ok(
            "Generated output",
            data_objects=[data_obj],
        )
        assert result.status == "success"
        assert len(result.data_objects) == 1

    def test_error_class_method(self):
        """ToolResult.error() should create error result."""
        result = ToolResult.error("Something went wrong", code="ERR_001")
        assert result.status == "error"
        assert result.message == "Something went wrong"
        assert result.error_code == "ERR_001"

    def test_error_with_data(self):
        """ToolResult.error() should accept additional data."""
        result = ToolResult.error(
            "Failed",
            code="ERR_002",
            data={"failed_item": "xyz"},
        )
        assert result.status == "error"
        assert result.data == {"failed_item": "xyz"}

    def test_partial_class_method(self):
        """ToolResult.partial() should create partial success result."""
        result = ToolResult.partial(
            "2 of 3 items processed",
            data={"processed": 2, "failed": 1},
        )
        assert result.status == "partial"
        assert result.message == "2 of 3 items processed"
        assert result.data == {"processed": 2, "failed": 1}

    def test_partial_with_data_objects(self):
        """ToolResult.partial() should accept data_objects."""
        data_obj = DataObject(name="partial_output.txt", content="partial")
        result = ToolResult.partial(
            "Partial success",
            data_objects=[data_obj],
            error_code="PARTIAL_ERR",
        )
        assert result.status == "partial"
        assert len(result.data_objects) == 1
        assert result.error_code == "PARTIAL_ERR"

    def test_model_dump(self):
        """ToolResult should serialize to dict correctly."""
        data_obj = DataObject(
            name="output.json",
            content="{}",
            mime_type="application/json",
        )
        result = ToolResult(
            status="success",
            message="Done",
            data={"count": 1},
            data_objects=[data_obj],
        )
        data = result.model_dump()
        assert data["status"] == "success"
        assert data["message"] == "Done"
        assert data["data"] == {"count": 1}
        assert len(data["data_objects"]) == 1
        assert data["data_objects"][0]["name"] == "output.json"

    def test_custom_status(self):
        """ToolResult should accept custom status values."""
        result = ToolResult(status="warning", message="Potential issue")
        assert result.status == "warning"

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        result = ToolResult()
        assert result.message is None
        assert result.data is None
        assert result.error_code is None

    def test_multiple_data_objects(self):
        """ToolResult should handle multiple data objects."""
        result = ToolResult(
            message="Multiple outputs",
            data_objects=[
                DataObject(name="out1.txt", content="content1"),
                DataObject(name="out2.txt", content="content2"),
                DataObject(name="out3.txt", content="content3"),
            ],
        )
        assert len(result.data_objects) == 3
        assert result.data_objects[0].name == "out1.txt"
        assert result.data_objects[1].name == "out2.txt"
        assert result.data_objects[2].name == "out3.txt"


class TestToolResultWithDataObjects:
    """Test cases for ToolResult combined with DataObjects."""

    def test_full_workflow_example(self):
        """Test a realistic workflow with ToolResult and DataObjects."""
        # Simulate a tool that processes data and produces multiple outputs
        result = ToolResult.ok(
            message="Analysis complete: processed 100 records",
            data={
                "records_processed": 100,
                "records_failed": 0,
                "summary": "All records processed successfully",
            },
            data_objects=[
                DataObject(
                    name="results.json",
                    content='{"results": []}',
                    mime_type="application/json",
                    disposition=DataDisposition.ARTIFACT_WITH_PREVIEW,
                    description="Full analysis results",
                    preview='{"results": [...100 items...]}',
                ),
                DataObject(
                    name="log.txt",
                    content="Processing started...\nProcessing complete.",
                    mime_type="text/plain",
                    disposition=DataDisposition.INLINE,
                    description="Processing log",
                ),
            ],
        )

        assert result.status == "success"
        assert "100 records" in result.message
        assert result.data["records_processed"] == 100
        assert len(result.data_objects) == 2

        # Check first data object (artifact with preview)
        results_obj = result.data_objects[0]
        assert results_obj.name == "results.json"
        assert results_obj.disposition == DataDisposition.ARTIFACT_WITH_PREVIEW
        assert results_obj.preview is not None

        # Check second data object (inline)
        log_obj = result.data_objects[1]
        assert log_obj.name == "log.txt"
        assert log_obj.disposition == DataDisposition.INLINE

    def test_error_result_no_data_objects(self):
        """Error results typically don't include data_objects."""
        result = ToolResult.error(
            "Failed to process data: file not found",
            code="FILE_NOT_FOUND",
            data={"missing_file": "input.csv"},
        )

        assert result.status == "error"
        assert result.error_code == "FILE_NOT_FOUND"
        assert result.data_objects == []
        assert "file not found" in result.message
