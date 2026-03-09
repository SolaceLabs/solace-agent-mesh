import asyncio
import contextlib
import logging
import time

log = logging.getLogger(__name__)


class OutboxEventPoller:

    def __init__(
        self,
        processor,
        db_session_factory,
        outbox_repository,
        heartbeat_tracker,
        batch_size: int = 50,
        interval_seconds: int = 10,
        cleanup_interval_seconds: int = 3600,
        cleanup_retention_ms: int = 86_400_000,
    ):
        self._processor = processor
        self._db_session_factory = db_session_factory
        self._outbox_repository = outbox_repository
        self._heartbeat_tracker = heartbeat_tracker
        self._batch_size = batch_size
        self._interval_seconds = interval_seconds
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._cleanup_retention_ms = cleanup_retention_ms
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_cleanup: float = 0

    async def start(self):
        if self._running:
            log.warning("OutboxEventPoller already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info(f"OutboxEventPoller started with {self._interval_seconds}s interval")

    async def stop(self):
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        log.info("OutboxEventPoller stopped")

    async def _run(self):
        while self._running:
            try:
                await asyncio.sleep(self._interval_seconds)
                self._poll_cycle()
                self._maybe_cleanup()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in outbox poller cycle")

    def _poll_cycle(self):
        cycle_start = time.time()

        if not self._heartbeat_tracker.is_heartbeat_active():
            log.debug("Deployer offline, skipping outbox poll cycle")
            return

        now_ms = int(time.time() * 1000)
        fetch_db = self._db_session_factory()
        try:
            events = self._outbox_repository.get_pending_events(fetch_db, now_ms, limit=self._batch_size)
            if not events:
                return

            event_ids = [e.id for e in events]
            deduplicated_ids = self._outbox_repository.bulk_deduplicate_events(fetch_db, event_ids)
            fetch_db.commit()
        except Exception:
            log.exception("Error fetching outbox events")
            fetch_db.rollback()
            return
        finally:
            fetch_db.close()

        fetched = len(events)
        processed = 0
        failed = 0

        for event in events:
            if event.id in deduplicated_ids:
                continue
            db = self._db_session_factory()
            try:
                self._processor.process_single_event(db, event)
                db.commit()
                processed += 1
            except Exception:
                log.exception("Error processing outbox event %s", event.id)
                db.rollback()
                failed += 1
            finally:
                db.close()

        cycle_ms = int((time.time() - cycle_start) * 1000)
        log.info(
            "Outbox poll cycle: fetched=%d deduplicated=%d processed=%d failed=%d duration_ms=%d",
            fetched, len(deduplicated_ids), processed, failed, cycle_ms,
        )

    def _maybe_cleanup(self):
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval_seconds:
            return

        db = self._db_session_factory()
        try:
            threshold = int(now * 1000) - self._cleanup_retention_ms
            count = self._outbox_repository.cleanup_old_events(db, threshold)
            db.commit()
            self._last_cleanup = now
            if count > 0:
                log.info("Cleaned up %d old outbox events", count)
        except Exception:
            log.exception("Error during outbox event cleanup")
            db.rollback()
        finally:
            db.close()
