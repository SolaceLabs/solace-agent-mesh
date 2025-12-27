"""
Unit tests for executor tool schema parsing.

Tests for the _build_schema_from_config function that parses YAML parameter
configurations into ADK schemas, including detection of 'type: artifact'
for artifact pre-loading.
"""

import pytest
from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.executors.executor_tool import (
    _build_schema_from_config,
    SchemaParseResult,
)
from solace_agent_mesh.agent.tools.artifact_types import ArtifactContentInfo


class TestBuildSchemaFromConfigBasicTypes:
    """Test basic type handling in schema parsing."""

    def test_string_type(self):
        """String type should be parsed correctly."""
        config = {
            "properties": {
                "name": {"type": "string", "description": "User name"}
            },
            "required": ["name"]
        }
        result = _build_schema_from_config(config)

        assert isinstance(result, SchemaParseResult)
        assert result.schema.type == adk_types.Type.OBJECT
        assert "name" in result.schema.properties
        assert result.schema.properties["name"].type == adk_types.Type.STRING

    def test_integer_type(self):
        """Integer type should be parsed correctly."""
        config = {
            "properties": {
                "count": {"type": "integer"}
            }
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["count"].type == adk_types.Type.INTEGER

    def test_number_type(self):
        """Number/float type should be parsed correctly."""
        config = {
            "properties": {
                "price": {"type": "number"}
            }
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["price"].type == adk_types.Type.NUMBER

    def test_boolean_type(self):
        """Boolean type should be parsed correctly."""
        config = {
            "properties": {
                "enabled": {"type": "boolean"}
            }
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["enabled"].type == adk_types.Type.BOOLEAN

    def test_array_of_strings(self):
        """Array of strings should be parsed correctly."""
        config = {
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["tags"].type == adk_types.Type.ARRAY
        assert result.schema.properties["tags"].items.type == adk_types.Type.STRING


class TestBuildSchemaFromConfigArtifactType:
    """Test artifact type detection and translation."""

    def test_artifact_type_translated_to_string(self):
        """'type: artifact' should be translated to string for LLM."""
        config = {
            "properties": {
                "input_file": {
                    "type": "artifact",
                    "description": "Input file to process"
                }
            },
            "required": ["input_file"]
        }
        result = _build_schema_from_config(config)

        # Schema should show STRING type for LLM
        assert result.schema.properties["input_file"].type == adk_types.Type.STRING
        assert result.schema.properties["input_file"].description == "Input file to process"

    def test_artifact_type_detected_in_result(self):
        """Artifact parameters should be tracked in result.artifact_params."""
        config = {
            "properties": {
                "input_file": {"type": "artifact"}
            }
        }
        result = _build_schema_from_config(config)

        assert "input_file" in result.artifact_params
        assert result.artifact_params["input_file"].is_artifact is True
        assert result.artifact_params["input_file"].is_list is False

    def test_array_of_artifacts_translated_to_array_of_strings(self):
        """Array of artifacts should be translated to array of strings."""
        config = {
            "properties": {
                "input_files": {
                    "type": "array",
                    "items": {"type": "artifact"},
                    "description": "Multiple input files"
                }
            }
        }
        result = _build_schema_from_config(config)

        # Schema should show ARRAY of STRING
        assert result.schema.properties["input_files"].type == adk_types.Type.ARRAY
        assert result.schema.properties["input_files"].items.type == adk_types.Type.STRING

    def test_array_of_artifacts_detected_as_list(self):
        """Array of artifacts should be tracked with is_list=True."""
        config = {
            "properties": {
                "input_files": {
                    "type": "array",
                    "items": {"type": "artifact"}
                }
            }
        }
        result = _build_schema_from_config(config)

        assert "input_files" in result.artifact_params
        assert result.artifact_params["input_files"].is_artifact is True
        assert result.artifact_params["input_files"].is_list is True


class TestBuildSchemaFromConfigMixedParams:
    """Test schemas with mixed artifact and regular parameters."""

    def test_mixed_artifact_and_regular_params(self):
        """Schema with both artifact and regular params should work correctly."""
        config = {
            "properties": {
                "input_file": {
                    "type": "artifact",
                    "description": "File to process"
                },
                "output_name": {
                    "type": "string",
                    "description": "Output filename"
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum rows to process"
                }
            },
            "required": ["input_file", "output_name"]
        }
        result = _build_schema_from_config(config)

        # Check schema types
        assert result.schema.properties["input_file"].type == adk_types.Type.STRING
        assert result.schema.properties["output_name"].type == adk_types.Type.STRING
        assert result.schema.properties["max_rows"].type == adk_types.Type.INTEGER

        # Only input_file should be in artifact_params
        assert "input_file" in result.artifact_params
        assert "output_name" not in result.artifact_params
        assert "max_rows" not in result.artifact_params

    def test_multiple_artifact_params(self):
        """Multiple artifact parameters should all be detected."""
        config = {
            "properties": {
                "file1": {"type": "artifact"},
                "file2": {"type": "artifact"},
                "files_list": {
                    "type": "array",
                    "items": {"type": "artifact"}
                }
            }
        }
        result = _build_schema_from_config(config)

        assert len(result.artifact_params) == 3
        assert result.artifact_params["file1"].is_list is False
        assert result.artifact_params["file2"].is_list is False
        assert result.artifact_params["files_list"].is_list is True


class TestBuildSchemaFromConfigFormats:
    """Test different config format styles."""

    def test_properties_format(self):
        """Standard JSON Schema properties format should work."""
        config = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        result = _build_schema_from_config(config)

        assert result.schema.type == adk_types.Type.OBJECT
        assert "name" in result.schema.properties
        assert "age" in result.schema.properties
        assert result.schema.required == ["name"]

    def test_simple_format(self):
        """Simple {param: type} format should work."""
        config = {
            "name": "string",
            "count": "integer",
            "enabled": "boolean"
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["name"].type == adk_types.Type.STRING
        assert result.schema.properties["count"].type == adk_types.Type.INTEGER
        assert result.schema.properties["enabled"].type == adk_types.Type.BOOLEAN

    def test_simple_format_with_artifact(self):
        """Simple format with artifact type should work."""
        config = {
            "input_file": "artifact",
            "output_name": "string"
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["input_file"].type == adk_types.Type.STRING
        assert "input_file" in result.artifact_params

    def test_simple_format_with_dict_value(self):
        """Simple format with dict value should work."""
        config = {
            "name": {"type": "string", "description": "User name"},
            "file": {"type": "artifact"}
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["name"].type == adk_types.Type.STRING
        assert result.schema.properties["name"].description == "User name"
        assert "file" in result.artifact_params


class TestBuildSchemaFromConfigEdgeCases:
    """Test edge cases and empty configs."""

    def test_empty_config(self):
        """Empty config should return empty schema."""
        result = _build_schema_from_config({})

        assert result.schema.type == adk_types.Type.OBJECT
        assert result.schema.properties == {}
        assert result.artifact_params == {}

    def test_none_config(self):
        """None config should return empty schema."""
        # The function should handle None gracefully
        result = _build_schema_from_config(None)

        assert result.schema.type == adk_types.Type.OBJECT
        assert result.schema.properties == {}

    def test_nullable_parameter(self):
        """Nullable parameter should have nullable=True in schema."""
        config = {
            "properties": {
                "optional_file": {
                    "type": "artifact",
                    "nullable": True
                }
            }
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["optional_file"].nullable is True

    def test_type_aliases(self):
        """Type aliases (str, int, etc.) should work."""
        config = {
            "name": "str",
            "count": "int",
            "price": "float",
            "enabled": "bool",
            "items": "list",
            "metadata": "dict"
        }
        result = _build_schema_from_config(config)

        assert result.schema.properties["name"].type == adk_types.Type.STRING
        assert result.schema.properties["count"].type == adk_types.Type.INTEGER
        assert result.schema.properties["price"].type == adk_types.Type.NUMBER
        assert result.schema.properties["enabled"].type == adk_types.Type.BOOLEAN
        assert result.schema.properties["items"].type == adk_types.Type.ARRAY
        assert result.schema.properties["metadata"].type == adk_types.Type.OBJECT


class TestSchemaParseResult:
    """Test the SchemaParseResult class."""

    def test_schema_parse_result_attributes(self):
        """SchemaParseResult should have schema and artifact_params."""
        config = {
            "properties": {
                "file": {"type": "artifact"},
                "name": {"type": "string"}
            }
        }
        result = _build_schema_from_config(config)

        assert isinstance(result.schema, adk_types.Schema)
        assert isinstance(result.artifact_params, dict)

    def test_artifact_content_info_in_result(self):
        """artifact_params should contain ArtifactContentInfo instances."""
        config = {
            "properties": {
                "file": {"type": "artifact"}
            }
        }
        result = _build_schema_from_config(config)

        info = result.artifact_params["file"]
        assert isinstance(info, ArtifactContentInfo)
        assert info.is_artifact is True
