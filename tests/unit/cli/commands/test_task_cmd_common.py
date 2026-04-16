"""
Unit tests for cli/commands/task_cmd/common.py

Tests the shared utilities used by the task send and task run commands:
- build_structured_invocation_part: builds a StructuredInvocationRequest data part
- build_data_part: builds a DataPart from inline JSON or a @file path
- execute_task: wiring test verifying si_part and data_part appear in the HTTP payload
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.commands.task_cmd.common import build_structured_invocation_part, build_data_part, execute_task


class TestBuildStructuredInvocationPart:
    """Tests for build_structured_invocation_part"""

    def test_no_schemas(self):
        """Returns a valid data part when both schema paths are None."""
        result = build_structured_invocation_part(None, None)

        assert result["kind"] == "data"
        data = result["data"]
        assert data["type"] == "structured_invocation_request"
        assert data["workflow_name"] == "cli-test"
        assert data["node_id"].startswith("cli-")
        assert "input_schema" not in data
        assert "output_schema" not in data

    def test_node_id_is_unique(self):
        """Each call generates a distinct node_id."""
        r1 = build_structured_invocation_part(None, None)
        r2 = build_structured_invocation_part(None, None)
        assert r1["data"]["node_id"] != r2["data"]["node_id"]

    def test_with_input_schema(self, tmp_path):
        """Reads input schema from file and embeds it in the data part."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "input_schema.json"
        schema_file.write_text(json.dumps(schema))

        result = build_structured_invocation_part(str(schema_file), None)

        assert result["data"]["input_schema"] == schema
        assert "output_schema" not in result["data"]

    def test_with_output_schema(self, tmp_path):
        """Reads output schema from file and embeds it in the data part."""
        schema = {"type": "object", "properties": {"score": {"type": "number"}}}
        schema_file = tmp_path / "output_schema.json"
        schema_file.write_text(json.dumps(schema))

        result = build_structured_invocation_part(None, str(schema_file))

        assert result["data"]["output_schema"] == schema
        assert "input_schema" not in result["data"]

    def test_with_both_schemas(self, tmp_path):
        """Reads both schemas from files and embeds them in the data part."""
        input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
        output_schema = {"type": "object", "properties": {"answer": {"type": "string"}}}

        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        input_file.write_text(json.dumps(input_schema))
        output_file.write_text(json.dumps(output_schema))

        result = build_structured_invocation_part(str(input_file), str(output_file))

        assert result["data"]["input_schema"] == input_schema
        assert result["data"]["output_schema"] == output_schema

    def test_missing_schema_file_raises(self, tmp_path):
        """Raises FileNotFoundError when a schema path does not exist."""
        missing = str(tmp_path / "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            build_structured_invocation_part(missing, None)


class TestBuildDataPart:
    """Tests for build_data_part"""

    def test_inline_json_object(self):
        """Parses an inline JSON object string."""
        result = build_data_part('{"key": "value", "count": 42}')

        assert result["kind"] == "data"
        assert result["data"] == {"key": "value", "count": 42}

    def test_inline_json_array(self):
        """Parses an inline JSON array string."""
        result = build_data_part('[1, 2, 3]')

        assert result["kind"] == "data"
        assert result["data"] == [1, 2, 3]

    def test_inline_json_nested(self):
        """Parses nested inline JSON."""
        payload = {"outer": {"inner": [True, None, 3.14]}}
        result = build_data_part(json.dumps(payload))

        assert result["data"] == payload

    def test_file_path_syntax(self, tmp_path):
        """Reads data from a file when the string starts with @."""
        payload = {"from": "file", "items": [1, 2]}
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps(payload))

        result = build_data_part(f"@{data_file}")

        assert result["kind"] == "data"
        assert result["data"] == payload

    def test_file_path_missing_raises(self, tmp_path):
        """Raises FileNotFoundError when the @file path does not exist."""
        missing = str(tmp_path / "missing.json")
        with pytest.raises(FileNotFoundError):
            build_data_part(f"@{missing}")

    def test_invalid_inline_json_raises(self):
        """Raises json.JSONDecodeError for malformed inline JSON."""
        with pytest.raises(json.JSONDecodeError):
            build_data_part("{not valid json}")

    def test_invalid_json_in_file_raises(self, tmp_path):
        """Raises json.JSONDecodeError when the @file contains malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{broken")

        with pytest.raises(json.JSONDecodeError):
            build_data_part(f"@{bad_file}")


def _make_execute_task_mocks():
    """Create mock objects for execute_task's lazy imports and httpx."""
    # Mock the SSE client to yield no events
    mock_sse_instance = MagicMock()
    mock_sse_instance.subscribe = MagicMock(return_value=_AsyncIteratorMock([]))
    mock_sse_cls = MagicMock(return_value=mock_sse_instance)

    # Mock the message assembler
    mock_msg = MagicMock(is_complete=True, is_error=False)
    mock_assembler_instance = MagicMock()
    mock_assembler_instance.process_event = MagicMock(return_value=(mock_msg, None))
    mock_assembler_instance.get_message = MagicMock(return_value=mock_msg)
    mock_assembler_cls = MagicMock(return_value=mock_assembler_instance)

    # Mock the event recorder
    mock_recorder_instance = MagicMock()
    mock_recorder_instance.get_event_count = MagicMock(return_value=0)
    mock_recorder_cls = MagicMock(return_value=mock_recorder_instance)

    # Mock the artifact handler
    mock_artifact_handler_instance = MagicMock()
    mock_artifact_handler_instance.download_all_artifacts = AsyncMock(return_value=[])
    mock_artifact_handler_cls = MagicMock(return_value=mock_artifact_handler_instance)

    # Mock httpx async client
    mock_http_instance = MagicMock()
    mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
    mock_http_instance.__aexit__ = AsyncMock(return_value=False)
    mock_http_instance.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={"result": {"id": "task-test"}}),
    ))
    mock_http_instance.get = AsyncMock()

    return {
        "sse_cls": mock_sse_cls,
        "assembler_cls": mock_assembler_cls,
        "recorder_cls": mock_recorder_cls,
        "artifact_handler_cls": mock_artifact_handler_cls,
        "http_instance": mock_http_instance,
    }


