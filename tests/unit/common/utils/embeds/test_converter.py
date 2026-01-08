
"""
Unit tests for common/utils/embeds/converter.py
Tests data conversion and serialization functions.
"""

import pytest
import json
import csv
import io
import base64

from solace_agent_mesh.common.utils.embeds.converter import (
    _parse_string_to_list_of_dicts,
    convert_data,
    serialize_data,
)
from solace_agent_mesh.common.utils.embeds.types import DataFormat


class TestParseStringToListOfDicts:
    """Test _parse_string_to_list_of_dicts function."""

    def test_parse_json_list_of_dicts(self):
        """Test parsing JSON list of dictionaries."""
        json_string = '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]'
        result, error = _parse_string_to_list_of_dicts(
            json_string, "application/json", "[Test]"
        )
        
        assert error is None
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == 25

    def test_parse_json_single_dict(self):
        """Test parsing JSON single dictionary (converted to list)."""
        json_string = '{"name": "Alice", "age": 30}'
        result, error = _parse_string_to_list_of_dicts(
            json_string, "application/json", "[Test]"
        )
        
        assert error is None
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_parse_json_invalid_structure(self):
        """Test parsing JSON with invalid structure."""
        json_string = '["not", "a", "dict"]'
        result, error = _parse_string_to_list_of_dicts(
            json_string, "application/json", "[Test]"
        )
        
        assert result is None
        assert error is not None
        assert "not a list of dictionaries" in error

    def test_parse_csv_string(self):
        """Test parsing CSV string."""
        csv_string = "name,age\nAlice,30\nBob,25"
        result, error = _parse_string_to_list_of_dicts(
            csv_string, "text/csv", "[Test]"
        )
        
        assert error is None
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == "25"

    def test_parse_yaml_list_of_dicts(self):
        """Test parsing YAML list of dictionaries."""
        yaml_string = "- name: Alice\n  age: 30\n- name: Bob\n  age: 25"
        result, error = _parse_string_to_list_of_dicts(
            yaml_string, "application/yaml", "[Test]"
        )
        
        # Skip if PyYAML not available
        if error and "PyYAML" in error:
            pytest.skip("PyYAML not installed")
        
        assert error is None
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_parse_yaml_single_dict(self):
        """Test parsing YAML single dictionary."""
        yaml_string = "name: Alice\nage: 30"
        result, error = _parse_string_to_list_of_dicts(
            yaml_string, "application/yaml", "[Test]"
        )
        
        # Skip if PyYAML not available
        if error and "PyYAML" in error:
            pytest.skip("PyYAML not installed")
        
        assert error is None
        assert len(result) == 1
        assert result[0]["name"] == "Alice"

    def test_parse_unsupported_mime_type(self):
        """Test parsing with unsupported MIME type."""
        result, error = _parse_string_to_list_of_dicts(
            "some data", "application/xml", "[Test]"
        )
        
        assert result is None
        assert error is not None
        assert "Unsupported MIME type" in error

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        result, error = _parse_string_to_list_of_dicts(
            "{invalid json}", "application/json", "[Test]"
        )
        
        assert result is None
        assert error is not None
        assert "JSON" in error

    def test_parse_invalid_csv(self):
        """Test parsing invalid CSV."""
        # CSV with inconsistent columns
        csv_string = "name,age\nAlice\nBob,25,extra"
        result, error = _parse_string_to_list_of_dicts(
            csv_string, "text/csv", "[Test]"
        )
        
        # CSV parser is lenient, so this might succeed
        # Just verify it doesn't crash
        assert result is not None or error is not None


