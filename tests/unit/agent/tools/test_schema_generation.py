"""
Unit tests for schema generation from function signatures.

Tests for the _get_schema_from_signature function that converts Python function
type hints into ADK schemas, including detection of ArtifactContent types for
artifact pre-loading.
"""

import pytest
from typing import List, Optional, Dict, Any
from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.dynamic_tool import (
    _get_schema_from_signature,
    _SchemaDetectionResult,
)
from solace_agent_mesh.agent.tools.artifact_types import ArtifactContent
from solace_agent_mesh.agent.utils.tool_context_facade import ToolContextFacade


class TestSchemaFromSignatureBasicTypes:
    """Test basic type handling in schema generation."""

    def test_string_param(self):
        """String parameter should generate STRING schema."""
        async def tool_func(name: str):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.type == adk_types.Type.OBJECT
        assert "name" in schema.properties
        assert schema.properties["name"].type == adk_types.Type.STRING

    def test_int_param(self):
        """Integer parameter should generate INTEGER schema."""
        async def tool_func(count: int):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["count"].type == adk_types.Type.INTEGER

    def test_float_param(self):
        """Float parameter should generate NUMBER schema."""
        async def tool_func(price: float):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["price"].type == adk_types.Type.NUMBER

    def test_bool_param(self):
        """Boolean parameter should generate BOOLEAN schema."""
        async def tool_func(enabled: bool):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["enabled"].type == adk_types.Type.BOOLEAN

    def test_list_param(self):
        """List parameter should generate ARRAY schema."""
        async def tool_func(items: list):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["items"].type == adk_types.Type.ARRAY

    def test_dict_param(self):
        """Dict parameter should generate OBJECT schema."""
        async def tool_func(metadata: dict):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["metadata"].type == adk_types.Type.OBJECT


