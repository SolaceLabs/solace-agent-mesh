"""Tests for OpenAPI audit logging callbacks."""
import pytest
from unittest.mock import Mock, patch

from solace_agent_mesh.agent.adk.callbacks import (
    audit_log_openapi_tool_invocation_start,
    audit_log_openapi_tool_execution_result,
)


@pytest.fixture
def mock_component():
    """Create a mock SamAgentComponent."""
    component = Mock()
    component.agent_name = "TestAgent"
    component.namespace = "test"
    component.log_identifier = "[TestAgent]"
    return component


@pytest.fixture
def mock_openapi_tool():
    """Create a mock OpenAPI RestApiTool with origin attribute."""
    tool = Mock()
    tool.__class__.__name__ = "RestApiTool"
    tool.name = "test_api_operation"

    # SAM sets the 'origin' attribute at initialization for OpenAPI tools
    tool.origin = "openapi"

    # RestApiTool has an 'operation' attribute when created from OpenAPI specs
    tool.operation = Mock()
    tool.operation.operationId = "testOperation"

    # RestApiTool has an 'endpoint' attribute
    tool.endpoint = Mock()
    tool.endpoint.base_url = "https://api.example.com"
    tool.endpoint.method = "POST"
    tool.endpoint.path = "/posts/{id}"

    return tool


