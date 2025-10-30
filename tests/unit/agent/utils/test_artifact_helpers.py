
"""
Unit tests for artifact helper functions.
Tests cover filename validation, URI handling, schema inference, metadata processing, and artifact operations.
"""

import pytest
import json
import base64
import yaml
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from solace_agent_mesh.agent.adk.services import BaseArtifactService
from solace_agent_mesh.agent.utils.artifact_helpers import (
    is_filename_safe,
    ensure_correct_extension,
    format_artifact_uri,
    parse_artifact_uri,
    _inspect_structure,
    _infer_schema,
    save_artifact_with_metadata,
    process_artifact_upload,
    format_metadata_for_llm,
    decode_and_get_bytes,
    get_latest_artifact_version,
    load_artifact_content_or_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)


class TestIsFilenameSafe:
    """Test the is_filename_safe function."""

    def test_safe_filename(self):
        """Test that safe filenames return True."""
        safe_filenames = [
            "document.txt",
            "my_file.pdf",
            "data-2023.csv",
            "image.png",
            "script.py",
            "config.json",
            "file123.docx",
            "test_file_name.xlsx"
        ]
        
        for filename in safe_filenames:
            assert is_filename_safe(filename), f"Expected '{filename}' to be safe"

    def test_unsafe_filename_empty(self):
        """Test that empty or whitespace filenames return False."""
        unsafe_filenames = ["", " ", "  ", "\t", "\n", "   \t\n  "]
        
        for filename in unsafe_filenames:
            assert not is_filename_safe(filename), f"Expected '{filename}' to be unsafe"

    def test_unsafe_filename_path_traversal(self):
        """Test that filenames with path traversal return False."""
        unsafe_filenames = [
            "../file.txt",
            "file..txt",
            "..file.txt",
            "dir/../file.txt",
            "../../etc/passwd",
            "file..\\..\\windows\\system32"
        ]
        
        for filename in unsafe_filenames:
            assert not is_filename_safe(filename), f"Expected '{filename}' to be unsafe"

    def test_unsafe_filename_path_separators(self):
        """Test that filenames with path separators return False."""
        unsafe_filenames = [
            "dir/file.txt",
            "folder\\file.txt",
            "/absolute/path.txt",
            "C:\\Windows\\file.txt",
            "relative/path/file.txt"
        ]
        
        for filename in unsafe_filenames:
            assert not is_filename_safe(filename), f"Expected '{filename}' to be unsafe"

    def test_unsafe_filename_reserved_names(self):
        """Test that reserved names return False."""
        unsafe_filenames = [".", "..", " . ", " .. "]
        
        for filename in unsafe_filenames:
            assert not is_filename_safe(filename), f"Expected '{filename}' to be unsafe"


class TestEnsureCorrectExtension:
    """Test the ensure_correct_extension function."""

    def test_correct_extension_already_present(self):
        """Test filename with correct extension is unchanged."""
        result = ensure_correct_extension("document.pdf", "pdf")
        assert result == "document.pdf"

    def test_correct_extension_case_insensitive(self):
        """Test that extension matching is case insensitive."""
        result = ensure_correct_extension("document.PDF", "pdf")
        assert result == "document.PDF"

    def test_wrong_extension_replaced(self):
        """Test that wrong extension is replaced."""
        result = ensure_correct_extension("document.txt", "pdf")
        assert result == "document.pdf"

    def test_no_extension_added(self):
        """Test that extension is added when missing."""
        result = ensure_correct_extension("document", "pdf")
        assert result == "document.pdf"

    def test_empty_filename_default(self):
        """Test that empty filename gets default name."""
        result = ensure_correct_extension("", "pdf")
        assert result == "unnamed.pdf"

    def test_extension_with_dot_handled(self):
        """Test that extension with leading dot is handled correctly."""
        result = ensure_correct_extension("document", ".pdf")
        assert result == "document.pdf"

    def test_whitespace_filename_handled(self):
        """Test that whitespace in filename is handled."""
        result = ensure_correct_extension("  document.txt  ", "pdf")
        assert result == "document.pdf"


class TestFormatArtifactUri:
    """Test the format_artifact_uri function."""

    def test_format_basic_uri(self):
        """Test formatting basic artifact URI."""
        uri = format_artifact_uri("myapp", "user123", "session456", "file.txt", 1)
        expected = "artifact://myapp/user123/session456/file.txt?version=1"
        assert uri == expected

    def test_format_uri_with_string_version(self):
        """Test formatting URI with string version."""
        uri = format_artifact_uri("myapp", "user123", "session456", "file.txt", "latest")
        expected = "artifact://myapp/user123/session456/file.txt?version=latest"
        assert uri == expected

    def test_format_uri_special_characters(self):
        """Test formatting URI with special characters in filename."""
        uri = format_artifact_uri("myapp", "user123", "session456", "my file.txt", 1)
        assert "artifact://myapp/user123/session456/my file.txt?version=1" == uri

    def test_format_uri_numeric_identifiers(self):
        """Test formatting URI with numeric identifiers."""
        uri = format_artifact_uri("app", "12345", "67890", "data.csv", 42)
        expected = "artifact://app/12345/67890/data.csv?version=42"
        assert uri == expected