class TestExecuteTaskPayloadWiring:
    """Tests that execute_task correctly wires si_part and data_part into the HTTP payload."""

    @pytest.mark.asyncio
    async def test_si_part_included_in_payload(self, tmp_path):
        """When si_input_schema is provided, the payload includes a structured_invocation_request part."""
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        schema_file = tmp_path / "input.json"
        schema_file.write_text(json.dumps(schema))

        mocks = _make_execute_task_mocks()

        # Stub the lazy imports inside execute_task by temporarily injecting mock modules
        fake_modules = {
            "cli.commands.task_cmd.sse_client": MagicMock(SSEClient=mocks["sse_cls"]),
            "cli.commands.task_cmd.message_assembler": MagicMock(MessageAssembler=mocks["assembler_cls"]),
            "cli.commands.task_cmd.event_recorder": MagicMock(EventRecorder=mocks["recorder_cls"]),
            "cli.commands.task_cmd.artifact_handler": MagicMock(ArtifactHandler=mocks["artifact_handler_cls"]),
        }

        with (
            patch.dict(sys.modules, fake_modules),
            patch("cli.commands.task_cmd.common.httpx.AsyncClient", return_value=mocks["http_instance"]),
        ):
            await execute_task(
                message="hello",
                url="http://localhost:8080",
                agent="TestAgent",
                session_id="s1",
                token=None,
                files=[],
                timeout=30,
                output_dir=tmp_path / "out",
                quiet=True,
                no_stim=True,
                debug=False,
                si_input_schema=str(schema_file),
            )

            mocks["http_instance"].post.assert_called_once()
            call_kwargs = mocks["http_instance"].post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            parts = payload["params"]["message"]["parts"]

            si_parts = [
                p for p in parts
                if p.get("kind") == "data"
                and p.get("data", {}).get("type") == "structured_invocation_request"
            ]
            assert len(si_parts) == 1
            assert si_parts[0]["data"]["input_schema"] == schema

    @pytest.mark.asyncio
    async def test_data_part_included_in_payload(self, tmp_path):
        """When data param is provided, the payload includes a data part."""
        mocks = _make_execute_task_mocks()

        fake_modules = {
            "cli.commands.task_cmd.sse_client": MagicMock(SSEClient=mocks["sse_cls"]),
            "cli.commands.task_cmd.message_assembler": MagicMock(MessageAssembler=mocks["assembler_cls"]),
            "cli.commands.task_cmd.event_recorder": MagicMock(EventRecorder=mocks["recorder_cls"]),
            "cli.commands.task_cmd.artifact_handler": MagicMock(ArtifactHandler=mocks["artifact_handler_cls"]),
        }

        with (
            patch.dict(sys.modules, fake_modules),
            patch("cli.commands.task_cmd.common.httpx.AsyncClient", return_value=mocks["http_instance"]),
        ):
            await execute_task(
                message="hello",
                url="http://localhost:8080",
                agent="TestAgent",
                session_id="s1",
                token=None,
                files=[],
                timeout=30,
                output_dir=tmp_path / "out",
                quiet=True,
                no_stim=True,
                debug=False,
                data='{"key": "value"}',
            )

            mocks["http_instance"].post.assert_called_once()
            call_kwargs = mocks["http_instance"].post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            parts = payload["params"]["message"]["parts"]

            data_parts = [
                p for p in parts
                if p.get("kind") == "data" and p.get("data", {}).get("key") == "value"
            ]
            assert len(data_parts) == 1


class _AsyncIteratorMock:
    """Helper to make a list behave as an async iterator for SSE subscribe."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
