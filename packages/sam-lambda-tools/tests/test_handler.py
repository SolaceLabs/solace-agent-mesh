"""
Tests for LambdaToolHandler and related functionality.
"""

import asyncio
import base64
import pytest
from typing import List

from sam_lambda_tools import (
    LambdaToolHandler,
    LambdaToolContext,
    deserialize_artifact,
    deserialize_args,
    ToolResult,
    DataObject,
    Artifact,
    ToolContextBase,
    StreamMessage,
    StreamMessageType,
)


class TestDeserializeArtifact:
    """Tests for artifact deserialization."""

    def test_deserialize_text_artifact(self):
        """Text artifact should be deserialized correctly."""
        data = {
            "filename": "test.txt",
            "content": "Hello World",
            "is_binary": False,
            "mime_type": "text/plain",
            "version": 1,
            "metadata": {"author": "test"},
        }
        artifact = deserialize_artifact(data)

        assert artifact.filename == "test.txt"
        assert artifact.as_text() == "Hello World"
        assert artifact.mime_type == "text/plain"
        assert artifact.version == 1
        assert artifact.metadata == {"author": "test"}

    def test_deserialize_binary_artifact(self):
        """Binary artifact should be base64-decoded."""
        binary_content = b"\x00\x01\x02\x03"
        encoded = base64.b64encode(binary_content).decode("utf-8")

        data = {
            "filename": "data.bin",
            "content": encoded,
            "is_binary": True,
            "mime_type": "application/octet-stream",
            "version": 2,
            "metadata": {},
        }
        artifact = deserialize_artifact(data)

        assert artifact.filename == "data.bin"
        assert artifact.as_bytes() == binary_content
        assert artifact.version == 2


class TestDeserializeArgs:
    """Tests for argument deserialization."""

    def test_deserialize_single_artifact(self):
        """Single artifact in args should be deserialized."""
        args = {
            "input_file": {
                "filename": "input.txt",
                "content": "data",
                "is_binary": False,
                "mime_type": "text/plain",
                "version": 1,
                "metadata": {},
            },
            "output_name": "result.json",
        }
        result = deserialize_args(args)

        assert isinstance(result["input_file"], Artifact)
        assert result["input_file"].filename == "input.txt"
        assert result["output_name"] == "result.json"

    def test_deserialize_list_of_artifacts(self):
        """List of artifacts should all be deserialized."""
        args = {
            "files": [
                {
                    "filename": "file1.txt",
                    "content": "one",
                    "is_binary": False,
                    "mime_type": "text/plain",
                    "version": 1,
                    "metadata": {},
                },
                {
                    "filename": "file2.txt",
                    "content": "two",
                    "is_binary": False,
                    "mime_type": "text/plain",
                    "version": 1,
                    "metadata": {},
                },
            ],
        }
        result = deserialize_args(args)

        assert len(result["files"]) == 2
        assert all(isinstance(f, Artifact) for f in result["files"])
        assert result["files"][0].filename == "file1.txt"
        assert result["files"][1].filename == "file2.txt"

    def test_preserves_non_artifact_args(self):
        """Non-artifact arguments should be preserved."""
        args = {
            "name": "test",
            "count": 42,
            "options": {"verbose": True},
        }
        result = deserialize_args(args)

        assert result == args


class TestLambdaToolContext:
    """Tests for LambdaToolContext."""

    @pytest.fixture
    def stream_queue(self):
        return asyncio.Queue(maxsize=10)

    @pytest.fixture
    def context(self, stream_queue):
        return LambdaToolContext(
            session_id="sess-123",
            user_id="user-456",
            app_name="test-app",
            tool_config={"max_items": 100},
            stream_queue=stream_queue,
        )

    def test_properties(self, context):
        """Context properties should be accessible."""
        assert context.session_id == "sess-123"
        assert context.user_id == "user-456"
        assert context.app_name == "test-app"

    def test_get_config(self, context):
        """get_config should return config values."""
        assert context.get_config("max_items") == 100
        assert context.get_config("missing", default="default") == "default"

    def test_send_status(self, context, stream_queue):
        """send_status should queue a status message."""
        result = context.send_status("Processing...")

        assert result is True
        assert not stream_queue.empty()

        msg = stream_queue.get_nowait()
        assert msg.type == StreamMessageType.STATUS
        assert msg.payload["message"] == "Processing..."

    def test_state_is_local(self, context):
        """State should be local and modifiable."""
        assert context.state == {}
        context.state["key"] = "value"
        assert context.state["key"] == "value"

    def test_a2a_context_is_none(self, context):
        """A2A context should be None in Lambda."""
        assert context.a2a_context is None


