"""
Unit tests for LambdaExecutor behavior.

Tests the execute() method behavior with mocked boto3 at the boundary.
We verify what payload is sent to Lambda and how different responses are handled.

Also tests the streaming mode with mocked httpx.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO

from google.genai import types as adk_types

from solace_agent_mesh.agent.tools.executors.lambda_executor import LambdaExecutor
from solace_agent_mesh.agent.tools.executors.executor_tool import ExecutorBasedTool
from solace_agent_mesh.agent.tools.executors.base import ToolExecutionResult
from solace_agent_mesh.agent.tools.tool_result import ToolResult, DataObject
from solace_agent_mesh.agent.tools.artifact_types import Artifact, ArtifactTypeInfo


def make_lambda_response(payload: dict, function_error: bool = False) -> dict:
    """Helper to create a mock Lambda response."""
    response = {
        "Payload": BytesIO(json.dumps(payload).encode("utf-8")),
        "StatusCode": 200,
    }
    if function_error:
        response["FunctionError"] = "Unhandled"
    return response


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
def lambda_executor():
    """Create a LambdaExecutor instance for testing.

    Uses include_context=False to avoid needing to mock context helpers.
    Tests that need context should create their own executor with include_context=True.
    """
    return LambdaExecutor(
        function_arn="arn:aws:lambda:us-east-1:123456789:function:test-function",
        region="us-east-1",
        include_context=False,
    )


class TestLambdaExecutorBehavior:
    """Test LambdaExecutor.execute() behavior with mocked boto3."""

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result_when_lambda_returns_tool_result_json(
        self, lambda_executor, mock_tool_context
    ):
        """When Lambda returns a serialized ToolResult, execute() returns a ToolResult."""
        tool_result_json = {
            "_schema": "ToolResult",
            "_schema_version": "1.0",
            "status": "success",
            "message": "Done",
            "data": {"count": 42},
            "data_objects": [],
            "error_code": None,
        }

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.return_value = make_lambda_response(tool_result_json)

            result = await lambda_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolResult)
        assert result.status == "success"
        assert result.message == "Done"
        assert result.data == {"count": 42}

    @pytest.mark.asyncio
    async def test_execute_returns_success_when_lambda_returns_simple_success(
        self, lambda_executor, mock_tool_context
    ):
        """When Lambda returns {success: true}, execute() returns ToolExecutionResult.ok()."""
        simple_response = {
            "success": True,
            "data": {"result": "processed"},
        }

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.return_value = make_lambda_response(simple_response)

            result = await lambda_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.data == {"result": "processed"}

    @pytest.mark.asyncio
    async def test_execute_returns_data_when_lambda_returns_raw_dict(
        self, lambda_executor, mock_tool_context
    ):
        """When Lambda returns a raw dict (no success field), wrap it as data."""
        raw_response = {"key": "value", "count": 123}

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.return_value = make_lambda_response(raw_response)

            result = await lambda_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.data == raw_response

    @pytest.mark.asyncio
    async def test_execute_handles_lambda_function_error(
        self, lambda_executor, mock_tool_context
    ):
        """When Lambda returns a FunctionError, execute() returns a failure."""
        error_payload = {
            "errorMessage": "Something went wrong in Lambda",
            "errorType": "RuntimeError",
        }

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.return_value = make_lambda_response(
                error_payload, function_error=True
            )

            result = await lambda_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert "Something went wrong in Lambda" in result.error
        assert result.error_code == "LAMBDA_FUNCTION_ERROR"

    @pytest.mark.asyncio
    async def test_execute_handles_boto_client_error(
        self, lambda_executor, mock_tool_context
    ):
        """When boto3 raises ClientError, execute() returns a failure."""
        # Import the actual exception class for mocking
        with patch(
            "solace_agent_mesh.agent.tools.executors.lambda_executor.ClientError",
            Exception,
        ):
            with patch.object(lambda_executor, "_client") as mock_client:
                # Create a mock ClientError-like exception
                error = Exception("Access Denied")
                error.response = {
                    "Error": {"Code": "AccessDenied", "Message": "Access Denied"}
                }
                mock_client.invoke.side_effect = error

                result = await lambda_executor.execute(
                    args={"input": "test"},
                    tool_context=mock_tool_context,
                    tool_config={},
                )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert "Access Denied" in result.error

    @pytest.mark.asyncio
    async def test_execute_fails_when_not_initialized(self, mock_tool_context):
        """When client is None (not initialized), execute() returns error."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
        )
        # _client is None by default (not initialized)

        result = await executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_execute_serializes_artifact_args_correctly(
        self, lambda_executor, mock_tool_context
    ):
        """Artifact args are serialized to JSON-compatible dict before sending."""
        artifact = Artifact(
            content="file content here",
            filename="data.txt",
            version=1,
            mime_type="text/plain",
            metadata={"author": "test"},
        )

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke

            await lambda_executor.execute(
                args={"input_file": artifact, "name": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        # Verify the artifact was serialized
        assert captured_payload is not None
        serialized_artifact = captured_payload["args"]["input_file"]
        assert serialized_artifact["filename"] == "data.txt"
        assert serialized_artifact["content"] == "file content here"
        assert serialized_artifact["is_binary"] is False
        assert serialized_artifact["mime_type"] == "text/plain"
        # Regular args pass through
        assert captured_payload["args"]["name"] == "test"

    @pytest.mark.asyncio
    async def test_execute_serializes_binary_artifact_as_base64(
        self, lambda_executor, mock_tool_context
    ):
        """Binary artifact content is base64-encoded with is_binary flag."""
        binary_content = b"\x00\x01\x02\xff\xfe"
        artifact = Artifact(
            content=binary_content,
            filename="data.bin",
            version=1,
            mime_type="application/octet-stream",
        )

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke

            await lambda_executor.execute(
                args={"input_file": artifact},
                tool_context=mock_tool_context,
                tool_config={},
            )

        serialized = captured_payload["args"]["input_file"]
        assert serialized["is_binary"] is True
        # Content should be base64-encoded string
        assert isinstance(serialized["content"], str)
        # Verify it decodes back to original
        import base64

        decoded = base64.b64decode(serialized["content"])
        assert decoded == binary_content

    @pytest.mark.asyncio
    async def test_execute_includes_context_when_configured(
        self, mock_tool_context
    ):
        """When include_context=True, session context is included in payload.

        Note: Only session_id and user_id are sent to Lambda. app_name is NOT
        included because Lambda tools can't access the artifact store (artifacts
        are pre-loaded), so app_name serves no purpose in the Lambda context.
        """
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
            include_context=True,
        )

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke
            # Mock the context helper where it's imported from
            with patch(
                "solace_agent_mesh.agent.utils.context_helpers.get_original_session_id",
                return_value="test-session-123",
            ):
                await executor.execute(
                    args={"input": "test"},
                    tool_context=mock_tool_context,
                    tool_config={},
                )

        assert "context" in captured_payload
        assert captured_payload["context"]["session_id"] == "test-session-123"
        assert captured_payload["context"]["user_id"] == "test-user"
        # app_name is intentionally NOT sent - Lambda tools don't need it
        # since they can't access the artifact store (artifacts are pre-loaded)
        assert "app_name" not in captured_payload["context"]

    @pytest.mark.asyncio
    async def test_execute_excludes_context_when_not_configured(
        self, mock_tool_context
    ):
        """When include_context=False, context is not in payload."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
            include_context=False,
        )

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke

            await executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert "context" not in captured_payload

    @pytest.mark.asyncio
    async def test_execute_includes_tool_config_in_payload(
        self, lambda_executor, mock_tool_context
    ):
        """Tool config is always included in the Lambda payload."""
        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke

            await lambda_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={"operation": "process", "mode": "fast"},
            )

        assert captured_payload["tool_config"] == {"operation": "process", "mode": "fast"}

    @pytest.mark.asyncio
    async def test_execute_with_tool_result_containing_data_objects(
        self, lambda_executor, mock_tool_context
    ):
        """ToolResult with DataObjects from Lambda is deserialized correctly."""
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

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.return_value = make_lambda_response(tool_result_json)

            result = await lambda_executor.execute(
                args={},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert isinstance(result, ToolResult)
        assert len(result.data_objects) == 1
        assert result.data_objects[0].name == "output.txt"
        assert result.data_objects[0].content == "Generated content"

    @pytest.mark.asyncio
    async def test_execute_serializes_list_of_artifacts(
        self, lambda_executor, mock_tool_context
    ):
        """List of artifacts is serialized correctly."""
        artifacts = [
            Artifact(
                content="content 1",
                filename="file1.txt",
                version=1,
                mime_type="text/plain",
            ),
            Artifact(
                content=b"\x00\x01",
                filename="file2.bin",
                version=2,
                mime_type="application/octet-stream",
            ),
        ]

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(lambda_executor, "_client") as mock_client:
            mock_client.invoke.side_effect = capture_invoke

            await lambda_executor.execute(
                args={"files": artifacts},
                tool_context=mock_tool_context,
                tool_config={},
            )

        serialized_files = captured_payload["args"]["files"]
        assert len(serialized_files) == 2
        assert serialized_files[0]["filename"] == "file1.txt"
        assert serialized_files[0]["is_binary"] is False
        assert serialized_files[1]["filename"] == "file2.bin"
        assert serialized_files[1]["is_binary"] is True


class TestExecutorBasedToolArtifactPreloading:
    """
    Test the full run_async flow for ExecutorBasedTool with artifact pre-loading.

    This tests that when the LLM provides a filename string for an artifact parameter,
    the framework pre-loads the artifact and the Lambda receives a serialized Artifact.
    """

    @pytest.fixture
    def tool_context_with_artifact_service(self):
        """Create a mock ToolContext with artifact service for pre-loading tests."""
        context = MagicMock()

        # Set up invocation context
        inv_context = MagicMock()
        inv_context.session_id = "test-session-123"
        inv_context.user_id = "test-user"
        inv_context.app_name = "test-app"

        # Set up session context
        session = MagicMock()
        session.user_id = "test-user"
        session.app_name = "test-app"
        inv_context.session = session

        # Set up artifact service
        inv_context.artifact_service = MagicMock()

        context._invocation_context = inv_context
        return context

    @pytest.fixture
    def executor_tool_with_artifact_param(self):
        """Create an ExecutorBasedTool with an artifact parameter."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
            include_context=False,
        )

        schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "input_file": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Input artifact filename",
                ),
                "output_name": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Output filename",
                ),
            },
            required=["input_file"],
        )

        tool = ExecutorBasedTool(
            name="process_artifact",
            description="Process an artifact file",
            parameters_schema=schema,
            executor=executor,
            artifact_params={
                "input_file": ArtifactTypeInfo(is_artifact=True, is_list=False),
            },
        )
        return tool

    @pytest.mark.asyncio
    async def test_run_async_preloads_artifact_and_sends_to_lambda(
        self, executor_tool_with_artifact_param, tool_context_with_artifact_service
    ):
        """
        When run_async receives a filename string for an artifact param,
        it pre-loads the artifact and Lambda receives a serialized Artifact object.
        """
        tool = executor_tool_with_artifact_param
        tool_context = tool_context_with_artifact_service

        # Mock the artifact loading to return artifact content
        artifact_content = "This is the artifact content loaded from storage."

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True, "data": {"processed": True}})

        with patch.object(tool._executor, "_client") as mock_client, \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.load_artifact_content_or_metadata",
                 new_callable=AsyncMock,
             ) as mock_load_artifact, \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.get_original_session_id",
                 return_value="test-session-123",
             ):

            # Configure artifact loading mock
            mock_load_artifact.return_value = {
                "status": "success",
                "content": artifact_content,
                "version": 1,
                "mime_type": "text/plain",
                "metadata": {"author": "test"},
            }

            mock_client.invoke.side_effect = capture_invoke

            # Call run_async with a FILENAME string (not an Artifact object)
            # The framework should pre-load this and convert to Artifact
            result = await tool.run_async(
                args={
                    "input_file": "data.txt",  # Just a filename string
                    "output_name": "result.txt",
                },
                tool_context=tool_context,
            )

        # Verify artifact loading was called
        mock_load_artifact.assert_called_once()
        call_kwargs = mock_load_artifact.call_args[1]
        assert call_kwargs["filename"] == "data.txt"

        # Verify Lambda received a serialized Artifact, not a filename string
        assert captured_payload is not None
        serialized_artifact = captured_payload["args"]["input_file"]

        # Should be a dict (serialized Artifact), not a string
        assert isinstance(serialized_artifact, dict)
        assert serialized_artifact["filename"] == "data.txt"
        assert serialized_artifact["content"] == artifact_content
        assert serialized_artifact["mime_type"] == "text/plain"
        assert serialized_artifact["is_binary"] is False
        assert serialized_artifact["version"] == 1
        assert serialized_artifact["metadata"] == {"author": "test"}

        # Regular params should pass through unchanged
        assert captured_payload["args"]["output_name"] == "result.txt"

    @pytest.mark.asyncio
    async def test_run_async_preloads_binary_artifact(
        self, tool_context_with_artifact_service
    ):
        """Binary artifacts are pre-loaded and base64-encoded for Lambda."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
            include_context=False,
        )

        schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "image": adk_types.Schema(type=adk_types.Type.STRING),
            },
        )

        tool = ExecutorBasedTool(
            name="process_image",
            description="Process an image",
            parameters_schema=schema,
            executor=executor,
            artifact_params={
                "image": ArtifactTypeInfo(is_artifact=True, is_list=False),
            },
        )

        tool_context = tool_context_with_artifact_service
        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00"  # PNG header bytes

        captured_payload = None

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        with patch.object(tool._executor, "_client") as mock_client, \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.load_artifact_content_or_metadata",
                 new_callable=AsyncMock,
             ) as mock_load_artifact, \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.get_original_session_id",
                 return_value="test-session-123",
             ):

            mock_load_artifact.return_value = {
                "status": "success",
                "raw_bytes": binary_content,
                "version": 1,
                "mime_type": "image/png",
                "metadata": {},
            }

            mock_client.invoke.side_effect = capture_invoke

            await tool.run_async(
                args={"image": "photo.png"},
                tool_context=tool_context,
            )

        # Verify binary content is base64 encoded
        serialized = captured_payload["args"]["image"]
        assert serialized["is_binary"] is True
        assert serialized["mime_type"] == "image/png"

        # Decode and verify content
        import base64
        decoded = base64.b64decode(serialized["content"])
        assert decoded == binary_content

    @pytest.mark.asyncio
    async def test_run_async_preloads_list_of_artifacts(
        self, tool_context_with_artifact_service
    ):
        """List[Artifact] parameters have all artifacts pre-loaded."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
            include_context=False,
        )

        schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "files": adk_types.Schema(
                    type=adk_types.Type.ARRAY,
                    items=adk_types.Schema(type=adk_types.Type.STRING),
                ),
            },
        )

        tool = ExecutorBasedTool(
            name="merge_files",
            description="Merge multiple files",
            parameters_schema=schema,
            executor=executor,
            artifact_params={
                "files": ArtifactTypeInfo(is_artifact=True, is_list=True),
            },
        )

        tool_context = tool_context_with_artifact_service

        captured_payload = None
        load_call_count = 0

        def capture_invoke(**kwargs):
            nonlocal captured_payload
            captured_payload = json.loads(kwargs["Payload"].decode("utf-8"))
            return make_lambda_response({"success": True})

        async def mock_load(artifact_service, app_name, user_id, session_id, filename, version, return_raw_bytes):
            nonlocal load_call_count
            load_call_count += 1
            return {
                "status": "success",
                "content": f"Content of {filename}",
                "version": 1,
                "mime_type": "text/plain",
                "metadata": {},
            }

        with patch.object(tool._executor, "_client") as mock_client, \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.load_artifact_content_or_metadata",
                 side_effect=mock_load,
             ), \
             patch(
                 "solace_agent_mesh.agent.tools.dynamic_tool.get_original_session_id",
                 return_value="test-session-123",
             ):

            mock_client.invoke.side_effect = capture_invoke

            await tool.run_async(
                args={"files": ["file1.txt", "file2.txt", "file3.txt"]},
                tool_context=tool_context,
            )

        # Verify all 3 artifacts were loaded
        assert load_call_count == 3

        # Verify Lambda received list of serialized Artifacts
        serialized_files = captured_payload["args"]["files"]
        assert len(serialized_files) == 3
        assert serialized_files[0]["filename"] == "file1.txt"
        assert serialized_files[0]["content"] == "Content of file1.txt"
        assert serialized_files[1]["filename"] == "file2.txt"
        assert serialized_files[2]["filename"] == "file3.txt"


