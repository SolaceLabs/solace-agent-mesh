"""Tests for the local-filesystem object storage backend.

Round-trips bytes through real files in a tmp dir so we exercise the actual
disk path, not a mock. Lives in its own module (rather than alongside the
other backend tests) because the existing `test_object_storage.py` imports
the azure SDK at module top — we want these to run even when azure is not
installed.
"""

import os

import pytest

from solace_agent_mesh.services.platform.storage.exceptions import (
    StorageError,
    StorageNotFoundError,
)
from solace_agent_mesh.services.platform.storage.factory import create_storage_client
from solace_agent_mesh.services.platform.storage.filesystem_client import (
    FileSystemStorageClient,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Keep `create_storage_client` from picking up an outer OBJECT_STORAGE_TYPE."""
    monkeypatch.delenv("OBJECT_STORAGE_TYPE", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_FS_ROOT", raising=False)


@pytest.fixture()
def fs_client(tmp_path):
    return FileSystemStorageClient(bucket_name="bkt", root_path=str(tmp_path))


class TestFactory:
    def test_factory_creates_filesystem_client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OBJECT_STORAGE_FS_ROOT", str(tmp_path))
        client = create_storage_client(bucket_name="b", storage_type="filesystem")
        assert isinstance(client, FileSystemStorageClient)

    @pytest.mark.parametrize("alias", ["fs", "local", "FILESYSTEM"])
    def test_factory_accepts_aliases(self, tmp_path, monkeypatch, alias):
        monkeypatch.setenv("OBJECT_STORAGE_FS_ROOT", str(tmp_path))
        client = create_storage_client(bucket_name="b", storage_type=alias)
        assert isinstance(client, FileSystemStorageClient)


class TestRoundTrip:
    def test_put_then_get_roundtrips_bytes(self, fs_client):
        fs_client.put_object("a/b/c.json", b'{"hello": "world"}', "application/json")
        obj = fs_client.get_object("a/b/c.json")
        assert obj.content == b'{"hello": "world"}'

    def test_get_missing_raises_storage_not_found(self, fs_client):
        with pytest.raises(StorageNotFoundError):
            fs_client.get_object("does/not/exist.json")


class TestDelete:
    def test_delete_object_removes_file(self, fs_client):
        fs_client.put_object("k.txt", b"x", "text/plain")
        fs_client.delete_object("k.txt")
        with pytest.raises(StorageNotFoundError):
            fs_client.get_object("k.txt")

    def test_delete_object_missing_is_noop(self, fs_client):
        fs_client.delete_object("never-existed.txt")  # must not raise

    def test_delete_prefix_removes_subtree(self, fs_client):
        fs_client.put_object("ns/a.txt", b"1", "text/plain")
        fs_client.put_object("ns/sub/b.txt", b"2", "text/plain")
        fs_client.put_object("other/c.txt", b"3", "text/plain")
        count = fs_client.delete_prefix("ns")
        assert count == 2
        # Sibling prefix must not be affected.
        assert fs_client.get_object("other/c.txt").content == b"3"


class TestListAndUrls:
    def test_list_objects_returns_relative_keys(self, fs_client):
        fs_client.put_object("ns/a.txt", b"1", "text/plain")
        fs_client.put_object("ns/sub/b.txt", b"2", "text/plain")
        fs_client.put_object("other/c.txt", b"3", "text/plain")
        keys = sorted(fs_client.list_objects("ns"))
        assert keys == ["ns/a.txt", "ns/sub/b.txt"]

    def test_list_objects_returns_posix_separators(self, fs_client):
        """Keys must use '/' even when nested, so they round-trip with cloud backends."""
        fs_client.put_object("a/b/c/d.txt", b"x", "text/plain")
        keys = fs_client.list_objects("a")
        assert keys == ["a/b/c/d.txt"]
        assert all("\\" not in k for k in keys)

    def test_get_public_url_returns_file_uri(self, fs_client):
        fs_client.put_object("k.txt", b"x", "text/plain")
        url = fs_client.get_public_url("k.txt")
        assert url.startswith("file://")
        assert url.endswith("/bkt/k.txt")


class TestRelativeRootPath:
    """A relative root_path must still produce a usable absolute filesystem path.

    `Path.as_uri()` (used by `get_public_url`/`generate_presigned_url`) raises
    ValueError on relative paths, so the client has to resolve to absolute
    during `__init__`.
    """

    def test_relative_root_path_resolves_to_absolute(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = FileSystemStorageClient(bucket_name="bkt", root_path="./storage")
        client.put_object("k.txt", b"x", "text/plain")
        url = client.get_public_url("k.txt")
        assert url.startswith("file://")
        assert os.path.isabs(url.removeprefix("file://"))


class TestPathTraversalRejected:
    """Defense-in-depth: keys must stay inside the bucket root."""

    @pytest.mark.parametrize(
        "evil_key",
        [
            "../escape.txt",
            "../../etc/passwd",
            "ns/../../escape.txt",
            "/etc/passwd",
        ],
    )
    def test_traversal_keys_are_rejected(self, fs_client, evil_key):
        with pytest.raises(StorageError):
            fs_client.put_object(evil_key, b"x", "text/plain")

    def test_empty_key_is_rejected(self, fs_client):
        with pytest.raises(StorageError):
            fs_client.put_object("", b"x", "text/plain")

    def test_traversal_does_not_leak_through_get(self, fs_client, tmp_path):
        outside = tmp_path / "outside.txt"
        outside.write_bytes(b"secret")
        with pytest.raises(StorageError):
            fs_client.get_object("../outside.txt")