@pytest.fixture
def mock_non_openapi_tool():
    """Create a mock non-OpenAPI tool (no origin='openapi')."""
    tool = Mock()
    tool.__class__.__name__ = "RegularTool"
    tool.name = "regular_tool"

    # Non-OpenAPI tools either have no origin or a different origin value
    tool.origin = "builtin"  # Or could be None, "mcp", etc.

    tool.operation = None  # No operation attribute
    delattr(tool, 'specification_url')  # No specification_url either

    return tool


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext."""
    context = Mock()
    context.function_call_id = "fc_test123"
    context.state = {}

    # Mock invocation context
    invocation_context = Mock()
    session = Mock()
    session.id = "sess_abc123"
    session.user_id = "user_xyz789"
    invocation_context.session = session
    context._invocation_context = invocation_context

    return context


class TestAuditCallbacks:
    """Test audit callback functions."""

    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    def test_invocation_start_skips_non_openapi_tool(
        self, mock_log, mock_component, mock_non_openapi_tool, mock_tool_context
    ):
        """Test callback skips non-OpenAPI tools (no logging)."""
        audit_log_openapi_tool_invocation_start(
            mock_non_openapi_tool, {}, mock_tool_context, mock_component
        )

        # Should not have logged anything
        mock_log.info.assert_not_called()
        mock_log.error.assert_not_called()

    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    def test_invocation_start_logs_openapi_tool(
        self, mock_log, mock_component, mock_openapi_tool, mock_tool_context
    ):
        """Test callback logs OpenAPI tool invocation."""
        args = {}

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        # Verify log.info was called
        assert mock_log.info.called
        call_args = mock_log.info.call_args

        # Check log message format
        assert "[openapi-tool]" in call_args[0][0]
        assert "Tool call:" in call_args[0][0]

        # Check structured logging extra data contains required fields
        extra_data = call_args[1]["extra"]
        assert "user_id" in extra_data
        assert "agent_id" in extra_data
        assert "tool_name" in extra_data
        assert "session_id" in extra_data
        assert "operation_id" in extra_data
        assert "tool_uri" in extra_data
        assert extra_data["user_id"] == "user_xyz789"
        assert extra_data["tool_name"] == "test_api_operation"
        assert extra_data["operation_id"] == "testOperation"
        assert extra_data["tool_uri"] == "https://api.example.com/posts/{id}"

        # Verify start time was stored for latency calculation
        assert "audit_start_time_ms" in mock_tool_context.state

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    async def test_execution_result_skips_non_openapi_tool(
        self, mock_log, mock_component, mock_non_openapi_tool, mock_tool_context
    ):
        """Test callback skips non-OpenAPI tools."""
        result = await audit_log_openapi_tool_execution_result(
            mock_non_openapi_tool, {}, mock_tool_context, {}, mock_component
        )

        assert result is None
        # Should not have logged anything
        mock_log.info.assert_not_called()
        mock_log.error.assert_not_called()

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks.time')
    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    async def test_execution_result_logs_success(
        self, mock_log, mock_time, mock_component, mock_openapi_tool, mock_tool_context
    ):
        """Test callback logs successful execution with latency."""
        # Simulate start time was recorded
        mock_tool_context.state["audit_start_time_ms"] = 1000000
        mock_time.time.return_value = 1000.450  # 450ms later

        args = {}
        response = {"result": "success"}  # Success response (no "error" key)

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        assert result is None

        # Verify log.info was called (success case uses info, not error)
        assert mock_log.info.called
        call_args = mock_log.info.call_args

        # Check log message format (it's a template string)
        assert "[openapi-tool]" in call_args[0][0]
        assert "completed" in call_args[0][0]
        assert "Latency:" in call_args[0][0]

        # Check that latency value is passed as argument
        assert 450 in call_args[0]  # Latency value in args

        # Check structured logging extra data
        extra_data = call_args[1]["extra"]
        assert extra_data["user_id"] == "user_xyz789"
        assert extra_data["agent_id"] == "TestAgent"
        assert extra_data["tool_uri"] == "https://api.example.com/posts/{id}"
        assert extra_data["operation_id"] == "testOperation"

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks.time')
    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    async def test_execution_result_logs_error_with_type(
        self, mock_log, mock_time, mock_component, mock_openapi_tool, mock_tool_context
    ):
        """Test callback logs error with type classification."""
        # Simulate start time
        mock_tool_context.state["audit_start_time_ms"] = 1000000
        mock_time.time.return_value = 1000.050  # 50ms later

        args = {}
        response = {
            "error": {"type": "validation_error", "details": "Invalid input"}
        }

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        assert result is None

        # Verify log.error was called (error case)
        assert mock_log.error.called
        call_args = mock_log.error.call_args

        # Check log message format
        log_message = call_args[0][0]
        assert "[openapi-tool]" in log_message
        assert "failed" in log_message
        assert "Path: /posts/{id}" in log_message
        assert "Error Type: validation_error" in log_message
        assert "50ms" in log_message

        # Check structured logging extra data
        extra_data = call_args[1]["extra"]
        assert extra_data["error_type"] == "validation_error"
        assert extra_data["endpoint_path"] == "/posts/{id}"
        assert extra_data["tool_uri"] == "https://api.example.com/posts/{id}"
        # Should NOT log error details/message
        assert "details" not in extra_data
        assert "Invalid input" not in str(call_args)

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    async def test_execution_result_logs_pending_auth(
        self, mock_log, mock_component, mock_openapi_tool, mock_tool_context
    ):
        """Test callback logs pending auth as warning."""
        args = {}
        response = {"pending": True}

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        assert result is None

        # Verify log.warning was called (pending auth case)
        assert mock_log.warning.called
        call_args = mock_log.warning.call_args

        # Check log message format
        assert "[openapi-tool]" in call_args[0][0]
        assert "pending auth" in call_args[0][0]

        # Check structured logging extra data
        extra_data = call_args[1]["extra"]
        assert extra_data["status"] == "pending_auth"
        assert extra_data["tool_uri"] == "https://api.example.com/posts/{id}"

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.callbacks.log')
    async def test_execution_result_classifies_error_string(
        self, mock_log, mock_component, mock_openapi_tool, mock_tool_context
    ):
        """Test callback classifies error from string content."""
        args = {}
        response = {
            "error": "Connection timeout after 30 seconds"
        }

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        assert result is None

        # Verify error was classified as timeout
        assert mock_log.error.called
        call_args = mock_log.error.call_args

        log_message = call_args[0][0]
        assert "Error Type: timeout" in log_message

        extra_data = call_args[1]["extra"]
        assert extra_data["error_type"] == "timeout"