class TestLambdaExecutorStreamingMode:
    """Test LambdaExecutor streaming mode via Function URLs."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext for tests."""
        context = MagicMock()
        context._invocation_context = MagicMock()
        context._invocation_context.session_id = "test-session-123"
        context._invocation_context.user_id = "test-user"
        context._invocation_context.app_name = "test-app"
        context.state = {}
        return context

    @pytest.fixture
    def streaming_executor(self):
        """Create a LambdaExecutor in streaming mode."""
        return LambdaExecutor(
            function_url="https://lambda.example.com/default",
            include_context=False,
            timeout_seconds=30,
        )

    def test_streaming_mode_detected_with_function_url(self):
        """Executor with function_url should be in streaming mode."""
        executor = LambdaExecutor(
            function_url="https://lambda.example.com/default",
        )
        assert executor._is_streaming_mode is True
        assert executor._function_url == "https://lambda.example.com/default"

    def test_standard_mode_detected_with_function_arn(self):
        """Executor with function_arn should be in standard mode."""
        executor = LambdaExecutor(
            function_arn="arn:aws:lambda:us-east-1:123456789:function:test",
        )
        assert executor._is_streaming_mode is False
        assert executor._function_arn is not None

    def test_requires_function_arn_or_url(self):
        """Executor requires either function_arn or function_url."""
        with pytest.raises(ValueError, match="Either function_arn or function_url"):
            LambdaExecutor()

    @pytest.mark.asyncio
    async def test_streaming_execute_processes_ndjson_stream(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should process NDJSON stream and return result."""
        # Create NDJSON stream content
        ndjson_lines = [
            '{"type":"status","payload":{"message":"Starting..."},"timestamp":1704067200.0}',
            '{"type":"status","payload":{"message":"Processing..."},"timestamp":1704067201.0}',
            '{"type":"result","payload":{"tool_result":{"_schema":"ToolResult","_schema_version":"1.0","status":"success","message":"Done","data":{"count":42},"data_objects":[],"error_code":null}},"timestamp":1704067202.0}',
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        # Create mock context manager
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        # Create mock http client
        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        streaming_executor._http_client = mock_http_client

        result = await streaming_executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolResult)
        assert result.status == "success"
        assert result.message == "Done"
        assert result.data == {"count": 42}

    @pytest.mark.asyncio
    async def test_streaming_execute_forwards_status_updates(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should forward status updates to ToolContextFacade."""
        ndjson_lines = [
            '{"type":"status","payload":{"message":"Loading..."},"timestamp":1704067200.0}',
            '{"type":"status","payload":{"message":"Processing..."},"timestamp":1704067201.0}',
            '{"type":"result","payload":{"tool_result":{"_schema":"ToolResult","_schema_version":"1.0","status":"success","message":"Done","data":{},"data_objects":[],"error_code":null}},"timestamp":1704067202.0}',
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        streaming_executor._http_client = mock_http_client

        # Track status updates
        status_messages = []
        mock_facade = MagicMock()
        mock_facade.send_status.side_effect = lambda msg: status_messages.append(msg)

        with patch.object(
            streaming_executor,
            "_get_tool_context_facade",
            return_value=mock_facade,
        ):
            await streaming_executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        assert status_messages == ["Loading...", "Processing..."]

    @pytest.mark.asyncio
    async def test_streaming_execute_handles_error_message(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should handle error messages in stream."""
        ndjson_lines = [
            '{"type":"status","payload":{"message":"Starting..."},"timestamp":1704067200.0}',
            '{"type":"error","payload":{"error":"Something went wrong","error_code":"PROCESSING_ERROR"},"timestamp":1704067201.0}',
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        streaming_executor._http_client = mock_http_client

        result = await streaming_executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert "Something went wrong" in result.error
        assert result.error_code == "PROCESSING_ERROR"

    @pytest.mark.asyncio
    async def test_streaming_execute_handles_http_error(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should handle HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        async def mock_aread():
            return b"Internal Server Error"

        mock_response.aread = mock_aread

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        streaming_executor._http_client = mock_http_client

        result = await streaming_executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert "HTTP 500" in result.error
        assert result.error_code == "HTTP_500"

    @pytest.mark.asyncio
    async def test_streaming_execute_handles_no_result(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should handle stream with no result message."""
        ndjson_lines = [
            '{"type":"status","payload":{"message":"Starting..."},"timestamp":1704067200.0}',
            '{"type":"heartbeat","payload":{},"timestamp":1704067201.0}',
            # No result message
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        streaming_executor._http_client = mock_http_client

        result = await streaming_executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "NO_RESULT"

    @pytest.mark.asyncio
    async def test_streaming_execute_fails_when_not_initialized(
        self, mock_tool_context
    ):
        """Streaming mode should fail when HTTP client is not initialized."""
        executor = LambdaExecutor(
            function_url="https://lambda.example.com/default",
        )
        # _http_client is None by default

        result = await executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert result.error_code == "NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_streaming_execute_appends_invoke_path(
        self, streaming_executor, mock_tool_context
    ):
        """Streaming mode should append /invoke to URL if not present."""
        ndjson_lines = [
            '{"type":"result","payload":{"tool_result":{"_schema":"ToolResult","_schema_version":"1.0","status":"success","message":"Done","data":{},"data_objects":[],"error_code":null}},"timestamp":1704067202.0}',
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        captured_url = None

        def capture_stream(method, url, **kwargs):
            nonlocal captured_url
            captured_url = url
            return mock_stream_context

        mock_http_client = MagicMock()
        mock_http_client.stream.side_effect = capture_stream

        streaming_executor._http_client = mock_http_client

        await streaming_executor.execute(
            args={"input": "test"},
            tool_context=mock_tool_context,
            tool_config={},
        )

        assert captured_url == "https://lambda.example.com/default/invoke"

    @pytest.mark.asyncio
    async def test_streaming_execute_skips_status_forwarding_when_disabled(
        self, mock_tool_context
    ):
        """When stream_status=False, status updates should not be forwarded."""
        executor = LambdaExecutor(
            function_url="https://lambda.example.com/default",
            stream_status=False,
        )

        ndjson_lines = [
            '{"type":"status","payload":{"message":"Loading..."},"timestamp":1704067200.0}',
            '{"type":"result","payload":{"tool_result":{"_schema":"ToolResult","_schema_version":"1.0","status":"success","message":"Done","data":{},"data_objects":[],"error_code":null}},"timestamp":1704067202.0}',
        ]

        async def mock_aiter_lines():
            for line in ndjson_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = mock_stream_context

        executor._http_client = mock_http_client

        mock_facade = MagicMock()

        with patch.object(
            executor,
            "_get_tool_context_facade",
            return_value=mock_facade,
        ):
            await executor.execute(
                args={"input": "test"},
                tool_context=mock_tool_context,
                tool_config={},
            )

        # send_status should not have been called
        mock_facade.send_status.assert_not_called()
