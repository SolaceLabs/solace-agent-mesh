"""
Unit tests for ExecutorBasedTool behavior.

Tests the tool execution behavior.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.executors.executor_tool import (
    ExecutorBasedTool,
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
