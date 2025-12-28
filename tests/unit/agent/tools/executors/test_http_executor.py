"""
Unit tests for HTTPExecutor behavior.

Tests the execute() method behavior with mocked aiohttp at the boundary.
We verify what request is sent and how different responses are handled.
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from solace_agent_mesh.agent.tools.executors.http_executor import HTTPExecutor
from solace_agent_mesh.agent.tools.executors.base import ToolExecutionResult
from solace_agent_mesh.agent.tools.tool_result import ToolResult, DataObject


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext for tests."""
    context = MagicMock()
    context._invocation_context = MagicMock()
    context._invocation_context.session_id = "test-session-123"
    context._invocation_context.user_id = "test-user"
    context._invocation_context.app_name = "test-app"
    return context


@pytest.fixture
def http_executor():
    """Create an HTTPExecutor instance for testing.

    Uses include_context=False to simplify testing.
    """
    return HTTPExecutor(
        endpoint="https://api.example.com/tool",
        method="POST",
        include_context=False,
    )


def create_mock_response(
    status: int = 200,
    json_data: dict = None,
    text_data: str = None,
    content_type: str = "application/json",
):
    """Helper to create a mock aiohttp response."""
    response = AsyncMock()
    response.status = status
    response.headers = {"Content-Type": content_type}

    if json_data is not None:
        response.json = AsyncMock(return_value=json_data)
        response.text = AsyncMock(return_value=json.dumps(json_data))
    else:
        response.json = AsyncMock(side_effect=json.JSONDecodeError("", "", 0))
        response.text = AsyncMock(return_value=text_data or "")

    return response