class TestParseArtifactUri:
    """Test the parse_artifact_uri function."""

    def test_parse_valid_uri(self):
        """Test parsing valid artifact URI."""
        uri = "artifact://myapp/user123/session456/file.txt?version=1"
        result = parse_artifact_uri(uri)
        
        expected = {
            "app_name": "myapp",
            "user_id": "user123",
            "session_id": "session456",
            "filename": "file.txt",
            "version": 1
        }
        assert result == expected

    def test_parse_uri_string_version(self):
        """Test parsing URI with string version."""
        uri = "artifact://myapp/user123/session456/file.txt?version=latest"
        result = parse_artifact_uri(uri)
        
        assert result["version"] == "latest"

    def test_parse_invalid_scheme(self):
        """Test parsing URI with invalid scheme."""
        uri = "http://myapp/user123/session456/file.txt?version=1"
        
        with pytest.raises(ValueError, match="Invalid URI scheme"):
            parse_artifact_uri(uri)

    def test_parse_invalid_path(self):
        """Test parsing URI with invalid path structure."""
        invalid_uris = [
            "artifact://myapp/user123?version=1",  # Missing session_id and filename
            "artifact://myapp/user123/session456?version=1",  # Missing filename
            "artifact://myapp/user123/session456/file.txt/extra?version=1"  # Extra path component
        ]
        
        for uri in invalid_uris:
            with pytest.raises(ValueError, match="Invalid URI path"):
                parse_artifact_uri(uri)

    def test_parse_missing_version(self):
        """Test parsing URI with missing version parameter."""
        uri = "artifact://myapp/user123/session456/file.txt"
        
        with pytest.raises(ValueError, match="Version is missing"):
            parse_artifact_uri(uri)

    def test_parse_numeric_version_string(self):
        """Test parsing URI with numeric version as string."""
        uri = "artifact://myapp/user123/session456/file.txt?version=42"
        result = parse_artifact_uri(uri)
        
        assert result["version"] == 42
        assert isinstance(result["version"], int)


class TestInspectStructure:
    """Test the _inspect_structure function."""

    def test_inspect_simple_dict(self):
        """Test inspecting simple dictionary structure."""
        data = {"name": "John", "age": 30, "active": True}
        result = _inspect_structure(data, max_depth=3, max_keys=10)
        
        expected = {"name": "str", "age": "int", "active": "bool"}
        assert result == expected

    def test_inspect_nested_dict(self):
        """Test inspecting nested dictionary structure."""
        data = {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "dark", "notifications": True}
        }
        result = _inspect_structure(data, max_depth=3, max_keys=10)
        
        assert "user" in result
        assert "settings" in result
        assert result["user"]["name"] == "str"
        assert result["user"]["age"] == "int"

    def test_inspect_list_structure(self):
        """Test inspecting list structure."""
        data = [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]
        result = _inspect_structure(data, max_depth=3, max_keys=10)
        
        expected = [{"id": "int", "name": "str"}]
        assert result == expected

    def test_inspect_max_depth_limit(self):
        """Test that max_depth limit is respected."""
        data = {"level1": {"level2": {"level3": {"level4": "deep"}}}}
        result = _inspect_structure(data, max_depth=2, max_keys=10)
        
        assert result["level1"]["level2"] == "dict"

    def test_inspect_max_keys_limit(self):
        """Test that max_keys limit is respected."""
        data = {f"key{i}": f"value{i}" for i in range(25)}
        result = _inspect_structure(data, max_depth=3, max_keys=20)
        
        assert len([k for k in result.keys() if not k.startswith("...")]) <= 20
        assert "..." in result
        assert "5 more keys" in result["..."]

    def test_inspect_empty_structures(self):
        """Test inspecting empty structures."""
        assert _inspect_structure({}, max_depth=3, max_keys=10) == {}
        assert _inspect_structure([], max_depth=3, max_keys=10) == []

    def test_inspect_primitive_types(self):
        """Test inspecting primitive types."""
        assert _inspect_structure("string", max_depth=3, max_keys=10) == "str"
        assert _inspect_structure(42, max_depth=3, max_keys=10) == "int"
        assert _inspect_structure(3.14, max_depth=3, max_keys=10) == "float"
        assert _inspect_structure(True, max_depth=3, max_keys=10) == "bool"
        assert _inspect_structure(None, max_depth=3, max_keys=10) == "NoneType"


