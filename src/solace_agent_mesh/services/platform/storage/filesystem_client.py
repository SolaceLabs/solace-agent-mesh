"""Local filesystem storage client.

Intended for local development and tests where running real S3 / GCS / Azure
is overkill. The on-disk layout mirrors the bucket+key shape one-to-one:
``{root}/{bucket_name}/{key}``. Keys may contain ``/`` separators — they map
directly to nested directories.

`generate_presigned_url` and `get_public_url` return ``file://`` URLs; they
are not browser-loadable but they are stable and unique, which is enough for
the diagnostic and dev paths that consume them.
"""

import logging
import shutil
from pathlib import Path

from .base import ObjectStorageClient, StorageObject
from .exceptions import StorageError, StorageNotFoundError

log = logging.getLogger(__name__)


class FileSystemStorageClient(ObjectStorageClient):
    """Object-storage implementation backed by the local filesystem."""

    def __init__(self, bucket_name: str, root_path: str):
        self._bucket = bucket_name
        # `.resolve()` is required so `as_uri()` works (it rejects relative
        # paths) and so the path-traversal guard in `_path_for` has a stable
        # absolute anchor to compare against.
        self._root = (Path(root_path).expanduser() / bucket_name).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        log.info(
            "FileSystemStorageClient ready: bucket=%s, root=%s",
            self._bucket,
            self._root,
        )

    def _path_for(self, key: str) -> Path:
        """Resolve a key to an absolute path inside the bucket root.

        Rejects absolute keys and any key that resolves outside the root
        (e.g. ``..`` traversal). This is defense-in-depth: callers in this
        codebase only pass server-constructed keys, but the class is part
        of the public storage interface.
        """
        if not key:
            raise StorageError("Storage key must be non-empty", key=key)
        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise StorageError(
                f"Storage key resolves outside bucket root: {key!r}",
                key=key,
            )
        return candidate

    def put_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def get_object(self, key: str) -> StorageObject:
        path = self._path_for(key)
        if not path.is_file():
            raise StorageNotFoundError(f"No object at key {key!r}", key=key)
        return StorageObject(content=path.read_bytes())

    def delete_object(self, key: str) -> None:
        path = self._path_for(key)
        if path.is_file():
            path.unlink()

    def delete_prefix(self, prefix: str) -> int:
        target = self._path_for(prefix)
        if target.is_dir():
            count = sum(1 for p in target.rglob("*") if p.is_file())
            shutil.rmtree(target)
            return count
        if target.is_file():
            target.unlink()
            return 1
        # Treat the prefix as a key-prefix string match against existing files.
        count = 0
        for p in self._root.rglob("*"):
            if not p.is_file():
                continue
            if p.relative_to(self._root).as_posix().startswith(prefix):
                p.unlink()
                count += 1
        return count

    def list_objects(self, prefix: str) -> list[str]:
        out: list[str] = []
        for p in self._root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(self._root).as_posix()
            if rel.startswith(prefix):
                out.append(rel)
        return out

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self._path_for(key).as_uri()

    def get_public_url(self, key: str) -> str:
        return self._path_for(key).as_uri()
