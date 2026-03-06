"""Tests for sandbox protocol models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from solace_agent_mesh.sandbox.protocol import (
    ArtifactReference,
    CreatedArtifact,
    PreloadedArtifact,
    SandboxErrorCodes,
    SandboxInitParams,
    SandboxInvokeParams,
    SandboxInvokeResult,
    SandboxStatusUpdate,
    SandboxStatusUpdateParams,
    SandboxToolInitRequest,
    SandboxToolInitResponse,
    SandboxToolInitResult,
    SandboxToolInvocationRequest,
    SandboxToolInvocationResponse,
)


class TestPreloadedArtifactRequiredFields:
    def test_missing_filename_raises(self):
        with pytest.raises(ValidationError):
            PreloadedArtifact(content="abc", version=1)

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            PreloadedArtifact(filename="f.txt", version=1)

    def test_valid_creation(self):
        a = PreloadedArtifact(filename="f.txt", content="abc", version=1)
        assert a.filename == "f.txt"
        assert a.mime_type == "application/octet-stream"
        assert a.metadata == {}


class TestArtifactReferenceRequiredFields:
    def test_missing_filename_raises(self):
        with pytest.raises(ValidationError):
            ArtifactReference()

    def test_default_version_is_none(self):
        ref = ArtifactReference(filename="data.csv")
        assert ref.version is None

    def test_explicit_version(self):
        ref = ArtifactReference(filename="data.csv", version=3)
        assert ref.version == 3


class TestSandboxInvokeParamsRequiredFields:
    def test_missing_task_id_raises(self):
        with pytest.raises(ValidationError):
            SandboxInvokeParams(
                tool_name="t", app_name="a", user_id="u", session_id="s"
            )

    def test_defaults(self):
        p = SandboxInvokeParams(
            task_id="tid",
            tool_name="t",
            app_name="a",
            user_id="u",
            session_id="s",
        )
        assert p.timeout_seconds == 300
        assert p.sandbox_profile == "standard"
        assert p.args == {}
        assert p.tool_config == {}
        assert p.preloaded_artifacts == {}
        assert p.artifact_references == {}


class TestSandboxToolInvocationRequestLiterals:
    def test_jsonrpc_and_method(self):
        req = SandboxToolInvocationRequest(
            id="r1",
            params=SandboxInvokeParams(
                task_id="t1",
                tool_name="tool",
                app_name="app",
                user_id="u",
                session_id="s",
            ),
        )
        assert req.jsonrpc == "2.0"
        assert req.method == "sam_remote_tool/invoke"

    def test_wrong_method_raises(self):
        with pytest.raises(ValidationError):
            SandboxToolInvocationRequest(
                id="r1",
                method="wrong/method",
                params=SandboxInvokeParams(
                    task_id="t1",
                    tool_name="tool",
                    app_name="app",
                    user_id="u",
                    session_id="s",
                ),
            )


class TestSandboxInvokeResult:
    def test_defaults(self):
        r = SandboxInvokeResult(tool_result={"ok": True}, execution_time_ms=100)
        assert r.timed_out is False
        assert r.created_artifacts == []


class TestCreatedArtifact:
    def test_required_fields(self):
        a = CreatedArtifact(
            filename="out.png", version=1, mime_type="image/png", size_bytes=1024
        )
        assert a.description is None

    def test_missing_size_raises(self):
        with pytest.raises(ValidationError):
            CreatedArtifact(filename="out.png", version=1, mime_type="image/png")


class TestSandboxToolInvocationResponseSuccess:
    def test_factory(self):
        resp = SandboxToolInvocationResponse.success(
            request_id="req-1",
            tool_result={"data": 42},
            execution_time_ms=150,
        )
        assert resp.id == "req-1"
        assert resp.result is not None
        assert resp.result.tool_result == {"data": 42}
        assert resp.error is None


class TestSandboxToolInvocationResponseFailure:
    def test_factory(self):
        resp = SandboxToolInvocationResponse.failure(
            request_id="req-2",
            code=SandboxErrorCodes.TOOL_NOT_FOUND,
            message="Not found",
        )
        assert resp.id == "req-2"
        assert resp.error is not None
        assert resp.error.code == "TOOL_NOT_FOUND"
        assert resp.result is None


class TestSandboxStatusUpdateTimestamp:
    def test_timestamp_auto_populated(self):
        params = SandboxStatusUpdateParams(task_id="t1", status_text="running")
        assert params.timestamp is not None
        dt = datetime.fromisoformat(params.timestamp)
        assert dt.tzinfo is not None

    def test_notification_literals(self):
        update = SandboxStatusUpdate(
            params=SandboxStatusUpdateParams(task_id="t1", status_text="done"),
        )
        assert update.jsonrpc == "2.0"
        assert update.method == "sam_remote_tool/status"


class TestSandboxToolInitRequestLiterals:
    def test_jsonrpc_and_method(self):
        req = SandboxToolInitRequest(
            id="i1",
            params=SandboxInitParams(tool_name="tool_a"),
        )
        assert req.jsonrpc == "2.0"
        assert req.method == "sam_remote_tool/init"


class TestSandboxToolInitResponseFactories:
    def test_success_factory(self):
        resp = SandboxToolInitResponse.success(
            request_id="i1",
            tool_name="tool_a",
            tool_description="A tool",
            parameters_schema={"type": "object"},
        )
        assert resp.result is not None
        assert resp.result.tool_name == "tool_a"
        assert resp.error is None

    def test_failure_factory(self):
        resp = SandboxToolInitResponse.failure(
            request_id="i2",
            code=SandboxErrorCodes.INIT_ERROR,
            message="boom",
        )
        assert resp.error is not None
        assert resp.result is None


class TestSandboxErrorCodes:
    def test_all_codes_are_strings(self):
        codes = [
            SandboxErrorCodes.TIMEOUT,
            SandboxErrorCodes.SANDBOX_FAILED,
            SandboxErrorCodes.TOOL_NOT_FOUND,
            SandboxErrorCodes.TOOL_NOT_AVAILABLE,
            SandboxErrorCodes.IMPORT_ERROR,
            SandboxErrorCodes.EXECUTION_ERROR,
            SandboxErrorCodes.TOOL_ERROR,
            SandboxErrorCodes.ARTIFACT_ERROR,
            SandboxErrorCodes.INVALID_REQUEST,
            SandboxErrorCodes.INTERNAL_ERROR,
            SandboxErrorCodes.INIT_ERROR,
            SandboxErrorCodes.AUTHENTICATION_FAILED,
            SandboxErrorCodes.RESOURCE_EXHAUSTED,
        ]
        for code in codes:
            assert isinstance(code, str)

    def test_resource_exhausted_value(self):
        assert SandboxErrorCodes.RESOURCE_EXHAUSTED == "RESOURCE_EXHAUSTED"