class TestInferSchema:
    """Test the _infer_schema function."""

    def test_infer_json_schema(self):
        """Test inferring schema from JSON content."""
        data = {"name": "John", "age": 30, "active": True}
        content_bytes = json.dumps(data).encode("utf-8")
        
        result = _infer_schema(content_bytes, "application/json")
        
        assert result["type"] == "application/json"
        assert result["inferred"] is True
        assert result["error"] is None
        assert "structure" in result
        assert result["structure"]["name"] == "str"
        assert result["structure"]["age"] == "int"

    def test_infer_csv_schema(self):
        """Test inferring schema from CSV content."""
        csv_content = "name,age,email\nJohn,30,john@example.com\nJane,25,jane@example.com"
        content_bytes = csv_content.encode("utf-8")
        
        result = _infer_schema(content_bytes, "text/csv")
        
        assert result["type"] == "text/csv"
        assert result["inferred"] is True
        assert result["error"] is None
        assert "columns" in result
        assert result["columns"] == ["name", "age", "email"]

    def test_infer_yaml_schema(self):
        """Test inferring schema from YAML content."""
        data = {"name": "John", "age": 30, "settings": {"theme": "dark"}}
        content_bytes = yaml.safe_dump(data).encode("utf-8")
        
        result = _infer_schema(content_bytes, "application/yaml")
        
        assert result["type"] == "application/yaml"
        assert result["inferred"] is True
        assert result["error"] is None
        assert "structure" in result

    def test_infer_schema_invalid_json(self):
        """Test inferring schema from invalid JSON."""
        content_bytes = b'{"invalid": json}'
        
        result = _infer_schema(content_bytes, "application/json")
        
        assert result["type"] == "application/json"
        assert result["inferred"] is False
        assert result["error"] is not None
        assert "JSON structure inference failed" in result["error"]

    def test_infer_schema_invalid_csv(self):
        """Test inferring schema from invalid CSV."""
        content_bytes = b'\xff\xfe\x00\x00'  # Invalid UTF-8
        
        result = _infer_schema(content_bytes, "text/csv")
        
        assert result["type"] == "text/csv"
        assert result["inferred"] is False
        assert result["error"] is not None

    def test_infer_schema_unsupported_type(self):
        """Test inferring schema from unsupported MIME type."""
        content_bytes = b"Some binary content"
        
        result = _infer_schema(content_bytes, "application/octet-stream")
        
        assert result["type"] == "application/octet-stream"
        assert result["inferred"] is False
        assert result["error"] is None

    def test_infer_schema_with_depth_limit(self):
        """Test schema inference with depth limit."""
        data = {"level1": {"level2": {"level3": {"level4": "deep"}}}}
        content_bytes = json.dumps(data).encode("utf-8")
        
        result = _infer_schema(content_bytes, "application/json", depth=2)
        
        assert result["inferred"] is True
        assert result["structure"]["level1"]["level2"] == "dict"

    def test_infer_schema_with_max_keys_limit(self):
        """Test schema inference with max_keys limit."""
        data = {f"key{i}": f"value{i}" for i in range(25)}
        content_bytes = json.dumps(data).encode("utf-8")
        
        result = _infer_schema(content_bytes, "application/json", max_keys=10)
        
        assert result["inferred"] is True
        assert "..." in result["structure"]


