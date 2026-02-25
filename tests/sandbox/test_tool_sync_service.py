"""Tests for ToolSyncService."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from solace_agent_mesh.sandbox.storage.base import SyncObjectMeta, ToolSyncStorageClient
from solace_agent_mesh.sandbox.tool_sync_service import ToolSyncService


def _make_client(objects: list[SyncObjectMeta] | None = None) -> MagicMock:
    client = MagicMock(spec=ToolSyncStorageClient)
    client.list_objects.return_value = objects or []
    client.download_object.side_effect = lambda key: f"content-of-{key}".encode()
    return client


PREFIX = "ns/str-runtime/"


class TestFirstSyncDownloadsAllFiles:
    def test_all_files_written(self, tmp_path: Path):
        objects = [
            SyncObjectMeta(key=f"{PREFIX}manifest.yaml", etag="aaa", size=100),
            SyncObjectMeta(key=f"{PREFIX}python/tool_a.py", etag="bbb", size=200),
            SyncObjectMeta(key=f"{PREFIX}wheels/pkg-1.0.whl", etag="ccc", size=300),
        ]
        client = _make_client(objects)

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc.start()
        assert svc.wait_for_first_sync(timeout=5)
        svc.stop()

        assert (tmp_path / "manifest.yaml").read_bytes() == f"content-of-{PREFIX}manifest.yaml".encode()
        assert (tmp_path / "python" / "tool_a.py").read_bytes() == f"content-of-{PREFIX}python/tool_a.py".encode()
        assert (tmp_path / "wheels" / "pkg-1.0.whl").read_bytes() == f"content-of-{PREFIX}wheels/pkg-1.0.whl".encode()
        assert client.download_object.call_count == 3


class TestIncrementalSyncSkipsUnchanged:
    def test_no_redownload_on_same_etag(self, tmp_path: Path):
        objects = [
            SyncObjectMeta(key=f"{PREFIX}file.py", etag="aaa", size=100),
        ]
        client = _make_client(objects)

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc._sync_once()
        assert client.download_object.call_count == 1

        svc._sync_once()
        assert client.download_object.call_count == 1


class TestSyncDeletesRemovedFiles:
    def test_stale_file_deleted(self, tmp_path: Path):
        objects = [
            SyncObjectMeta(key=f"{PREFIX}keep.py", etag="aaa", size=100),
            SyncObjectMeta(key=f"{PREFIX}remove.py", etag="bbb", size=100),
        ]
        client = _make_client(objects)

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc._sync_once()
        assert (tmp_path / "remove.py").exists()

        client.list_objects.return_value = [
            SyncObjectMeta(key=f"{PREFIX}keep.py", etag="aaa", size=100),
        ]
        svc._sync_once()

        assert (tmp_path / "keep.py").exists()
        assert not (tmp_path / "remove.py").exists()


class TestSyncUpdatesChangedFiles:
    def test_changed_etag_triggers_redownload(self, tmp_path: Path):
        objects = [
            SyncObjectMeta(key=f"{PREFIX}file.py", etag="v1", size=100),
        ]
        client = _make_client(objects)

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc._sync_once()
        assert client.download_object.call_count == 1

        client.list_objects.return_value = [
            SyncObjectMeta(key=f"{PREFIX}file.py", etag="v2", size=150),
        ]
        client.download_object.side_effect = lambda key: b"updated-content"

        svc._sync_once()
        assert client.download_object.call_count == 2
        assert (tmp_path / "file.py").read_bytes() == b"updated-content"


class TestWaitForFirstSyncTimeout:
    def test_returns_false_on_error(self, tmp_path: Path):
        client = _make_client()
        client.list_objects.side_effect = RuntimeError("connection refused")

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc.start()
        assert not svc.wait_for_first_sync(timeout=5)
        svc.stop()

    def test_returns_false_on_timeout(self, tmp_path: Path):
        client = _make_client()
        client.list_objects.side_effect = lambda _: time.sleep(10)

        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=60)
        svc.start()
        assert not svc.wait_for_first_sync(timeout=0.5)
        svc.stop()


class TestStopTerminatesThread:
    def test_thread_joins(self, tmp_path: Path):
        client = _make_client()
        svc = ToolSyncService(client, PREFIX, str(tmp_path), interval=0.1)
        svc.start()
        svc.wait_for_first_sync(timeout=5)
        svc.stop()
        assert not svc._thread.is_alive()


class TestAtomicWrite:
    def test_creates_parent_directories(self, tmp_path: Path):
        target = tmp_path / "deep" / "nested" / "dir" / "file.txt"
        ToolSyncService._write_atomic(target, b"hello")
        assert target.read_bytes() == b"hello"

    def test_overwrites_existing_file(self, tmp_path: Path):
        target = tmp_path / "file.txt"
        target.write_bytes(b"old")
        ToolSyncService._write_atomic(target, b"new")
        assert target.read_bytes() == b"new"
