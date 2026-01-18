"""
Unit tests for ExecutorBasedTool behavior.

Tests the tool execution behavior and the factory function for creating tools
from configuration.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.executors.executor_tool import (
    ExecutorBasedTool,
    create_executor_tool_from_config,
)
from solace_agent_mesh.agent.tools.executors.base import (
    ToolExecutor,
    ToolExecutionResult,
)
from solace_agent_mesh.agent.tools.tool_result import ToolResult, DataObject


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext for tests."""
    context = MagicMock()
    context._invocation_context = MagicMock()
    context._invocation_context.session_id = "test-session"
    return context


@pytest.fixture
def mock_executor():
    """Create a mock ToolExecutor."""
    executor = MagicMock(spec=ToolExecutor)
    executor.executor_type = "mock"
    executor.execute = AsyncMock()
    return executor


@pytest.fixture
def simple_schema():
    """Create a simple parameter schema."""
    return adk_types.Schema(
        type=adk_types.Type.OBJECT,
        properties={
            "input": adk_types.Schema(type=adk_types.Type.STRING),
        },
        required=["input"],
    )


class TestExecutorBasedToolBehavior:
    """Test ExecutorBasedTool execution behavior."""

    @pytest.mark.asyncio
    async def test_execute_passes_through_tool_result_unchanged(
        self, mock_executor, mock_tool_context, simple_schema
    ):
        """When executor returns ToolResult, it's passed through unchanged."""
        tool = ExecutorBasedTool(
            name="test_tool",
            description="A test tool",
            parameters_schema=simple_schema,
            executor=mock_executor,
        )

        # Executor returns a ToolResult
        expected_result = ToolResult.ok(
            "Done",
            data={"count": 42},
            data_objects=[DataObject(name="out.txt", content="output")],
        )
        mock_executor.execute.return_value = expected_result

        result = await tool._run_async_impl(
            args={"input": "test"},
            tool_context=mock_tool_context,
        )

        # Should be the exact same ToolResult object
        assert result is expected_result
        assert isinstance(result, ToolResult)
        assert result.data == {"count": 42}
        assert len(result.data_objects) == 1

    @pytest.mark.asyncio
    async def test_execute_converts_tool_execution_result_to_dict(
        self, mock_executor, mock_tool_context, simple_schema
    ):
        """When executor returns ToolExecutionResult, it's converted to dict."""
        tool = ExecutorBasedTool(
            name="test_tool",
            description="A test tool",
            parameters_schema=simple_schema,
            executor=mock_executor,
        )

        # Executor returns a ToolExecutionResult (not ToolResult)
        mock_executor.execute.return_value = ToolExecutionResult.ok(
            data={"result": "processed"},
            metadata={"timing": 0.5},
        )

        result = await tool._run_async_impl(
            args={"input": "test"},
            tool_context=mock_tool_context,
        )

        # Should be converted to dict
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert result["data"] == {"result": "processed"}
        assert result["metadata"] == {"timing": 0.5}

    @pytest.mark.asyncio
    async def test_result_conversion_nests_data_to_avoid_collisions(
        self, mock_executor, mock_tool_context, simple_schema
    ):
        """Result data should be nested under 'data' key, not spread."""
        tool = ExecutorBasedTool(
            name="test_tool",
            description="A test tool",
            parameters_schema=simple_schema,
            executor=mock_executor,
        )

        # Return data with a key that might collide with status
        mock_executor.execute.return_value = ToolExecutionResult.ok(
            data={"status": "custom_status", "value": 123},
        )

        result = await tool._run_async_impl(
            args={"input": "test"},
            tool_context=mock_tool_context,
        )

        # The top-level status should be "success", not "custom_status"
        assert result["status"] == "success"
        # Data should be nested, preserving the original "status" key
        assert result["data"]["status"] == "custom_status"
        assert result["data"]["value"] == 123

    @pytest.mark.asyncio
    async def test_execute_error_result_conversion(
        self, mock_executor, mock_tool_context, simple_schema
    ):
        """Error results are converted correctly."""
        tool = ExecutorBasedTool(
            name="test_tool",
            description="A test tool",
            parameters_schema=simple_schema,
            executor=mock_executor,
        )

        mock_executor.execute.return_value = ToolExecutionResult.fail(
            error="Something went wrong",
            error_code="ERR_001",
        )

        result = await tool._run_async_impl(
            args={"input": "test"},
            tool_context=mock_tool_context,
        )

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["message"] == "Something went wrong"
        assert result["error_code"] == "ERR_001"


