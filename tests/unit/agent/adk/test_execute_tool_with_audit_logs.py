"""Tests for _execute_tool_with_audit_logs method."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPTool,
)


class TestExecuteToolWithAuditLogs:
    """Test _execute_tool_with_audit_logs method."""

    @pytest.mark.asyncio
    async def test_logs_success_with_duration(self):
        """Test success logging with duration."""
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.name = "test_tool"
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_session_manager = Mock()

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

        async def mock_tool_call():
            return {"result": "success"}

        with patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_success"
        ) as mock_log_success:
            result = await embed_tool._execute_tool_with_audit_logs(
                mock_tool_call, mock_tool_context
            )
            assert result == {"result": "success"}
            mock_log_success.assert_called_once()
            args = mock_log_success.call_args[0]
            assert args[0] == "user123"
            assert args[1] == "test-agent"
            assert args[2] == "test_tool"
            assert args[3] == "session456"
            assert isinstance(args[4], float)
            assert args[4] >= 0

    @pytest.mark.asyncio
    async def test_logs_failure_with_duration(self):
        """Test failure logging with duration."""
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.name = "test_tool"
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_session_manager = Mock()

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

        test_error = ValueError("Tool failed")

        async def mock_tool_call():
            raise test_error

        with patch(
            "solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._log_mcp_tool_failure"
        ) as mock_log_failure:
            with pytest.raises(ValueError) as exc_info:
                await embed_tool._execute_tool_with_audit_logs(
                    mock_tool_call, mock_tool_context
                )
            assert exc_info.value is test_error
            mock_log_failure.assert_called_once()
            args = mock_log_failure.call_args[0]
            assert args[0] == "user123"
            assert args[1] == "test-agent"
            assert args[2] == "test_tool"
            assert args[3] == "session456"
            assert isinstance(args[4], float)
            assert args[4] >= 0
            assert args[5] is test_error

    @pytest.mark.asyncio
    async def test_run_async_impl_calls_audit_logs(self):
        """Test that _run_async_impl calls _execute_tool_with_audit_logs."""
        mock_original_tool = Mock()
        mock_original_tool.name = "test_tool"
        mock_original_tool._mcp_tool = Mock()
        mock_original_tool._mcp_tool.name = "test_tool"
        mock_original_tool._mcp_tool.auth_scheme = None
        mock_original_tool._mcp_tool.auth_credential = None
        mock_original_tool._mcp_session_manager = Mock()
        mock_original_tool._run_async_impl = AsyncMock(return_value={"result": "ok"})

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

        with patch.object(
            embed_tool, "_execute_tool_with_audit_logs", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.return_value = {"result": "ok"}
            result = await embed_tool._run_async_impl(
                args={"test": "data"}, tool_context=mock_tool_context, credential=None
            )
            mock_audit.assert_called_once()
            assert result == {"result": "ok"}