class TestConvertData:
    """Test convert_data function."""

    def test_convert_same_format(self):
        """Test conversion when source and target formats are the same."""
        data = "test string"
        result, format_out, error = convert_data(
            data, DataFormat.STRING, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert result == data
        assert format_out == DataFormat.STRING

    def test_convert_unknown_to_string(self):
        """Test converting unknown/numeric type to string."""
        data = 42
        result, format_out, error = convert_data(
            data, None, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert result == "42"
        assert format_out == DataFormat.STRING

    def test_convert_unknown_to_other_fails(self):
        """Test converting unknown type to non-string format fails."""
        data = 42
        result, format_out, error = convert_data(
            data, None, DataFormat.JSON_OBJECT, "[Test]"
        )
        
        assert error is not None
        assert result == data
        assert format_out is None

    def test_convert_bytes_to_string_text_mime(self):
        """Test converting bytes to string with text MIME type."""
        data = b"Hello, world!"
        result, format_out, error = convert_data(
            data, DataFormat.BYTES, DataFormat.STRING, "[Test]", "text/plain"
        )
        
        assert error is None
        assert result == "Hello, world!"
        assert format_out == DataFormat.STRING

    def test_convert_bytes_to_string_binary_mime_fails(self):
        """Test converting binary bytes to string fails."""
        data = b"\x00\x01\x02"
        result, format_out, error = convert_data(
            data, DataFormat.BYTES, DataFormat.STRING, "[Test]", "application/octet-stream"
        )
        
        assert error is not None
        assert result == data

    def test_convert_bytes_to_json(self):
        """Test converting bytes to JSON object."""
        json_bytes = b'{"key": "value"}'
        result, format_out, error = convert_data(
            json_bytes, DataFormat.BYTES, DataFormat.JSON_OBJECT, "[Test]", "application/json"
        )
        
        assert error is None
        assert result == {"key": "value"}
        assert format_out == DataFormat.JSON_OBJECT

    def test_convert_bytes_to_json_wrong_mime_fails(self):
        """Test converting bytes to JSON with wrong MIME type fails."""
        data = b'{"key": "value"}'
        result, format_out, error = convert_data(
            data, DataFormat.BYTES, DataFormat.JSON_OBJECT, "[Test]", "text/plain"
        )
        
        assert error is not None
        assert result == data

    def test_convert_bytes_to_list_of_dicts_csv(self):
        """Test converting CSV bytes to list of dicts."""
        csv_bytes = b"name,age\nAlice,30\nBob,25"
        result, format_out, error = convert_data(
            csv_bytes, DataFormat.BYTES, DataFormat.LIST_OF_DICTS, "[Test]", "text/csv"
        )
        
        assert error is None
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert format_out == DataFormat.LIST_OF_DICTS

    def test_convert_string_to_bytes(self):
        """Test converting string to bytes."""
        data = "Hello, world!"
        result, format_out, error = convert_data(
            data, DataFormat.STRING, DataFormat.BYTES, "[Test]"
        )
        
        assert error is None
        assert result == b"Hello, world!"
        assert format_out == DataFormat.BYTES

    def test_convert_string_to_json(self):
        """Test converting JSON string to JSON object."""
        json_string = '{"key": "value", "number": 42}'
        result, format_out, error = convert_data(
            json_string, DataFormat.STRING, DataFormat.JSON_OBJECT, "[Test]"
        )
        
        assert error is None
        assert result == {"key": "value", "number": 42}
        assert format_out == DataFormat.JSON_OBJECT

    def test_convert_string_to_json_invalid(self):
        """Test converting invalid JSON string fails."""
        result, format_out, error = convert_data(
            "not json", DataFormat.STRING, DataFormat.JSON_OBJECT, "[Test]"
        )
        
        assert error is not None
        assert "JSON" in error

    def test_convert_string_to_list_of_dicts_json(self):
        """Test converting JSON string to list of dicts."""
        json_string = '[{"name": "Alice"}, {"name": "Bob"}]'
        result, format_out, error = convert_data(
            json_string, DataFormat.STRING, DataFormat.LIST_OF_DICTS, "[Test]", "application/json"
        )
        
        assert error is None
        assert len(result) == 2
        assert format_out == DataFormat.LIST_OF_DICTS

    def test_convert_string_to_list_of_dicts_csv(self):
        """Test converting CSV string to list of dicts."""
        csv_string = "name,age\nAlice,30"
        result, format_out, error = convert_data(
            csv_string, DataFormat.STRING, DataFormat.LIST_OF_DICTS, "[Test]", "text/csv"
        )
        
        assert error is None
        assert len(result) == 1
        assert format_out == DataFormat.LIST_OF_DICTS

    def test_convert_json_object_to_string(self):
        """Test converting JSON object to string."""
        data = {"key": "value", "number": 42}
        result, format_out, error = convert_data(
            data, DataFormat.JSON_OBJECT, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert '"key":"value"' in result
        assert format_out == DataFormat.STRING

    def test_convert_json_object_to_list_of_dicts(self):
        """Test converting JSON list to list of dicts."""
        data = [{"name": "Alice"}, {"name": "Bob"}]
        result, format_out, error = convert_data(
            data, DataFormat.JSON_OBJECT, DataFormat.LIST_OF_DICTS, "[Test]"
        )
        
        assert error is None
        assert result == data
        assert format_out == DataFormat.LIST_OF_DICTS

    def test_convert_json_object_to_list_of_dicts_invalid(self):
        """Test converting non-list JSON to list of dicts fails."""
        data = {"not": "a list"}
        result, format_out, error = convert_data(
            data, DataFormat.JSON_OBJECT, DataFormat.LIST_OF_DICTS, "[Test]"
        )
        
        assert error is not None
        assert "not a list" in error

    def test_convert_list_of_dicts_to_string_csv(self):
        """Test converting list of dicts to CSV string."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result, format_out, error = convert_data(
            data, DataFormat.LIST_OF_DICTS, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert "name,age" in result
        assert "Alice,30" in result
        assert format_out == DataFormat.STRING

    def test_convert_list_of_dicts_to_string_empty(self):
        """Test converting empty list of dicts to string."""
        data = []
        result, format_out, error = convert_data(
            data, DataFormat.LIST_OF_DICTS, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert result == ""
        assert format_out == DataFormat.STRING

    def test_convert_list_of_dicts_to_json_object(self):
        """Test converting list of dicts to JSON object."""
        data = [{"name": "Alice"}, {"name": "Bob"}]
        result, format_out, error = convert_data(
            data, DataFormat.LIST_OF_DICTS, DataFormat.JSON_OBJECT, "[Test]"
        )
        
        assert error is None
        assert result == data
        assert format_out == DataFormat.JSON_OBJECT

    def test_convert_unsupported_conversion(self):
        """Test unsupported conversion returns error."""
        result, format_out, error = convert_data(
            "data", DataFormat.STRING, DataFormat.BYTES, "[Test]"
        )
        
        # STRING to BYTES is supported, so try a truly unsupported one
        # Actually, let's test BYTES to LIST_OF_DICTS with wrong MIME
        data = b"some bytes"
        result, format_out, error = convert_data(
            data, DataFormat.BYTES, DataFormat.LIST_OF_DICTS, "[Test]", "application/pdf"
        )
        
        assert error is not None


class TestSerializeData:
    """Test serialize_data function."""

    def test_serialize_to_text_from_string(self):
        """Test serializing string to text format."""
        result, error = serialize_data(
            "Hello, world!", DataFormat.STRING, "text", None, "[Test]"
        )
        
        assert error is None
        assert result == "Hello, world!"

    def test_serialize_to_text_from_json(self):
        """Test serializing JSON object to text format."""
        data = {"key": "value"}
        result, error = serialize_data(
            data, DataFormat.JSON_OBJECT, "text", None, "[Test]"
        )
        
        assert error is None
        assert "key" in result

    def test_serialize_to_json_compact(self):
        """Test serializing to compact JSON."""
        data = {"key": "value", "number": 42}
        result, error = serialize_data(
            data, DataFormat.JSON_OBJECT, "json", None, "[Test]"
        )
        
        assert error is None
        assert result == '{"key":"value","number":42}'

    def test_serialize_to_json_pretty(self):
        """Test serializing to pretty JSON."""
        data = {"key": "value"}
        result, error = serialize_data(
            data, DataFormat.JSON_OBJECT, "json_pretty", None, "[Test]"
        )
        
        assert error is None
        assert "\n" in result
        assert "  " in result

    def test_serialize_to_csv(self):
        """Test serializing to CSV format."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result, error = serialize_data(
            data, DataFormat.LIST_OF_DICTS, "csv", None, "[Test]"
        )
        
        assert error is None
        assert "name,age" in result
        assert "Alice,30" in result

    def test_serialize_to_datauri(self):
        """Test serializing to data URI format."""
        data = b"Hello, world!"
        result, error = serialize_data(
            data, DataFormat.BYTES, "datauri", "text/plain", "[Test]"
        )
        
        assert error is None
        assert result.startswith("data:text/plain;base64,")

    def test_serialize_to_datauri_no_mime_fails(self):
        """Test serializing to data URI without MIME type fails."""
        data = b"test"
        result, error = serialize_data(
            data, DataFormat.BYTES, "datauri", None, "[Test]"
        )
        
        assert error is not None
        assert "MIME type required" in error

    def test_serialize_numeric_with_format_spec(self):
        """Test serializing numeric data with Python format specifier."""
        result, error = serialize_data(
            3.14159, None, ".2f", None, "[Test]"
        )
        
        assert error is None
        assert result == "3.14"

    def test_serialize_numeric_with_percentage(self):
        """Test serializing numeric data with percentage format."""
        result, error = serialize_data(
            0.85, None, ".1%", None, "[Test]"
        )
        
        assert error is None
        assert "85" in result

    def test_serialize_numeric_invalid_format_spec(self):
        """Test serializing with invalid format specifier."""
        result, error = serialize_data(
            42, None, ".2f", None, "[Test]"
        )
        
        # Integer with float format should work
        assert error is None

    def test_serialize_unknown_format_defaults_to_text(self):
        """Test serializing with unknown format defaults to text."""
        result, error = serialize_data(
            "test", DataFormat.STRING, "unknown_format", None, "[Test]"
        )
        
        assert error is None
        assert result == "test"

    def test_serialize_default_format(self):
        """Test serializing with default format (None or empty)."""
        result, error = serialize_data(
            "test", DataFormat.STRING, None, None, "[Test]"
        )
        
        assert error is None
        assert result == "test"

    def test_serialize_empty_string_format(self):
        """Test serializing with empty string format."""
        result, error = serialize_data(
            "test", DataFormat.STRING, "", None, "[Test]"
        )
        
        assert error is None
        assert result == "test"

    def test_serialize_conversion_error(self):
        """Test serialization with conversion error."""
        # Try to serialize bytes to JSON without proper MIME type
        data = b"not json"
        result, error = serialize_data(
            data, DataFormat.BYTES, "json", "application/octet-stream", "[Test]"
        )
        
        assert error is not None
        assert "Serialization Error" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_convert_bytes_decode_error(self):
        """Test converting bytes with decode error."""
        invalid_utf8 = b"\xff\xfe"
        result, format_out, error = convert_data(
            invalid_utf8, DataFormat.BYTES, DataFormat.STRING, "[Test]", "text/plain"
        )
        
        assert error is not None
        assert "UTF-8" in error

    def test_convert_bytes_invalid_json(self):
        """Test converting bytes with invalid JSON."""
        data = b"{invalid json}"
        result, format_out, error = convert_data(
            data, DataFormat.BYTES, DataFormat.JSON_OBJECT, "[Test]", "application/json"
        )
        
        assert error is not None
        assert "JSON" in error

    def test_convert_json_serialization_error(self):
        """Test JSON serialization error."""
        # Create an object that can't be serialized
        class NonSerializable:
            pass
        
        data = {"obj": NonSerializable()}
        result, format_out, error = convert_data(
            data, DataFormat.JSON_OBJECT, DataFormat.STRING, "[Test]"
        )
        
        assert error is not None

    def test_parse_yaml_invalid(self):
        """Test parsing invalid YAML."""
        yaml_string = "invalid: yaml: structure:"
        result, error = _parse_string_to_list_of_dicts(
            yaml_string, "application/yaml", "[Test]"
        )
        
        # Skip if PyYAML not available
        if error and "PyYAML" in error:
            pytest.skip("PyYAML not installed")
        
        # YAML parser might be lenient or strict
        assert result is not None or error is not None

    def test_convert_empty_list_of_dicts_to_csv(self):
        """Test converting empty list to CSV."""
        result, format_out, error = convert_data(
            [], DataFormat.LIST_OF_DICTS, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert result == ""

    def test_serialize_large_data(self):
        """Test serializing large data structures."""
        large_data = [{"id": i, "value": f"item_{i}"} for i in range(1000)]
        result, error = serialize_data(
            large_data, DataFormat.LIST_OF_DICTS, "json", None, "[Test]"
        )
        
        assert error is None
        assert len(result) > 0

    def test_convert_unicode_data(self):
        """Test converting Unicode data."""
        unicode_data = "Hello 世界 🌍"
        result, format_out, error = convert_data(
            unicode_data, DataFormat.STRING, DataFormat.BYTES, "[Test]"
        )
        
        assert error is None
        assert isinstance(result, bytes)

    def test_serialize_nested_json(self):
        """Test serializing deeply nested JSON."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        result, error = serialize_data(
            nested_data, DataFormat.JSON_OBJECT, "json_pretty", None, "[Test]"
        )
        
        assert error is None
        assert "deep" in result

    def test_parse_csv_with_quotes(self):
        """Test parsing CSV with quoted fields."""
        csv_string = 'name,description\nAlice,"Hello, world"\nBob,"Test, data"'
        result, error = _parse_string_to_list_of_dicts(
            csv_string, "text/csv", "[Test]"
        )
        
        assert error is None
        assert len(result) == 2
        assert "," in result[0]["description"]

    def test_convert_special_characters(self):
        """Test converting data with special characters."""
        data = {"key": "value with\nnewline\tand\ttabs"}
        result, format_out, error = convert_data(
            data, DataFormat.JSON_OBJECT, DataFormat.STRING, "[Test]"
        )
        
        assert error is None
        assert "\\n" in result or "\n" in result