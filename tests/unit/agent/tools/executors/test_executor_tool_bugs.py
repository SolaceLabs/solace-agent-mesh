"""
Tests exposing critical bugs in executor tool loading.

These tests document bugs found during code review and should FAIL
until the bugs are fixed.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from google.genai import types as adk_types


class TestArgumentNameMismatchBug:
    """
    Bug #1: setup.py passes `artifact_content_args` but ExecutorBasedTool
    expects `artifact_args`.

    This causes a TypeError at runtime when loading executor tools with
    artifact pre-loading configured.
    """

    def test_executor_based_tool_accepts_artifact_content_args(self):
        """
        ExecutorBasedTool should accept artifact_content_args parameter
        for backward compatibility with existing YAML configs.

        Currently FAILS with: TypeError: __init__() got an unexpected
        keyword argument 'artifact_content_args'
        """
        from solace_agent_mesh.agent.tools.executors.executor_tool import (
            ExecutorBasedTool,
        )
        from solace_agent_mesh.agent.tools.executors.base import ToolExecutor

        # Create a mock executor
        mock_executor = MagicMock(spec=ToolExecutor)
        mock_executor.executor_type = "python"

        # Create a simple schema
        schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "input_file": adk_types.Schema(type=adk_types.Type.STRING),
            },
            required=["input_file"],
        )

        # This should NOT raise TypeError
        # Currently it does because ExecutorBasedTool expects `artifact_args`
        # but setup.py passes `artifact_content_args`
        tool = ExecutorBasedTool(
            name="test_tool",
            description="A test tool",
            parameters_schema=schema,
            executor=mock_executor,
            artifact_content_args=["input_file"],  # This is what setup.py passes
        )

        # Verify the artifact args were set correctly
        assert "input_file" in tool.artifact_args


class TestUnifiedSchemaBuilder:
    """
    Tests verifying that the unified schema builder from executor_tool.py
    works correctly.
    """

    def test_unified_schema_builder_handles_artifact_type(self):
        """
        The unified _build_schema_from_config correctly handles artifact types.
        """
        from solace_agent_mesh.agent.tools.executors.executor_tool import (
            _build_schema_from_config,
        )

        params_config = {
            "properties": {
                "input_file": {
                    "type": "artifact",
                    "description": "An artifact to process",
                },
                "regular_param": {
                    "type": "string",
                    "description": "A regular string",
                },
            },
            "required": ["input_file"],
        }

        result = _build_schema_from_config(params_config)

        # Should produce a valid schema
        assert result.schema is not None
        assert "input_file" in result.schema.properties
        assert "regular_param" in result.schema.properties

        # Artifact type should be translated to STRING for the LLM
        assert result.schema.properties["input_file"].type == adk_types.Type.STRING
        assert result.schema.properties["regular_param"].type == adk_types.Type.STRING

        # Should correctly identify artifact params
        assert "input_file" in result.artifact_params
        assert result.artifact_params["input_file"].is_artifact is True
        assert result.artifact_params["input_file"].is_list is False

        # Regular param should NOT be in artifact_params
        assert "regular_param" not in result.artifact_params

    def test_unified_schema_builder_handles_artifact_arrays(self):
        """
        The unified schema builder correctly handles arrays of artifacts.
        """
        from solace_agent_mesh.agent.tools.executors.executor_tool import (
            _build_schema_from_config,
        )

        params_config = {
            "properties": {
                "input_files": {
                    "type": "array",
                    "items": {"type": "artifact"},
                    "description": "Multiple artifacts to process",
                },
            },
        }

        result = _build_schema_from_config(params_config)

        # Should correctly identify as a list of artifacts
        assert "input_files" in result.artifact_params
        assert result.artifact_params["input_files"].is_artifact is True
        assert result.artifact_params["input_files"].is_list is True