class TestCreateExecutorToolFromConfig:
    """Test the factory function for creating tools from config."""

    def test_creates_tool_with_python_executor(self):
        """Factory creates tool with Python executor."""
        config = {
            "name": "python_tool",
            "description": "A Python-based tool",
            "executor": "python",
            "module": "mymodule",
            "function": "myfunction",
            "parameters": {
                "properties": {
                    "input": {"type": "string", "description": "Input value"},
                },
                "required": ["input"],
            },
        }

        tool = create_executor_tool_from_config(config)

        assert tool.tool_name == "python_tool"
        assert tool.tool_description == "A Python-based tool"
        assert tool._executor.executor_type == "python"

    # Lambda executor test removed - Lambda support will be added in a future branch
    # as a top-level tool_type: lambda (not nested under executor)

    def test_raises_on_missing_required_fields(self):
        """Factory raises ValueError for missing required fields."""
        # Missing 'name'
        with pytest.raises(ValueError, match="Missing required field: name"):
            create_executor_tool_from_config({
                "description": "A tool",
                "executor": "python",
                "module": "m",
                "function": "f",
            })

        # Missing 'description'
        with pytest.raises(ValueError, match="Missing required field: description"):
            create_executor_tool_from_config({
                "name": "test",
                "executor": "python",
                "module": "m",
                "function": "f",
            })

        # Missing 'executor'
        with pytest.raises(ValueError, match="Missing required field: executor"):
            create_executor_tool_from_config({
                "name": "test",
                "description": "A tool",
                "module": "m",
                "function": "f",
            })

    def test_raises_on_missing_executor_specific_fields(self):
        """Factory raises ValueError for missing executor-specific fields."""
        # Python executor missing 'module'
        with pytest.raises(ValueError, match="Missing required fields.*module"):
            create_executor_tool_from_config({
                "name": "test",
                "description": "A tool",
                "executor": "python",
                "function": "f",
            })

        # Lambda executor test removed - Lambda support will be added in a future branch

    def test_raises_on_unknown_executor_type(self):
        """Factory raises ValueError for unknown executor type."""
        with pytest.raises(ValueError, match="Unknown executor type: unknown"):
            create_executor_tool_from_config({
                "name": "test",
                "description": "A tool",
                "executor": "unknown",
            })

    def test_detects_artifact_params_from_schema(self):
        """Factory detects artifact parameters from 'type: artifact' in schema."""
        config = {
            "name": "artifact_tool",
            "description": "A tool with artifact params",
            "executor": "python",
            "module": "m",
            "function": "f",
            "parameters": {
                "properties": {
                    "input_file": {
                        "type": "artifact",
                        "description": "An input artifact",
                    },
                    "regular_param": {
                        "type": "string",
                        "description": "A regular string",
                    },
                    "file_list": {
                        "type": "array",
                        "items": {"type": "artifact"},
                        "description": "List of artifacts",
                    },
                },
                "required": ["input_file"],
            },
        }

        tool = create_executor_tool_from_config(config)

        # Should detect artifact params
        assert "input_file" in tool.artifact_params
        assert tool.artifact_params["input_file"].is_artifact is True
        assert tool.artifact_params["input_file"].is_list is False

        # Should detect list of artifacts
        assert "file_list" in tool.artifact_params
        assert tool.artifact_params["file_list"].is_artifact is True
        assert tool.artifact_params["file_list"].is_list is True

        # Regular params should not be in artifact_params
        assert "regular_param" not in tool.artifact_params

    def test_explicit_artifact_content_args_config(self):
        """Factory respects explicit artifact_content_args config."""
        config = {
            "name": "artifact_tool",
            "description": "A tool",
            "executor": "python",
            "module": "m",
            "function": "f",
            "parameters": {
                "properties": {
                    "file": {"type": "string"},  # Not type: artifact
                },
            },
            "artifact_content_args": ["file"],  # Explicitly marked
        }

        tool = create_executor_tool_from_config(config)

        # Should be marked as artifact even though schema says string
        assert "file" in tool.artifact_params
        assert tool.artifact_params["file"].is_artifact is True

    def test_tool_config_passed_to_tool(self):
        """Factory passes tool_config to the tool."""
        config = {
            "name": "test",
            "description": "A tool",
            "executor": "python",
            "module": "m",
            "function": "f",
            "tool_config": {"custom_setting": "value"},
        }

        tool = create_executor_tool_from_config(config)

        assert tool.tool_config == {"custom_setting": "value"}