class TestSaveArtifactWithMetadata:
    """Test the save_artifact_with_metadata function."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock(spec=BaseArtifactService)
        service.save_artifact = AsyncMock(return_value=1)
        return service

    @pytest.fixture
    def mock_tool_context(self):
        """Mock tool context for testing."""
        context = Mock()
        context.actions = Mock()
        context.actions.artifact_delta = {}
        return context

    @pytest.mark.asyncio
    async def test_save_artifact_success(self, mock_artifact_service, mock_tool_context):
        """Test successful artifact saving."""
        content_bytes = b"Test content"
        metadata_dict = {"description": "Test artifact"}
        timestamp = datetime.now(timezone.utc)
        
        result = await save_artifact_with_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            content_bytes=content_bytes,
            mime_type="text/plain",
            metadata_dict=metadata_dict,
            timestamp=timestamp,
            tool_context=mock_tool_context
        )
        
        assert result["status"] == "success"
        assert result["data_filename"] == "test.txt"
        assert result["data_version"] == 1
        assert result["metadata_filename"] == "test.txt.metadata.json"
        assert result["metadata_version"] == 1
        
        # Verify artifact_delta was populated
        assert mock_tool_context.actions.artifact_delta["test.txt"] == 1
        
        # Verify save_artifact was called twice (data + metadata)
        assert mock_artifact_service.save_artifact.call_count == 2

    @pytest.mark.asyncio
    async def test_save_artifact_with_explicit_schema(self, mock_artifact_service):
        """Test saving artifact with explicit schema."""
        content_bytes = b'{"name": "test"}'
        explicit_schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        
        result = await save_artifact_with_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.json",
            content_bytes=content_bytes,
            mime_type="application/json",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc),
            explicit_schema=explicit_schema
        )
        
        assert result["status"] == "success"
        
        # Verify the metadata call included explicit schema
        metadata_call = mock_artifact_service.save_artifact.call_args_list[1]
        metadata_part = metadata_call[1]["artifact"]
        metadata_content = json.loads(metadata_part.inline_data.data.decode("utf-8"))
        
        assert metadata_content["schema"]["inferred"] is False
        assert "properties" in metadata_content["schema"]

    @pytest.mark.asyncio
    async def test_save_artifact_data_failure(self, mock_artifact_service):
        """Test handling of data artifact save failure."""
        mock_artifact_service.save_artifact.side_effect = Exception("Save failed")
        
        content_bytes = b"Test content"
        
        result = await save_artifact_with_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            content_bytes=content_bytes,
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc)
        )
        
        assert result["status"] == "error"
        assert "Failed to save data artifact" in result["message"]
        assert result["data_version"] is None

    @pytest.mark.asyncio
    async def test_save_artifact_metadata_failure(self, mock_artifact_service):
        """Test handling of metadata save failure."""
        # First call (data) succeeds, second call (metadata) fails
        mock_artifact_service.save_artifact.side_effect = [1, Exception("Metadata save failed")]
        
        content_bytes = b"Test content"
        
        result = await save_artifact_with_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            content_bytes=content_bytes,
            mime_type="text/plain",
            metadata_dict={},
            timestamp=datetime.now(timezone.utc)
        )
        
        assert result["status"] == "partial_success"
        assert result["data_version"] == 1
        assert result["metadata_version"] is None
        assert "failed to save metadata" in result["message"]


class TestProcessArtifactUpload:
    """Test the process_artifact_upload function."""

    @pytest.fixture
    def mock_component(self):
        """Mock component for testing."""
        component = Mock()
        component.get_config.side_effect = lambda key, default=None: {
            "name": "TestApp",
            "schema_max_keys": DEFAULT_SCHEMA_MAX_KEYS
        }.get(key, default)
        return component

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock(spec=BaseArtifactService)
        service.save_artifact = AsyncMock(return_value=1)
        return service

    @pytest.mark.asyncio
    async def test_process_upload_success(self, mock_artifact_service, mock_component):
        """Test successful artifact upload processing."""
        content_bytes = b"Test file content"
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "success",
                "data_version": 1,
                "metadata_version": 1,
                "message": "Saved successfully"
            }
            
            result = await process_artifact_upload(
                artifact_service=mock_artifact_service,
                component=mock_component,
                user_id="user123",
                session_id="session456",
                filename="test.txt",
                content_bytes=content_bytes,
                mime_type="text/plain"
            )
        
        assert result["status"] == "success"
        assert "artifact_uri" in result
        assert result["version"] == 1
        assert "artifact://TestApp/user123/session456/test.txt?version=1" == result["artifact_uri"]

    @pytest.mark.asyncio
    async def test_process_upload_invalid_filename(self, mock_artifact_service, mock_component):
        """Test upload processing with invalid filename."""
        content_bytes = b"Test content"
        
        result = await process_artifact_upload(
            artifact_service=mock_artifact_service,
            component=mock_component,
            user_id="user123",
            session_id="session456",
            filename="../invalid.txt",  # Invalid filename
            content_bytes=content_bytes,
            mime_type="text/plain"
        )
        
        assert result["status"] == "error"
        assert result["error"] == "invalid_filename"
        assert "Invalid filename" in result["message"]

    @pytest.mark.asyncio
    async def test_process_upload_empty_file(self, mock_artifact_service, mock_component):
        """Test upload processing with empty file."""
        result = await process_artifact_upload(
            artifact_service=mock_artifact_service,
            component=mock_component,
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            content_bytes=b"",  # Empty content
            mime_type="text/plain"
        )
        
        assert result["status"] == "error"
        assert result["error"] == "empty_file"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_process_upload_with_metadata_json(self, mock_artifact_service, mock_component):
        """Test upload processing with metadata JSON."""
        content_bytes = b"Test content"
        metadata_json = '{"description": "Test file", "author": "Test User"}'
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "success",
                "data_version": 1,
                "metadata_version": 1,
                "message": "Saved successfully"
            }
            
            result = await process_artifact_upload(
                artifact_service=mock_artifact_service,
                component=mock_component,
                user_id="user123",
                session_id="session456",
                filename="test.txt",
                content_bytes=content_bytes,
                mime_type="text/plain",
                metadata_json=metadata_json
            )
        
        assert result["status"] == "success"
        
        # Verify metadata was passed to save function
        mock_save.assert_called_once()
        call_args = mock_save.call_args[1]
        assert call_args["metadata_dict"]["description"] == "Test file"
        assert call_args["metadata_dict"]["author"] == "Test User"

    @pytest.mark.asyncio
    async def test_process_upload_invalid_metadata_json(self, mock_artifact_service, mock_component):
        """Test upload processing with invalid metadata JSON."""
        content_bytes = b"Test content"
        metadata_json = '{"invalid": json}'  # Invalid JSON
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "success",
                "data_version": 1,
                "metadata_version": 1,
                "message": "Saved successfully"
            }
            
            result = await process_artifact_upload(
                artifact_service=mock_artifact_service,
                component=mock_component,
                user_id="user123",
                session_id="session456",
                filename="test.txt",
                content_bytes=content_bytes,
                mime_type="text/plain",
                metadata_json=metadata_json
            )
        
        # Should succeed but ignore invalid metadata
        assert result["status"] == "success"
        
        # Verify empty metadata dict was passed
        mock_save.assert_called_once()
        call_args = mock_save.call_args[1]
        assert call_args["metadata_dict"] == {}


class TestFormatMetadataForLlm:
    """Test the format_metadata_for_llm function."""

    def test_format_basic_metadata(self):
        """Test formatting basic metadata."""
        metadata = {
            "filename": "test.txt",
            "version": 1,
            "description": "Test file",
            "mime_type": "text/plain",
            "size_bytes": 1024
        }
        
        result = format_metadata_for_llm(metadata)
        
        assert "test.txt" in result
        assert "v1" in result
        assert "Test file" in result
        assert "text/plain" in result
        assert "1024 bytes" in result

    def test_format_metadata_with_schema(self):
        """Test formatting metadata with schema information."""
        metadata = {
            "filename": "data.json",
            "version": 2,
            "mime_type": "application/json",
            "size_bytes": 2048,
            "schema": {
                "type": "application/json",
                "inferred": True,
                "structure": {"name": "str", "age": "int"}
            }
        }
        
        result = format_metadata_for_llm(metadata)
        
        assert "data.json" in result
        assert "v2" in result
        assert "application/json" in result
        assert "(Inferred)" in result
        assert '"name": "str"' in result

    def test_format_metadata_with_csv_schema(self):
        """Test formatting metadata with CSV schema."""
        metadata = {
            "filename": "data.csv",
            "version": 1,
            "mime_type": "text/csv",
            "schema": {
                "type": "text/csv",
                "inferred": True,
                "columns": ["name", "age", "email"]
            }
        }
        
        result = format_metadata_for_llm(metadata)
        
        assert "data.csv" in result
        assert "Columns: name,age,email" in result

    def test_format_metadata_with_schema_error(self):
        """Test formatting metadata with schema error."""
        metadata = {
            "filename": "broken.json",
            "version": 1,
            "schema": {
                "type": "application/json",
                "inferred": False,
                "error": "JSON parsing failed"
            }
        }
        
        result = format_metadata_for_llm(metadata)
        
        assert "broken.json" in result
        assert "Schema Error: JSON parsing failed" in result

    def test_format_metadata_with_custom_fields(self):
        """Test formatting metadata with custom fields."""
        metadata = {
            "filename": "custom.txt",
            "version": 1,
            "author": "John Doe",
            "tags": ["important", "draft"],
            "priority": "high"
        }
        
        result = format_metadata_for_llm(metadata)
        
        assert "custom.txt" in result
        assert "author: John Doe" in result
        assert "tags:" in result
        assert "priority: high" in result

    def test_format_metadata_minimal(self):
        """Test formatting minimal metadata."""
        metadata = {}
        
        result = format_metadata_for_llm(metadata)
        
        assert "Unknown Filename" in result
        assert "N/A" in result


class TestDecodeAndGetBytes:
    """Test the decode_and_get_bytes function."""

    def test_decode_text_content(self):
        """Test decoding text-based content."""
        content_str = "This is plain text content"
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_mime_type', return_value=True):
            result_bytes, final_mime_type = decode_and_get_bytes(
                content_str, "text/plain", "[test]"
            )
        
        assert result_bytes == content_str.encode("utf-8")
        assert final_mime_type == "text/plain"

    def test_decode_base64_content(self):
        """Test decoding base64 binary content."""
        original_bytes = b"Binary content here"
        content_str = base64.b64encode(original_bytes).decode("ascii")
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_mime_type', return_value=False):
            result_bytes, final_mime_type = decode_and_get_bytes(
                content_str, "application/octet-stream", "[test]"
            )
        
        assert result_bytes == original_bytes
        assert final_mime_type == "application/octet-stream"

    def test_decode_invalid_base64_fallback(self):
        """Test fallback to text when base64 decoding fails."""
        content_str = "Not valid base64 content!"
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_mime_type', return_value=False):
            result_bytes, final_mime_type = decode_and_get_bytes(
                content_str, "application/octet-stream", "[test]"
            )
        
        # Should fallback to text/plain when base64 decoding fails
        assert result_bytes == content_str.encode("utf-8")
        assert final_mime_type == "text/plain"

    def test_decode_unicode_text_content(self):
        """Test decoding Unicode text content."""
        content_str = "Unicode content: café, résumé, naïve"
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_mime_type', return_value=True):
            result_bytes, final_mime_type = decode_and_get_bytes(
                content_str, "text/plain", "[test]"
            )
        
        assert result_bytes == content_str.encode("utf-8")
        assert final_mime_type == "text/plain"


class TestGetLatestArtifactVersion:
    """Test the get_latest_artifact_version function."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock(spec=BaseArtifactService)
        return service

    @pytest.mark.asyncio
    async def test_get_latest_version_success(self, mock_artifact_service):
        """Test successful retrieval of latest version."""
        mock_artifact_service.list_versions = AsyncMock(return_value=[1, 2, 3, 5, 4])
        
        result = await get_latest_artifact_version(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt"
        )
        
        assert result == 5  # Maximum version

    @pytest.mark.asyncio
    async def test_get_latest_version_no_versions(self, mock_artifact_service):
        """Test handling when no versions exist."""
        mock_artifact_service.list_versions = AsyncMock(return_value=[])
        
        result = await get_latest_artifact_version(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt"
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_version_service_error(self, mock_artifact_service):
        """Test handling of service errors."""
        mock_artifact_service.list_versions = AsyncMock(side_effect=Exception("Service error"))
        
        result = await get_latest_artifact_version(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt"
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_version_no_list_versions_method(self):
        """Test handling when service doesn't support list_versions."""
        service_without_method = Mock()
        # Don't add list_versions method
        
        result = await get_latest_artifact_version(
            artifact_service=service_without_method,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt"
        )
        
        assert result is None


class TestLoadArtifactContentOrMetadata:
    """Test the load_artifact_content_or_metadata function."""

    @pytest.fixture
    def mock_artifact_service(self):
        """Mock artifact service for testing."""
        service = Mock(spec=BaseArtifactService)
        return service

    @pytest.fixture
    def mock_component(self):
        """Mock component for testing."""
        component = Mock()
        component.get_config.return_value = 10000  # text_artifact_content_max_length
        return component

    @pytest.mark.asyncio
    async def test_load_metadata_success(self, mock_artifact_service):
        """Test successful metadata loading."""
        # Mock the artifact part
        metadata_dict = {"filename": "test.txt", "mime_type": "text/plain", "size_bytes": 100}
        metadata_json = json.dumps(metadata_dict)
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "application/json"
        mock_part.inline_data.data = metadata_json.encode("utf-8")
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1, 2, 3])
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            version="latest",
            load_metadata_only=True
        )
        
        assert result["status"] == "success"
        assert result["filename"] == "test.txt"
        assert result["version"] == 3  # Latest version
        assert result["metadata"] == metadata_dict

    @pytest.mark.asyncio
    async def test_load_text_content_success(self, mock_artifact_service, mock_component):
        """Test successful text content loading."""
        content = "This is test content"
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "text/plain"
        mock_part.inline_data.data = content.encode("utf-8")
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_file', return_value=True):
            result = await load_artifact_content_or_metadata(
                artifact_service=mock_artifact_service,
                app_name="testapp",
                user_id="user123",
                session_id="session456",
                filename="test.txt",
                version=1,
                component=mock_component
            )
        
        assert result["status"] == "success"
        assert result["filename"] == "test.txt"
        assert result["version"] == 1
        assert result["content"] == content
        assert result["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_load_binary_content_success(self, mock_artifact_service, mock_component):
        """Test successful binary content loading."""
        binary_data = b"\x89PNG\r\n\x1a\n"
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "image/png"
        mock_part.inline_data.data = binary_data
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_file', return_value=False):
            result = await load_artifact_content_or_metadata(
                artifact_service=mock_artifact_service,
                app_name="testapp",
                user_id="user123",
                session_id="session456",
                filename="image.png",
                version=1,
                component=mock_component
            )
        
        assert result["status"] == "success"
        assert result["filename"] == "image.png"
        assert result["version"] == 1
        assert result["mime_type"] == "image/png"
        assert result["size_bytes"] == len(binary_data)
        assert "Binary data" in result["content"]

    @pytest.mark.asyncio
    async def test_load_raw_bytes_success(self, mock_artifact_service):
        """Test successful raw bytes loading."""
        binary_data = b"Raw binary data"
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "application/octet-stream"
        mock_part.inline_data.data = binary_data
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="data.bin",
            version=1,
            return_raw_bytes=True
        )
        
        assert result["status"] == "success"
        assert result["filename"] == "data.bin"
        assert result["version"] == 1
        assert result["raw_bytes"] == binary_data
        assert result["size_bytes"] == len(binary_data)

    @pytest.mark.asyncio
    async def test_load_content_truncation(self, mock_artifact_service, mock_component):
        """Test content truncation when exceeding max length."""
        long_content = "x" * 20000  # Long content
        
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "text/plain"
        mock_part.inline_data.data = long_content.encode("utf-8")
        
        mock_artifact_service.load_artifact = AsyncMock(return_value=mock_part)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        # Set max_content_length to small value
        mock_component.get_config.return_value = 1000
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_file', return_value=True):
            result = await load_artifact_content_or_metadata(
                artifact_service=mock_artifact_service,
                app_name="testapp",
                user_id="user123",
                session_id="session456",
                filename="long.txt",
                version=1,
                component=mock_component
            )
        
        assert result["status"] == "success"
        assert len(result["content"]) == 1003  # 1000 + "..."
        assert result["content"].endswith("...")
        assert "truncated" in result["message_to_llm"]

    @pytest.mark.asyncio
    async def test_load_artifact_not_found(self, mock_artifact_service):
        """Test handling of artifact not found."""
        mock_artifact_service.load_artifact = AsyncMock(return_value=None)
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="missing.txt",
            version=1
        )
        
        assert result["status"] == "not_found"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_load_invalid_version_string(self, mock_artifact_service):
        """Test handling of invalid version string."""
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            version="invalid"
        )
        
        assert result["status"] == "error"
        assert "Invalid version" in result["message"]

    @pytest.mark.asyncio
    async def test_load_negative_version(self, mock_artifact_service):
        """Test handling of negative version number."""
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            version=-1
        )
        
        assert result["status"] == "error"
        assert "positive integer" in result["message"]

    @pytest.mark.asyncio
    async def test_load_latest_version_resolution_failure(self, mock_artifact_service):
        """Test handling of latest version resolution failure."""
        mock_artifact_service.list_versions = AsyncMock(side_effect=Exception("List error"))
        
        result = await load_artifact_content_or_metadata(
            artifact_service=mock_artifact_service,
            app_name="testapp",
            user_id="user123",
            session_id="session456",
            filename="test.txt",
            version="latest"
        )
        
        assert result["status"] == "not_found"
        assert "Could not determine latest version" in result["message"]


