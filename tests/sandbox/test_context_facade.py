"""Tests for SandboxToolContextFacade."""

import json
from pathlib import Path

import pytest

from solace_agent_mesh.sandbox.context_facade import SandboxToolContextFacade


def _make_facade(
    tmp_path: Path,
    artifacts: dict | None = None,
    tool_config: dict | None = None,
    status_pipe: str | None = None,
) -> SandboxToolContextFacade:
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return SandboxToolContextFacade(
        status_pipe_path=status_pipe or "",
        tool_config=tool_config or {},
        artifacts=artifacts or {},
        output_dir=str(output_dir),
        user_id="test-user",
        session_id="test-session",
        app_name="test-app",
    )


class TestLoadArtifactValid:
    @pytest.mark.asyncio
    async def test_returns_bytes(self, tmp_path: Path):
        artifact_file = tmp_path / "data.bin"
        artifact_file.write_bytes(b"\x00\x01\x02")
        facade = _make_facade(tmp_path, artifacts={
            "data.bin": {"local_path": str(artifact_file), "mime_type": "application/octet-stream", "version": 1},
        })

        content = await facade.load_artifact("data.bin")
        assert content == b"\x00\x01\x02"


class TestLoadArtifactAsText:
    @pytest.mark.asyncio
    async def test_returns_string(self, tmp_path: Path):
        artifact_file = tmp_path / "note.txt"
        artifact_file.write_text("hello world")
        facade = _make_facade(tmp_path, artifacts={
            "note.txt": {"local_path": str(artifact_file), "mime_type": "text/plain", "version": 1},
        })

        content = await facade.load_artifact("note.txt", as_text=True)
        assert content == "hello world"


class TestLoadArtifactMissing:
    @pytest.mark.asyncio
    async def test_raises_file_not_found(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        with pytest.raises(FileNotFoundError):
            await facade.load_artifact("nonexistent.txt")


class TestLoadArtifactMissingFile:
    @pytest.mark.asyncio
    async def test_raises_when_file_deleted(self, tmp_path: Path):
        facade = _make_facade(tmp_path, artifacts={
            "gone.txt": {"local_path": str(tmp_path / "gone.txt"), "mime_type": "text/plain", "version": 1},
        })
        with pytest.raises(FileNotFoundError):
            await facade.load_artifact("gone.txt")


class TestLoadArtifactMetadata:
    @pytest.mark.asyncio
    async def test_returns_metadata(self, tmp_path: Path):
        artifact_file = tmp_path / "data.csv"
        artifact_file.write_text("a,b\n1,2")
        facade = _make_facade(tmp_path, artifacts={
            "data.csv": {"local_path": str(artifact_file), "mime_type": "text/csv", "version": 3},
        })

        meta = await facade.load_artifact_metadata("data.csv")
        assert meta["mime_type"] == "text/csv"
        assert meta["version"] == 3
        assert meta["size_bytes"] > 0


class TestLoadArtifactMetadataMissing:
    @pytest.mark.asyncio
    async def test_raises_file_not_found(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        with pytest.raises(FileNotFoundError):
            await facade.load_artifact_metadata("nope.bin")


class TestListArtifacts:
    @pytest.mark.asyncio
    async def test_returns_filenames(self, tmp_path: Path):
        facade = _make_facade(tmp_path, artifacts={
            "a.txt": {"local_path": "/x/a.txt", "mime_type": "text/plain", "version": 1},
            "b.bin": {"local_path": "/x/b.bin", "mime_type": "application/octet-stream", "version": 1},
        })

        names = await facade.list_artifacts()
        assert sorted(names) == ["a.txt", "b.bin"]


class TestArtifactExists:
    @pytest.mark.asyncio
    async def test_true_for_known(self, tmp_path: Path):
        facade = _make_facade(tmp_path, artifacts={
            "x.txt": {"local_path": "/x/x.txt", "mime_type": "text/plain", "version": 1},
        })
        assert await facade.artifact_exists("x.txt") is True

    @pytest.mark.asyncio
    async def test_false_for_unknown(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert await facade.artifact_exists("nope.txt") is False


class TestSendStatus:
    def test_writes_to_pipe(self, tmp_path: Path):
        pipe_file = tmp_path / "pipe"
        pipe_file.write_text("")
        facade = _make_facade(tmp_path, status_pipe=str(pipe_file))

        result = facade.send_status("processing")
        assert result is True

        content = pipe_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["status"] == "processing"

    def test_no_pipe_returns_false(self, tmp_path: Path):
        facade = _make_facade(tmp_path, status_pipe="")
        assert facade.send_status("test") is False


class TestSendStatusBrokenPipe:
    def test_broken_pipe_returns_false(self, tmp_path: Path):
        facade = _make_facade(tmp_path, status_pipe="/dev/null/nonexistent/pipe")
        assert facade.send_status("test") is False


class TestSendSignal:
    def test_returns_false(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.send_signal({"type": "custom"}) is False


class TestSaveArtifact:
    def test_writes_file(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        path = facade.save_artifact("result.json", b'{"ok": true}')
        assert Path(path).read_bytes() == b'{"ok": true}'


class TestProperties:
    def test_session_id(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.session_id == "test-session"

    def test_user_id(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.user_id == "test-user"

    def test_app_name(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.app_name == "test-app"

    def test_state_is_dict(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.state == {}
        facade.state["key"] = "val"
        assert facade.state["key"] == "val"


class TestGetConfig:
    def test_returns_value(self, tmp_path: Path):
        facade = _make_facade(tmp_path, tool_config={"api_key": "secret"})
        assert facade.get_config("api_key") == "secret"

    def test_returns_default(self, tmp_path: Path):
        facade = _make_facade(tmp_path)
        assert facade.get_config("missing", "fallback") == "fallback"
