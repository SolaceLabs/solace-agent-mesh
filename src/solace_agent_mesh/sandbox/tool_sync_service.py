"""Background service that syncs tool files from object storage to the local filesystem."""

import logging
import os
import tempfile
import threading
from pathlib import Path

from .storage.base import ToolSyncStorageClient

log = logging.getLogger(__name__)


class ToolSyncService:
    """Periodically syncs tool files from remote storage to a local directory.

    Replaces the aws-cli sidecar container with in-process sync that supports
    S3, GCS, and Azure via the ToolSyncStorageClient abstraction.

    The sync loop:
    1. Lists objects under ``remote_prefix``
    2. Compares ETags to an in-memory tracking dict
    3. Downloads new/changed files atomically (write-to-temp, rename)
    4. Deletes local files that no longer exist remotely
    5. The existing manifest mtime-based watcher detects changes
    """

    def __init__(
        self,
        client: ToolSyncStorageClient,
        remote_prefix: str,
        local_dir: str,
        interval: float = 10.0,
    ):
        self._client = client
        self._remote_prefix = remote_prefix.rstrip("/") + "/"
        self._local_dir = Path(local_dir)
        self._interval = interval

        self._etag_cache: dict[str, str] = {}
        self._stop = threading.Event()
        self._first_sync_done = threading.Event()
        self._first_sync_error: Exception | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background sync thread."""
        self._thread = threading.Thread(
            target=self._sync_loop,
            name="tool-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background sync thread and wait for it to finish."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._interval + 5)

    def wait_for_first_sync(self, timeout: float = 120.0) -> bool:
        """Block until the first sync cycle completes.

        Returns True if the first sync succeeded, False on timeout or error.
        """
        if not self._first_sync_done.wait(timeout=timeout):
            log.error("Tool sync timed out waiting for first sync (%.0fs)", timeout)
            return False
        if self._first_sync_error is not None:
            log.error("First tool sync failed: %s", self._first_sync_error)
            return False
        return True

    def _sync_loop(self) -> None:
        """Background loop: sync immediately, then sleep(interval) between cycles."""
        log.info(
            "Tool sync started: remote=%s local=%s interval=%.0fs",
            self._remote_prefix,
            self._local_dir,
            self._interval,
        )

        first = True
        while not self._stop.is_set():
            try:
                self._sync_once()
                if first:
                    self._first_sync_done.set()
                    first = False
                    log.info("First tool sync completed successfully")
            except Exception as e:
                if first:
                    self._first_sync_error = e
                    self._first_sync_done.set()
                    first = False
                log.error("Tool sync cycle failed: %s", e, exc_info=True)

            self._stop.wait(self._interval)

    def _sync_once(self) -> None:
        """Execute one sync cycle."""
        remote_objects = self._client.list_objects(self._remote_prefix)

        remote_keys: set[str] = set()
        for obj in remote_objects:
            rel_path = obj.key[len(self._remote_prefix) :]
            if not rel_path:
                continue
            remote_keys.add(rel_path)

            cached_etag = self._etag_cache.get(rel_path)
            if cached_etag == obj.etag:
                continue

            data = self._client.download_object(obj.key)
            local_path = self._local_dir / rel_path
            self._write_atomic(local_path, data)
            self._etag_cache[rel_path] = obj.etag

            log.debug("Synced: %s (etag=%s)", rel_path, obj.etag)

        stale_keys = set(self._etag_cache.keys()) - remote_keys
        for rel_path in stale_keys:
            local_path = self._local_dir / rel_path
            if local_path.exists():
                local_path.unlink()
                log.debug("Deleted stale file: %s", rel_path)
            self._etag_cache.pop(rel_path, None)

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        """Write data to *path* atomically via temp-file + rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        closed = False
        try:
            os.write(fd, data)
            os.close(fd)
            closed = True
            os.replace(tmp_path, path)
        except BaseException:
            if not closed:
                os.close(fd)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