class TestArtifactHelpersIntegration:
    """Integration tests for artifact helper functions."""

    @pytest.mark.asyncio
    async def test_complete_artifact_workflow(self):
        """Test complete artifact workflow from upload to retrieval."""
        # Mock services
        mock_artifact_service = Mock(spec=BaseArtifactService)
        mock_artifact_service.save_artifact = AsyncMock(return_value=1)
        mock_artifact_service.load_artifact = AsyncMock()
        mock_artifact_service.list_versions = AsyncMock(return_value=[1])
        
        mock_component = Mock()
        mock_component.get_config.side_effect = lambda key, default=None: {
            "name": "TestApp",
            "schema_max_keys": DEFAULT_SCHEMA_MAX_KEYS,
            "text_artifact_content_max_length": 10000
        }.get(key, default)
        
        # Step 1: Process upload
        content_bytes = b'{"name": "test", "value": 42}'
        
        upload_result = await process_artifact_upload(
            artifact_service=mock_artifact_service,
            component=mock_component,
            user_id="user123",
            session_id="session456",
            filename="test.json",
            content_bytes=content_bytes,
            mime_type="application/json"
        )
        
        assert upload_result["status"] == "success"
        assert "artifact_uri" in upload_result
        
        # Step 2: Parse the generated URI
        parsed_uri = parse_artifact_uri(upload_result["artifact_uri"])
        assert parsed_uri["app_name"] == "TestApp"
        assert parsed_uri["user_id"] == "user123"
        assert parsed_uri["filename"] == "test.json"
        
        # Step 3: Mock loading the artifact back
        mock_part = Mock()
        mock_part.inline_data = Mock()
        mock_part.inline_data.mime_type = "application/json"
        mock_part.inline_data.data = content_bytes
        mock_artifact_service.load_artifact.return_value = mock_part
        
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_file', return_value=True):
            load_result = await load_artifact_content_or_metadata(
                artifact_service=mock_artifact_service,
                app_name="TestApp",
                user_id="user123",
                session_id="session456",
                filename="test.json",
                version=1,
                component=mock_component
            )
        
        assert load_result["status"] == "success"
        assert load_result["content"] == content_bytes.decode("utf-8")

    def test_filename_safety_and_extension_workflow(self):
        """Test filename safety and extension correction workflow."""
        # Test unsafe filename
        unsafe_filename = "../malicious.txt"
        assert not is_filename_safe(unsafe_filename)
        
        # Test safe filename with wrong extension
        filename_with_wrong_ext = "document.txt"
        corrected_filename = ensure_correct_extension(filename_with_wrong_ext, "pdf")
        assert corrected_filename == "document.pdf"
        assert is_filename_safe(corrected_filename)
        
        # Test URI formatting with corrected filename
        uri = format_artifact_uri("app", "user", "session", corrected_filename, 1)
        parsed = parse_artifact_uri(uri)
        assert parsed["filename"] == "document.pdf"

    def test_schema_inference_workflow(self):
        """Test schema inference workflow for different content types."""
        # JSON content
        json_data = {"name": "test", "items": [1, 2, 3]}
        json_bytes = json.dumps(json_data).encode("utf-8")
        json_schema = _infer_schema(json_bytes, "application/json")
        
        assert json_schema["inferred"] is True
        assert "structure" in json_schema
        assert json_schema["structure"]["name"] == "str"
        
        # CSV content
        csv_content = "name,age\nJohn,30\nJane,25"
        csv_bytes = csv_content.encode("utf-8")
        csv_schema = _infer_schema(csv_bytes, "text/csv")
        
        assert csv_schema["inferred"] is True
        assert "columns" in csv_schema
        assert csv_schema["columns"] == ["name", "age"]
        
        # YAML content
        yaml_data = {"config": {"debug": True, "port": 8080}}
        yaml_bytes = yaml.safe_dump(yaml_data).encode("utf-8")
        yaml_schema = _infer_schema(yaml_bytes, "application/yaml")
        
        assert yaml_schema["inferred"] is True
        assert "structure" in yaml_schema

    def test_metadata_formatting_workflow(self):
        """Test metadata formatting workflow."""
        # Create comprehensive metadata
        metadata = {
            "filename": "test_data.csv",
            "version": 2,
            "description": "Test dataset",
            "mime_type": "text/csv",
            "size_bytes": 2048,
            "author": "Test User",
            "schema": {
                "type": "text/csv",
                "inferred": True,
                "columns": ["id", "name", "value"]
            },
            "custom_field": "custom_value"
        }
        
        # Format for LLM
        formatted = format_metadata_for_llm(metadata)
        
        # Verify all important information is included
        assert "test_data.csv" in formatted
        assert "v2" in formatted
        assert "Test dataset" in formatted
        assert "text/csv" in formatted
        assert "2048 bytes" in formatted
        assert "Test User" in formatted
        assert "Columns: id,name,value" in formatted
        assert "custom_field: custom_value" in formatted

    def test_error_handling_consistency(self):
        """Test consistent error handling across functions."""
        # Test invalid JSON in schema inference
        invalid_json = b'{"invalid": json}'
        schema = _infer_schema(invalid_json, "application/json")
        assert schema["inferred"] is False
        assert schema["error"] is not None
        
        # Test invalid URI parsing
        with pytest.raises(ValueError):
            parse_artifact_uri("invalid://uri")
        
        # Test unsafe filename
        assert not is_filename_safe("../unsafe")
        
        # Test invalid base64 decoding fallback
        with patch('solace_agent_mesh.agent.utils.artifact_helpers.is_text_based_mime_type', return_value=False):
            result_bytes, final_mime_type = decode_and_get_bytes(
                "invalid base64", "application/octet-stream", "[test]"
            )
            assert final_mime_type == "text/plain"  # Fallback


