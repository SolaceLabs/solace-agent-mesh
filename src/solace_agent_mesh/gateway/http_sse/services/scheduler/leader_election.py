"""
Leader election service for distributed scheduler coordination.
Uses database-based locking mechanism to ensure only one scheduler instance
is active at a time across multiple gateway instances.

SQLite note: SELECT FOR UPDATE is not supported. Single-instance deployments
skip row locking (only one instance = no contention). Multi-instance requires
PostgreSQL.
"""

import asyncio
import logging
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ...repository.models import SchedulerLockModel
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


def _is_sqlite(session: DBSession) -> bool:
    """Check if the session is using SQLite."""
    return session.bind.dialect.name == "sqlite"


class LeaderElection:
    """
    Implements leader election for distributed scheduler instances.
    Uses database-based locking with heartbeat mechanism.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        instance_id: str,
        namespace: str,
        heartbeat_interval_seconds: int = 30,
        lease_duration_seconds: int = 60,
    ):
        self.session_factory = session_factory
        self.instance_id = instance_id
        self.namespace = namespace
        self.heartbeat_interval = heartbeat_interval_seconds
        self.lease_duration = lease_duration_seconds

        self._is_leader = False
        self._election_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        log.info(
            "[LeaderElection:%s] Initialized with heartbeat=%ss, lease=%ss",
            instance_id, heartbeat_interval_seconds, lease_duration_seconds
        )

    async def start(self):
        """Start participating in leader election."""
        if self._election_task is not None:
            return

        log.info("[LeaderElection:%s] Starting leader election", self.instance_id)
        self._stop_event.clear()
        self._election_task = asyncio.create_task(self._election_loop())

    async def stop(self):
        """Stop participating in leader election and release leadership if held."""
        log.info("[LeaderElection:%s] Stopping leader election", self.instance_id)
        self._stop_event.set()

        if self._election_task:
            self._election_task.cancel()
            try:
                await self._election_task
            except asyncio.CancelledError:
                pass
            self._election_task = None

        if self._is_leader:
            await self._release_leadership()

    async def is_leader(self) -> bool:
        """Check if this instance is currently the leader."""
        return self._is_leader

    async def _election_loop(self):
        """Continuously attempt to acquire or maintain leadership."""
        while not self._stop_event.is_set():
            try:
                if await self._try_acquire_leadership():
                    if not self._is_leader:
                        self._is_leader = True
                        log.info("[LeaderElection:%s] Acquired leadership", self.instance_id)

                    await self._maintain_leadership()
                else:
                    if self._is_leader:
                        self._is_leader = False
                        log.warning("[LeaderElection:%s] Lost leadership", self.instance_id)

                    await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    "[LeaderElection:%s] Error in election loop: %s",
                    self.instance_id, e,
                    exc_info=True,
                )
                self._is_leader = False
                await asyncio.sleep(5)

    async def _try_acquire_leadership(self) -> bool:
        """Attempt to acquire leadership."""
        try:
            with self.session_factory() as session:
                # FIX: Use FOR UPDATE to lock the row (skip for SQLite)
                stmt = select(SchedulerLockModel)
                if not _is_sqlite(session):
                    stmt = stmt.with_for_update(skip_locked=True)

                lock = session.execute(stmt).scalar_one_or_none()

                current_time = now_epoch_ms()
                expires_at = current_time + (self.lease_duration * 1000)

                if lock is None:
                    lock = SchedulerLockModel(
                        id=1,
                        leader_id=self.instance_id,
                        leader_namespace=self.namespace,
                        acquired_at=current_time,
                        expires_at=expires_at,
                        heartbeat_at=current_time,
                    )
                    session.add(lock)
                    session.commit()
                    return True

                if lock.expires_at < current_time:
                    lock.leader_id = self.instance_id
                    lock.leader_namespace = self.namespace
                    lock.acquired_at = current_time
                    lock.expires_at = expires_at
                    lock.heartbeat_at = current_time
                    session.commit()
                    return True

                if lock.leader_id == self.instance_id:
                    lock.expires_at = expires_at
                    lock.heartbeat_at = current_time
                    session.commit()
                    return True

                return False

        except Exception as e:
            log.error(
                "[LeaderElection:%s] Failed to acquire leadership: %s",
                self.instance_id, e,
                exc_info=True,
            )
            return False

    async def _maintain_leadership(self):
        """Maintain leadership by sending periodic heartbeats."""
        while not self._stop_event.is_set() and self._is_leader:
            try:
                success = await self._send_heartbeat()
                if not success:
                    break
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    "[LeaderElection:%s] Error maintaining leadership: %s",
                    self.instance_id, e,
                    exc_info=True,
                )
                break

    async def _send_heartbeat(self) -> bool:
        """Send a heartbeat to maintain leadership."""
        try:
            with self.session_factory() as session:
                # FIX: Add FOR UPDATE to heartbeat SELECT (skip for SQLite)
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                if not _is_sqlite(session):
                    stmt = stmt.with_for_update()

                lock = session.execute(stmt).scalar_one_or_none()

                if lock is None or lock.leader_id != self.instance_id:
                    log.warning("[LeaderElection:%s] Lost lock during heartbeat", self.instance_id)
                    return False

                current_time = now_epoch_ms()
                lock.heartbeat_at = current_time
                lock.expires_at = current_time + (self.lease_duration * 1000)
                session.commit()
                return True

        except Exception as e:
            log.error(
                "[LeaderElection:%s] Failed to send heartbeat: %s",
                self.instance_id, e,
                exc_info=True,
            )
            return False

    async def _release_leadership(self):
        """Release leadership gracefully."""
        try:
            with self.session_factory() as session:
                # FIX: Add FOR UPDATE to release SELECT (skip for SQLite)
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                if not _is_sqlite(session):
                    stmt = stmt.with_for_update()

                lock = session.execute(stmt).scalar_one_or_none()

                if lock and lock.leader_id == self.instance_id:
                    lock.expires_at = now_epoch_ms()
                    session.commit()
                    log.info("[LeaderElection:%s] Released leadership", self.instance_id)

        except Exception as e:
            log.error(
                "[LeaderElection:%s] Failed to release leadership: %s",
                self.instance_id, e,
                exc_info=True,
            )

    def get_leader_info(self) -> Optional[dict]:
        """Get information about the current leader."""
        try:
            with self.session_factory() as session:
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                lock = session.execute(stmt).scalar_one_or_none()

                if lock is None:
                    return None

                current_time = now_epoch_ms()
                return {
                    "leader_id": lock.leader_id,
                    "leader_namespace": lock.leader_namespace,
                    "acquired_at": lock.acquired_at,
                    "expires_at": lock.expires_at,
                    "heartbeat_at": lock.heartbeat_at,
                    "is_expired": lock.expires_at < current_time,
                    "is_self": lock.leader_id == self.instance_id,
                }

        except Exception as e:
            log.error(
                "[LeaderElection:%s] Failed to get leader info: %s",
                self.instance_id, e,
                exc_info=True,
            )
            return None