class TestHTTPExecutorBehavior:
    """Test HTTPExecutor.execute() behavior with mocked aiohttp."""

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result_when_response_is_tool_result_json(
        self, http_executor, mock_tool_context
    ):
        """When HTTP response is a serialized ToolResult, execute() returns a ToolResult."""
        tool_result_json = {
            "_schema": "ToolResult",
            "_schema_version": "1.0",
            "status": "success",
            "message": "Done",
            "data": {"count": 42},
            "data_objects": [],
            "error_code": None,
        }

        mock_response = create_mock_response(json_data=tool_result_json)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolResult)
        assert result.status == "success"
        assert result.message == "Done"
        assert result.data == {"count": 42}

    @pytest.mark.asyncio
    async def test_execute_returns_success_when_response_is_simple_success(
        self, http_executor, mock_tool_context
    ):
        """When HTTP response has {success: true}, execute() returns ToolExecutionResult.ok()."""
        simple_response = {
            "success": True,
            "data": {"result": "processed"},
        }

        mock_response = create_mock_response(json_data=simple_response)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.data == {"result": "processed"}

    @pytest.mark.asyncio
    async def test_execute_returns_data_when_response_is_raw_json(
        self, http_executor, mock_tool_context
    ):
        """When HTTP response is raw JSON (no success field), wrap it as data."""
        raw_response = {"key": "value", "count": 123}

        mock_response = create_mock_response(json_data=raw_response)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.data == raw_response

    @pytest.mark.asyncio
    async def test_execute_handles_http_error_status(
        self, http_executor, mock_tool_context
    ):
        """When HTTP returns error status, execute() returns a failure."""
        error_response = {"error": "Not found", "message": "Resource not found"}

        mock_response = create_mock_response(status=404, json_data=error_response)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "HTTP_404"

    @pytest.mark.asyncio
    async def test_execute_handles_connection_error(
        self, http_executor, mock_tool_context
    ):
        """When aiohttp raises ClientError, execute() returns a failure."""
        with patch.object(http_executor, "_session") as mock_session:
            # Import aiohttp to get the exception class
            import aiohttp

            mock_session.request = MagicMock(
                side_effect=aiohttp.ClientError("Connection failed")
            )

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "CLIENT_ERROR"
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(
        self, http_executor, mock_tool_context
    ):
        """When request times out, execute() returns a failure."""
        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(side_effect=asyncio.TimeoutError())

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_execute_fails_when_not_initialized(self, mock_tool_context):
        """When session is None (not initialized), execute() returns error."""
        executor = HTTPExecutor(
            endpoint="https://api.example.com/tool",
        )
        # _session is None by default (not initialized)

        result = await executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_execute_sends_args_in_body_for_post(
        self, mock_tool_context
    ):
        """When args_location='body' (default), args are sent in request body."""
        executor = HTTPExecutor(
            endpoint="https://api.example.com/tool",
            method="POST",
            args_location="body",
            include_context=False,
        )

        captured_request = {}

        async def capture_request(*args, **kwargs):
            captured_request.update(kwargs)
            return create_mock_response(json_data={"success": True})

        with patch.object(executor, "_session") as mock_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = create_mock_response(
                json_data={"success": True}
            )
            mock_session.request = MagicMock(return_value=mock_cm)

            await executor.execute(
                args={"name": "test", "value": 42},
                tool_context=mock_tool_context,
                tool_config={},
            )

        # Check that request was called with json body containing args
        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"] == {"args": {"name": "test", "value": 42}}
        assert call_kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_execute_sends_args_as_query_params_when_configured(
        self, mock_tool_context
    ):
        """When args_location='query', args are sent as query parameters."""
        executor = HTTPExecutor(
            endpoint="https://api.example.com/tool",
            method="GET",
            args_location="query",
            include_context=False,
        )

        with patch.object(executor, "_session") as mock_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = create_mock_response(
                json_data={"success": True}
            )
            mock_session.request = MagicMock(return_value=mock_cm)

            await executor.execute(
                args={"name": "test", "value": 42},
                tool_context=mock_tool_context,
                tool_config={},
            )

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["params"] == {"name": "test", "value": "42"}
        assert call_kwargs["json"] is None

    @pytest.mark.asyncio
    async def test_execute_includes_bearer_auth_header(
        self, mock_tool_context
    ):
        """When auth_type='bearer', Authorization header is included."""
        executor = HTTPExecutor(
            endpoint="https://api.example.com/tool",
            auth_type="bearer",
            auth_token="my-secret-token",
            include_context=False,
        )

        with patch.object(executor, "_session") as mock_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = create_mock_response(
                json_data={"success": True}
            )
            mock_session.request = MagicMock(return_value=mock_cm)

            await executor.execute(
                args={},
                tool_context=mock_tool_context,
                tool_config={},
            )

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-secret-token"

    @pytest.mark.asyncio
    async def test_execute_includes_api_key_header(
        self, mock_tool_context
    ):
        """When auth_type='api_key', API key header is included."""
        executor = HTTPExecutor(
            endpoint="https://api.example.com/tool",
            auth_type="api_key",
            auth_token="my-api-key",
            api_key_header="X-Custom-Key",
            include_context=False,
        )

        with patch.object(executor, "_session") as mock_session:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = create_mock_response(
                json_data={"success": True}
            )
            mock_session.request = MagicMock(return_value=mock_cm)

            await executor.execute(
                args={},
                tool_context=mock_tool_context,
                tool_config={},
            )

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["X-Custom-Key"] == "my-api-key"

    @pytest.mark.asyncio
    async def test_execute_with_tool_result_containing_data_objects(
        self, http_executor, mock_tool_context
    ):
        """ToolResult with DataObjects from HTTP response is deserialized correctly."""
        tool_result_json = {
            "_schema": "ToolResult",
            "_schema_version": "1.0",
            "status": "success",
            "message": "Generated files",
            "data": None,
            "data_objects": [
                {
                    "name": "output.txt",
                    "content": "Generated content",
                    "is_binary": False,
                    "mime_type": "text/plain",
                    "disposition": "artifact",
                    "description": "Output file",
                    "preview": None,
                    "metadata": None,
                }
            ],
            "error_code": None,
        }

        mock_response = create_mock_response(json_data=tool_result_json)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolResult)
        assert len(result.data_objects) == 1
        assert result.data_objects[0].name == "output.txt"
        assert result.data_objects[0].content == "Generated content"

    @pytest.mark.asyncio
    async def test_execute_handles_simple_failure_response(
        self, http_executor, mock_tool_context
    ):
        """When HTTP response has {success: false}, execute() returns failure."""
        failure_response = {
            "success": False,
            "error": "Something went wrong",
            "error_code": "PROCESSING_ERROR",
        }

        mock_response = create_mock_response(json_data=failure_response)

        with patch.object(http_executor, "_session") as mock_session:
            mock_session.request = MagicMock(return_value=AsyncMock())
            mock_session.request.return_value.__aenter__.return_value = mock_response

            result = await http_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.error_code == "PROCESSING_ERROR"