# Test fixtures for common test data
@pytest.fixture
def sample_json_metadata():
    """Sample JSON metadata for testing."""
    return {
        "filename": "data.json",
        "version": 1,
        "mime_type": "application/json",
        "size_bytes": 1024,
        "description": "Sample JSON data",
        "schema": {
            "type": "application/json",
            "inferred": True,
            "structure": {"name": "str", "age": "int", "active": "bool"}
        }
    }


@pytest.fixture
def sample_csv_metadata():
    """Sample CSV metadata for testing."""
    return {
        "filename": "data.csv",
        "version": 2,
        "mime_type": "text/csv",
        "size_bytes": 2048,
        "description": "Sample CSV data",
        "schema": {
            "type": "text/csv",
            "inferred": True,
            "columns": ["id", "name", "email", "age"]
        }
    }


class TestArtifactHelpersWithFixtures:
    """Tests using fixtures for consistent test data."""

    def test_format_json_metadata(self, sample_json_metadata):
        """Test formatting JSON metadata using fixture."""
        result = format_metadata_for_llm(sample_json_metadata)
        
        assert "data.json" in result
        assert "v1" in result
        assert "Sample JSON data" in result
        assert "application/json" in result
        assert '"name": "str"' in result

    def test_format_csv_metadata(self, sample_csv_metadata):
        """Test formatting CSV metadata using fixture."""
        result = format_metadata_for_llm(sample_csv_metadata)
        
        assert "data.csv" in result
        assert "v2" in result
        assert "Sample CSV data" in result
        assert "text/csv" in result
        assert "Columns: id,name,email,age" in result

    def test_uri_operations_with_fixtures(self, sample_json_metadata):
        """Test URI operations using fixture data."""
        filename = sample_json_metadata["filename"]
        version = sample_json_metadata["version"]
        
        # Format URI
        uri = format_artifact_uri("testapp", "user123", "session456", filename, version)
        
        # Parse URI
        parsed = parse_artifact_uri(uri)
        
        assert parsed["filename"] == filename
        assert parsed["version"] == version
        assert parsed["app_name"] == "testapp"

    def test_filename_operations_with_fixtures(self, sample_csv_metadata):
        """Test filename operations using fixture data."""
        filename = sample_csv_metadata["filename"]
        
        # Test safety
        assert is_filename_safe(filename)
        
        # Test extension correction
        corrected = ensure_correct_extension(filename, "csv")
        assert corrected == filename  # Should be unchanged
        
        # Test with wrong extension
        wrong_ext_filename = filename.replace(".csv", ".txt")
        corrected = ensure_correct_extension(wrong_ext_filename, "csv")
        assert corrected == filename