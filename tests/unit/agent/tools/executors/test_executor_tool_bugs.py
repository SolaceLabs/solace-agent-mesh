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
        from src.solace_agent_mesh.agent.tools.executors.executor_tool import (
            ExecutorBasedTool,
        )
        from src.solace_agent_mesh.agent.tools.executors.base import ToolExecutor

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


class TestFactoryWrongKeyBug:
    """
    Bug #2: create_executor_tool_from_config reads `artifact_args` from config
    but YAML configs and the Pydantic model use `artifact_content_args`.

    This causes artifact pre-loading to be silently ignored when using the
    factory with legacy configs.
    """

    def test_factory_reads_artifact_content_args_from_config(self):
        """
        The factory should read `artifact_content_args` from config, not `artifact_args`.

        Currently FAILS because factory reads wrong key and artifact params
        are not set.
        """
        from src.solace_agent_mesh.agent.tools.executors.executor_tool import (
            create_executor_tool_from_config,
        )

        # This is how configs look in YAML (using artifact_content_args)
        config = {
            "name": "test_tool",
            "description": "A test tool",
            "executor": "python",
            "module": "test_module",
            "function": "test_function",
            "parameters": {
                "input_file": {"type": "string", "description": "Input file"},
            },
            # This is the key used in YAML configs and Pydantic model
            "artifact_content_args": ["input_file"],
        }

        tool = create_executor_tool_from_config(config)

        # The factory should have picked up artifact_content_args
        # Currently FAILS because factory reads "artifact_args" instead
        assert "input_file" in tool.artifact_args, (
            f"Expected 'input_file' in artifact_args, got: {tool.artifact_args}"
        )

    def test_factory_reads_artifact_content_list_args_from_config(self):
        """
        The factory should also read `artifact_content_list_args` from config.
        """
        from src.solace_agent_mesh.agent.tools.executors.executor_tool import (
            create_executor_tool_from_config,
        )

        config = {
            "name": "test_tool",
            "description": "A test tool",
            "executor": "python",
            "module": "test_module",
            "function": "test_function",
            "parameters": {
                "input_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Input files",
                },
            },
            # This is the key used in YAML configs
            "artifact_content_list_args": ["input_files"],
        }

        tool = create_executor_tool_from_config(config)

        # Should recognize list args
        assert "input_files" in tool.artifact_args
        # Should be marked as a list type
        assert tool.artifact_params["input_files"].is_list is True


class TestSetupSchemaBuilderBug:
    """
    Bug #3: setup.py's _build_executor_schema doesn't recognize `type: artifact`.

    FIXED: setup.py now uses _build_schema_from_config from executor_tool.py,
    which correctly handles artifact types.

    The old _build_executor_schema is kept for backward compatibility but is
    deprecated.
    """

    def test_deprecated_schema_builder_still_works(self):
        """
        The deprecated _build_executor_schema should still work for basic types.
        It's kept for backward compatibility.
        """
        from src.solace_agent_mesh.agent.adk.setup import _build_executor_schema

        # Config using basic types
        params_config = {
            "properties": {
                "name": {
                    "type": "string",
                    "description": "A name",
                },
                "count": {
                    "type": "integer",
                    "description": "A count",
                },
            },
            "required": ["name"],
        }

        schema = _build_executor_schema(params_config)

        # The schema should be built correctly
        assert schema is not None
        assert "name" in schema.properties
        assert "count" in schema.properties
        assert schema.properties["name"].type == adk_types.Type.STRING
        assert schema.properties["count"].type == adk_types.Type.INTEGER

    def test_deprecated_schema_builder_limitation_documented(self):
        """
        Document that the deprecated _build_executor_schema doesn't return
        artifact info (this is why it's deprecated).
        """
        from src.solace_agent_mesh.agent.adk.setup import _build_executor_schema

        params_config = {
            "properties": {
                "input_file": {
                    "type": "artifact",
                    "description": "An artifact to process",
                },
            },
        }

        result = _build_executor_schema(params_config)

        # The deprecated function only returns Schema, not artifact info
        assert result is not None
        assert not hasattr(result, 'artifact_params'), (
            "The deprecated _build_executor_schema doesn't return artifact_params. "
            "Use _build_schema_from_config from executor_tool.py instead."
        )


class TestUnifiedSchemaBuilder:
    """
    Tests verifying that setup.py now uses the unified schema builder
    from executor_tool.py.

    FIXED: setup.py now imports and uses _build_schema_from_config,
    eliminating the code duplication and drift issues.
    """

    def test_unified_schema_builder_handles_artifact_type(self):
        """
        The unified _build_schema_from_config correctly handles artifact types.
        """
        from src.solace_agent_mesh.agent.tools.executors.executor_tool import (
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
        from src.solace_agent_mesh.agent.tools.executors.executor_tool import (
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
