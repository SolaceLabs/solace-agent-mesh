"""
Leader election service for distributed scheduler coordination.
Uses database-based locking mechanism to ensure only one scheduler instance
is active at a time across multiple gateway instances.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ...repository.models import SchedulerLockModel
from ...shared import now_epoch_ms

log = logging.getLogger(__name__)


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
        """
        Initialize leader election service.

        Args:
            session_factory: Factory function to create database sessions
            instance_id: Unique identifier for this scheduler instance
            namespace: Namespace this scheduler operates in
            heartbeat_interval_seconds: How often to send heartbeats
            lease_duration_seconds: How long a lease is valid
        """
        self.session_factory = session_factory
        self.instance_id = instance_id
        self.namespace = namespace
        self.heartbeat_interval = heartbeat_interval_seconds
        self.lease_duration = lease_duration_seconds

        self._is_leader = False
        self._election_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        log.info(
            f"[LeaderElection:{instance_id}] Initialized with heartbeat={heartbeat_interval_seconds}s, "
            f"lease={lease_duration_seconds}s"
        )

    async def start(self):
        """Start participating in leader election."""
        if self._election_task is not None:
            log.warning(
                f"[LeaderElection:{self.instance_id}] Already started, ignoring start request"
            )
            return

        log.info(f"[LeaderElection:{self.instance_id}] Starting leader election")
        self._stop_event.clear()
        self._election_task = asyncio.create_task(self._election_loop())

    async def stop(self):
        """Stop participating in leader election and release leadership if held."""
        log.info(f"[LeaderElection:{self.instance_id}] Stopping leader election")
        self._stop_event.set()

        if self._election_task:
            self._election_task.cancel()
            try:
                await self._election_task
            except asyncio.CancelledError:
                pass
            self._election_task = None

        # Release lock if we're the leader
        if self._is_leader:
            await self._release_leadership()

    async def is_leader(self) -> bool:
        """Check if this instance is currently the leader."""
        return self._is_leader

    async def _election_loop(self):
        """Continuously attempt to acquire or maintain leadership."""
        log.info(f"[LeaderElection:{self.instance_id}] Election loop started")

        while not self._stop_event.is_set():
            try:
                if await self._try_acquire_leadership():
                    if not self._is_leader:
                        # We just became the leader
                        self._is_leader = True
                        log.info(
                            f"[LeaderElection:{self.instance_id}] ✓ Acquired leadership"
                        )

                    # Maintain leadership with heartbeats
                    await self._maintain_leadership()
                else:
                    # Not the leader, wait and retry
                    if self._is_leader:
                        # We lost leadership
                        self._is_leader = False
                        log.warning(
                            f"[LeaderElection:{self.instance_id}] ✗ Lost leadership"
                        )

                    await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                log.info(
                    f"[LeaderElection:{self.instance_id}] Election loop cancelled"
                )
                break
            except Exception as e:
                log.error(
                    f"[LeaderElection:{self.instance_id}] Error in election loop: {e}",
                    exc_info=True,
                )
                self._is_leader = False
                await asyncio.sleep(5)  # Back off on error

        log.info(f"[LeaderElection:{self.instance_id}] Election loop stopped")

    async def _try_acquire_leadership(self) -> bool:
        """
        Attempt to acquire leadership.

        Returns:
            True if leadership was acquired or maintained, False otherwise
        """
        try:
            with self.session_factory() as session:
                # Use SELECT FOR UPDATE to lock the row
                stmt = select(SchedulerLockModel).with_for_update(skip_locked=True)
                lock = session.execute(stmt).scalar_one_or_none()

                current_time = now_epoch_ms()
                expires_at = current_time + (self.lease_duration * 1000)

                if lock is None:
                    # No lock exists, create it
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
                    log.info(
                        f"[LeaderElection:{self.instance_id}] Created new lock"
                    )
                    return True

                # Check if current lease has expired
                if lock.expires_at < current_time:
                    # Take over expired lease
                    log.info(
                        f"[LeaderElection:{self.instance_id}] Taking over expired lease from {lock.leader_id}"
                    )
                    lock.leader_id = self.instance_id
                    lock.leader_namespace = self.namespace
                    lock.acquired_at = current_time
                    lock.expires_at = expires_at
                    lock.heartbeat_at = current_time
                    session.commit()
                    return True

                # Check if we already own the lock
                if lock.leader_id == self.instance_id:
                    # Renew our lease
                    lock.expires_at = expires_at
                    lock.heartbeat_at = current_time
                    session.commit()
                    return True

                # Someone else owns the lock
                return False

        except Exception as e:
            log.error(
                f"[LeaderElection:{self.instance_id}] Failed to acquire leadership: {e}",
                exc_info=True,
            )
            return False

    async def _maintain_leadership(self):
        """Maintain leadership by sending periodic heartbeats."""
        while not self._stop_event.is_set() and self._is_leader:
            try:
                # Send heartbeat
                success = await self._send_heartbeat()
                if not success:
                    log.warning(
                        f"[LeaderElection:{self.instance_id}] Heartbeat failed, may lose leadership"
                    )
                    break

                # Wait for next heartbeat
                await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    f"[LeaderElection:{self.instance_id}] Error maintaining leadership: {e}",
                    exc_info=True,
                )
                break

    async def _send_heartbeat(self) -> bool:
        """
        Send a heartbeat to maintain leadership.

        Returns:
            True if heartbeat was successful, False otherwise
        """
        try:
            with self.session_factory() as session:
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                lock = session.execute(stmt).scalar_one_or_none()

                if lock is None or lock.leader_id != self.instance_id:
                    log.warning(
                        f"[LeaderElection:{self.instance_id}] Lost lock during heartbeat"
                    )
                    return False

                current_time = now_epoch_ms()
                lock.heartbeat_at = current_time
                lock.expires_at = current_time + (self.lease_duration * 1000)
                session.commit()

                log.debug(
                    f"[LeaderElection:{self.instance_id}] Heartbeat sent successfully"
                )
                return True

        except Exception as e:
            log.error(
                f"[LeaderElection:{self.instance_id}] Failed to send heartbeat: {e}",
                exc_info=True,
            )
            return False

    async def _release_leadership(self):
        """Release leadership gracefully."""
        try:
            with self.session_factory() as session:
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                lock = session.execute(stmt).scalar_one_or_none()

                if lock and lock.leader_id == self.instance_id:
                    # Set expiration to now to release immediately
                    lock.expires_at = now_epoch_ms()
                    session.commit()
                    log.info(
                        f"[LeaderElection:{self.instance_id}] Released leadership"
                    )

        except Exception as e:
            log.error(
                f"[LeaderElection:{self.instance_id}] Failed to release leadership: {e}",
                exc_info=True,
            )

    def get_leader_info(self) -> Optional[dict]:
        """
        Get information about the current leader.

        Returns:
            Dictionary with leader information or None if no leader
        """
        try:
            with self.session_factory() as session:
                stmt = select(SchedulerLockModel).where(SchedulerLockModel.id == 1)
                lock = session.execute(stmt).scalar_one_or_none()

                if lock is None:
                    return None

                current_time = now_epoch_ms()
                is_expired = lock.expires_at < current_time

                return {
                    "leader_id": lock.leader_id,
                    "leader_namespace": lock.leader_namespace,
                    "acquired_at": lock.acquired_at,
                    "expires_at": lock.expires_at,
                    "heartbeat_at": lock.heartbeat_at,
                    "is_expired": is_expired,
                    "is_self": lock.leader_id == self.instance_id,
                }

        except Exception as e:
            log.error(
                f"[LeaderElection:{self.instance_id}] Failed to get leader info: {e}",
                exc_info=True,
            )
            return None