class TestSchemaFromSignatureWithArtifacts:
    """Test ArtifactContent handling in schema generation."""

    def test_single_artifact_content_param(self):
        """ArtifactContent param should generate STRING schema."""
        async def tool_func(input_content: ArtifactContent, filename: str):
            pass

        schema = _get_schema_from_signature(tool_func)

        # ArtifactContent should be translated to STRING for LLM
        assert schema.properties["input_content"].type == adk_types.Type.STRING
        assert schema.properties["filename"].type == adk_types.Type.STRING

    def test_list_artifact_content_param(self):
        """List[ArtifactContent] param should generate ARRAY of STRING schema."""
        async def tool_func(input_files: List[ArtifactContent]):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["input_files"].type == adk_types.Type.ARRAY
        assert schema.properties["input_files"].items.type == adk_types.Type.STRING

    def test_optional_artifact_content_param(self):
        """Optional[ArtifactContent] should be nullable STRING."""
        async def tool_func(input_content: Optional[ArtifactContent] = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["input_content"].type == adk_types.Type.STRING
        assert schema.properties["input_content"].nullable is True

    def test_mixed_artifact_and_regular_params(self):
        """Function with mixed param types should work correctly."""
        async def tool_func(
            input_content: ArtifactContent,
            output_name: str,
            max_rows: int,
            include_header: bool = True,
        ):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["input_content"].type == adk_types.Type.STRING
        assert schema.properties["output_name"].type == adk_types.Type.STRING
        assert schema.properties["max_rows"].type == adk_types.Type.INTEGER
        assert schema.properties["include_header"].type == adk_types.Type.BOOLEAN


class TestSchemaFromSignatureWithDetectionResult:
    """Test schema generation with _SchemaDetectionResult for artifact tracking."""

    def test_artifact_detected_in_result(self):
        """ArtifactContent params should be tracked in detection result."""
        async def tool_func(input_content: ArtifactContent, filename: str):
            pass

        detection_result = _SchemaDetectionResult()
        schema = _get_schema_from_signature(tool_func, detection_result=detection_result)

        assert "input_content" in detection_result.artifact_content_params
        assert detection_result.artifact_content_params["input_content"].is_artifact is True
        assert detection_result.artifact_content_params["input_content"].is_list is False

        # filename should NOT be in artifact_content_params
        assert "filename" not in detection_result.artifact_content_params

    def test_list_artifact_detected_as_list(self):
        """List[ArtifactContent] should be detected with is_list=True."""
        async def tool_func(input_files: List[ArtifactContent]):
            pass

        detection_result = _SchemaDetectionResult()
        _get_schema_from_signature(tool_func, detection_result=detection_result)

        assert "input_files" in detection_result.artifact_content_params
        assert detection_result.artifact_content_params["input_files"].is_list is True

    def test_tool_context_facade_detected(self):
        """ToolContextFacade param should be detected and excluded from schema."""
        async def tool_func(
            input_content: ArtifactContent,
            ctx: ToolContextFacade = None,
        ):
            pass

        detection_result = _SchemaDetectionResult()
        schema = _get_schema_from_signature(tool_func, detection_result=detection_result)

        # ctx should be detected but not in schema
        assert detection_result.ctx_facade_param_name == "ctx"
        assert "ctx" not in schema.properties

    def test_artifact_content_args_property(self):
        """detection_result.artifact_content_args should return set of param names."""
        async def tool_func(
            file1: ArtifactContent,
            file2: ArtifactContent,
            name: str,
        ):
            pass

        detection_result = _SchemaDetectionResult()
        _get_schema_from_signature(tool_func, detection_result=detection_result)

        args = detection_result.artifact_content_args
        assert isinstance(args, set)
        assert "file1" in args
        assert "file2" in args
        assert "name" not in args


class TestSchemaFromSignatureRequired:
    """Test required parameter handling."""

    def test_required_params_without_defaults(self):
        """Parameters without defaults should be required."""
        async def tool_func(name: str, count: int):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "name" in schema.required
        assert "count" in schema.required

    def test_optional_params_with_defaults(self):
        """Parameters with defaults should NOT be required."""
        async def tool_func(name: str, count: int = 10, enabled: bool = True):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "name" in schema.required
        assert "count" not in schema.required
        assert "enabled" not in schema.required

    def test_artifact_excluded_from_required_when_optional(self):
        """Optional ArtifactContent should not be in required."""
        async def tool_func(
            input_content: Optional[ArtifactContent] = None,
            name: str = "default",
        ):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "input_content" not in schema.required
        assert "name" not in schema.required


class TestSchemaFromSignatureSpecialParams:
    """Test handling of special parameters that should be excluded."""

    def test_tool_context_excluded(self):
        """tool_context parameter should be excluded from schema."""
        async def tool_func(name: str, tool_context: Any = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "name" in schema.properties
        assert "tool_context" not in schema.properties

    def test_tool_config_excluded(self):
        """tool_config parameter should be excluded from schema."""
        async def tool_func(name: str, tool_config: Dict[str, Any] = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "name" in schema.properties
        assert "tool_config" not in schema.properties

    def test_kwargs_excluded(self):
        """kwargs parameter should be excluded from schema."""
        async def tool_func(name: str, **kwargs):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert "name" in schema.properties
        assert "kwargs" not in schema.properties

    def test_self_excluded(self):
        """self parameter should be excluded from schema."""
        class MyTool:
            async def process(self, name: str):
                pass

        schema = _get_schema_from_signature(MyTool().process)

        assert "name" in schema.properties
        assert "self" not in schema.properties


class TestSchemaFromSignatureEdgeCases:
    """Test edge cases in schema generation."""

    def test_any_type_defaults_to_string(self):
        """Any type should default to STRING."""
        async def tool_func(data: Any):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["data"].type == adk_types.Type.STRING

    def test_unannotated_param_defaults_to_string(self):
        """Unannotated parameters should default to STRING."""
        async def tool_func(name):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["name"].type == adk_types.Type.STRING

    def test_no_params_returns_empty_properties(self):
        """Function with no params should return empty properties."""
        async def tool_func():
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.type == adk_types.Type.OBJECT
        assert schema.properties == {}

    def test_only_special_params_returns_empty_properties(self):
        """Function with only special params should return empty properties."""
        async def tool_func(tool_context: Any = None, tool_config: Dict = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties == {}


class TestSchemaFromSignatureOptionalTypes:
    """Test Optional type handling."""

    def test_optional_string_is_nullable(self):
        """Optional[str] should be nullable STRING."""
        async def tool_func(name: Optional[str] = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["name"].type == adk_types.Type.STRING
        assert schema.properties["name"].nullable is True

    def test_optional_int_is_nullable(self):
        """Optional[int] should be nullable INTEGER."""
        async def tool_func(count: Optional[int] = None):
            pass

        schema = _get_schema_from_signature(tool_func)

        assert schema.properties["count"].type == adk_types.Type.INTEGER
        assert schema.properties["count"].nullable is True