class TestLambdaToolHandler:
    """Tests for LambdaToolHandler."""

    def test_detects_ctx_param_by_name(self):
        """Should detect context parameter by name 'ctx'."""
        async def tool_with_ctx(data: str, ctx) -> ToolResult:
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(tool_with_ctx)
        assert handler._ctx_param_name == "ctx"

    def test_detects_ctx_param_by_context_name(self):
        """Should detect context parameter by name 'context'."""
        async def tool_with_context(data: str, context) -> ToolResult:
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(tool_with_context)
        assert handler._ctx_param_name == "context"

    def test_detects_ctx_param_by_type(self):
        """Should detect context parameter by type annotation."""
        async def tool_with_typed_ctx(
            data: str,
            my_ctx: ToolContextBase,
        ) -> ToolResult:
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(tool_with_typed_ctx)
        assert handler._ctx_param_name == "my_ctx"

    def test_detects_async_function(self):
        """Should detect async functions."""
        async def async_tool(data: str) -> ToolResult:
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(async_tool)
        assert handler._is_async is True

    def test_detects_sync_function(self):
        """Should detect sync functions."""
        def sync_tool(data: str) -> ToolResult:
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(sync_tool)
        assert handler._is_async is False

    @pytest.mark.asyncio
    async def test_execute_async_tool(self):
        """Should execute async tool and return ToolResult."""
        async def my_tool(message: str) -> ToolResult:
            return ToolResult.ok(f"Processed: {message}")

        handler = LambdaToolHandler(my_tool)
        queue = asyncio.Queue()

        result = await handler.execute(
            args={"message": "hello"},
            context={"session_id": "s", "user_id": "u"},
            tool_config={},
            stream_queue=queue,
        )

        assert result.status == "success"
        assert result.message == "Processed: hello"

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self):
        """Should execute sync tool in executor."""
        def sync_tool(value: int) -> ToolResult:
            return ToolResult.ok("Done", data={"doubled": value * 2})

        handler = LambdaToolHandler(sync_tool)
        queue = asyncio.Queue()

        result = await handler.execute(
            args={"value": 21},
            context={},
            tool_config={},
            stream_queue=queue,
        )

        assert result.status == "success"
        assert result.data["doubled"] == 42

    @pytest.mark.asyncio
    async def test_execute_with_context_injection(self):
        """Should inject context into tool function."""
        received_ctx = None

        async def tool_with_ctx(data: str, ctx: ToolContextBase) -> ToolResult:
            nonlocal received_ctx
            received_ctx = ctx
            ctx.send_status("Working...")
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(tool_with_ctx)
        queue = asyncio.Queue()

        await handler.execute(
            args={"data": "test"},
            context={"session_id": "sess-1", "user_id": "user-1"},
            tool_config={"key": "value"},
            stream_queue=queue,
        )

        assert received_ctx is not None
        assert received_ctx.session_id == "sess-1"
        assert received_ctx.user_id == "user-1"
        assert received_ctx.get_config("key") == "value"

        # Check status was queued
        assert not queue.empty()

    @pytest.mark.asyncio
    async def test_execute_deserializes_artifacts(self):
        """Should deserialize artifact arguments."""
        received_artifact = None

        async def tool_with_artifact(doc: Artifact) -> ToolResult:
            nonlocal received_artifact
            received_artifact = doc
            return ToolResult.ok("Done")

        handler = LambdaToolHandler(tool_with_artifact)
        queue = asyncio.Queue()

        await handler.execute(
            args={
                "doc": {
                    "filename": "doc.txt",
                    "content": "Hello",
                    "is_binary": False,
                    "mime_type": "text/plain",
                    "version": 1,
                    "metadata": {},
                }
            },
            context={},
            tool_config={},
            stream_queue=queue,
        )

        assert received_artifact is not None
        assert isinstance(received_artifact, Artifact)
        assert received_artifact.filename == "doc.txt"
        assert received_artifact.as_text() == "Hello"

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self):
        """Should return error ToolResult on exception."""
        async def failing_tool() -> ToolResult:
            raise ValueError("Something went wrong")

        handler = LambdaToolHandler(failing_tool)
        queue = asyncio.Queue()

        result = await handler.execute(
            args={},
            context={},
            tool_config={},
            stream_queue=queue,
        )

        assert result.status == "error"
        assert "Something went wrong" in result.message
        assert result.error_code == "EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_execute_wraps_dict_result(self):
        """Should wrap dict return value in ToolResult."""
        async def dict_tool() -> dict:
            return {"key": "value"}

        handler = LambdaToolHandler(dict_tool)
        queue = asyncio.Queue()

        result = await handler.execute(
            args={},
            context={},
            tool_config={},
            stream_queue=queue,
        )

        assert result.status == "success"
        assert result.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_wraps_raw_result(self):
        """Should wrap raw return value in ToolResult."""
        async def raw_tool() -> str:
            return "raw value"

        handler = LambdaToolHandler(raw_tool)
        queue = asyncio.Queue()

        result = await handler.execute(
            args={},
            context={},
            tool_config={},
            stream_queue=queue,
        )

        assert result.status == "success"
        assert result.data == {"result": "raw value"}


class TestStreamMessage:
    """Tests for StreamMessage helpers."""

    def test_status_message(self):
        """status() should create STATUS message."""
        msg = StreamMessage.status("Processing...")

        assert msg.type == StreamMessageType.STATUS
        assert msg.payload["message"] == "Processing..."
        assert msg.timestamp > 0

    def test_result_message(self):
        """result() should create RESULT message."""
        tool_result = {"_schema": "ToolResult", "status": "success"}
        msg = StreamMessage.result(tool_result)

        assert msg.type == StreamMessageType.RESULT
        assert msg.payload["tool_result"] == tool_result

    def test_error_message(self):
        """error() should create ERROR message."""
        msg = StreamMessage.error("Failed", error_code="ERR_001")

        assert msg.type == StreamMessageType.ERROR
        assert msg.payload["error"] == "Failed"
        assert msg.payload["error_code"] == "ERR_001"

    def test_heartbeat_message(self):
        """heartbeat() should create HEARTBEAT message."""
        msg = StreamMessage.heartbeat()

        assert msg.type == StreamMessageType.HEARTBEAT
        assert msg.payload == {}

    def test_to_ndjson_line(self):
        """to_ndjson_line() should produce valid JSON with newline."""
        msg = StreamMessage.status("Test")
        line = msg.to_ndjson_line()

        assert line.endswith("\n")
        import json
        parsed = json.loads(line)
        assert parsed["type"] == "status"
        assert parsed["payload"]["message"] == "Test"
