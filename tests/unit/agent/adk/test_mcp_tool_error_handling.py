"""Tests for error handling in EmbedResolvingMCPTool."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, PropertyMock
from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPTool,
)


# Test how error handling behaves, this was written to investigate if errors would propogate up.
class TestMcpToolErrorHandling:
    """Test that exceptions from MCP tools propagate correctly."""

    @pytest.mark.asyncio
    async def test_mcp_tool_exception_propagates(self):
        """Test that exceptions from _run_async_impl propagate through try/catch."""
        # Create a mock original tool that raises an exception
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_tool.auth_discovery = None
        mock_original_tool._mcp_session_manager = Mock()

        # Make _run_async_impl raise an exception
        test_error = ValueError("Tool execution failed")
        mock_original_tool._run_async_impl = AsyncMock(side_effect=test_error)

        # Create EmbedResolvingMCPTool
        embed_tool = EmbedResolvingMCPTool(
            original_mcp_tool=mock_original_tool,
            tool_config=None,
            credential_manager=None,
        )

        # Create mock tool context
        mock_session = Mock()
        mock_session.user_id = "user123"
        mock_session.id = "session456"

        mock_tool_context = Mock()
        mock_tool_context.session = mock_session
        mock_tool_context.agent_name = "test-agent"

        # Test that exception propagates
        with pytest.raises(ValueError) as exc_info:
            await embed_tool._run_async_impl(
                args={"test": "arg"}, tool_context=mock_tool_context, credential=None
            )

        assert str(exc_info.value) == "Tool execution failed"
        assert exc_info.value is test_error

    @pytest.mark.asyncio
    async def test_mcp_tool_runtime_error_propagates(self):
        """Test that RuntimeError exceptions propagate correctly."""
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_tool.auth_discovery = None
        mock_original_tool._mcp_session_manager = Mock()

        test_error = RuntimeError("Connection timeout")
        mock_original_tool._run_async_impl = AsyncMock(side_effect=test_error)

        embed_tool = EmbedResolvingMCPTool(
            original_mcp_tool=mock_original_tool,
            tool_config=None,
            credential_manager=None,
        )

        mock_session = Mock()
        mock_session.user_id = "user123"
        mock_session.id = "session456"

        mock_tool_context = Mock()
        mock_tool_context.session = mock_session
        mock_tool_context.agent_name = "test-agent"

        with pytest.raises(RuntimeError) as exc_info:
            await embed_tool._run_async_impl(
                args={}, tool_context=mock_tool_context, credential=None
            )

        assert "Connection timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_tool_success_no_exception(self):
        """Test that successful execution doesn't raise exceptions."""
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_tool.auth_discovery = None
        mock_original_tool._mcp_session_manager = Mock()

        # Make _run_async_impl return successfully
        expected_result = {"status": "success", "data": "test"}
        mock_original_tool._run_async_impl = AsyncMock(return_value=expected_result)

        embed_tool = EmbedResolvingMCPTool(
            original_mcp_tool=mock_original_tool,
            tool_config=None,
            credential_manager=None,
        )

        mock_session = Mock()
        mock_session.user_id = "user123"
        mock_session.id = "session456"

        mock_tool_context = Mock()
        mock_tool_context.session = mock_session
        mock_tool_context.agent_name = "test-agent"

        # Should not raise exception
        result = await embed_tool._run_async_impl(
            args={"test": "arg"}, tool_context=mock_tool_context, credential=None
        )

        assert result == expected_result
