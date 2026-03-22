"""
Core scheduler service for managing and executing scheduled tasks.
Integrates with APScheduler for cron/interval scheduling and coordinates
with leader election for distributed operation.

Supports two modes:
1. Default mode: Uses APScheduler with in-memory result tracking (ResultHandler)
2. K8s mode: Uses StatelessResultCollector for horizontal scaling and optionally
   K8SCronJobManager for native Kubernetes CronJob scheduling
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.common import a2a
from solace_agent_mesh.core_a2a.service import CoreA2AService
from ...repository.models import (
    ExecutionStatus,
    ScheduledTaskExecutionModel,
    ScheduledTaskModel,
    ScheduleType,
)
from ...shared import now_epoch_ms
from .leader_election import LeaderElection
from .result_handler import ResultHandler
from .stateless_result_collector import StatelessResultCollector
from .notification_service import NotificationService

log = logging.getLogger(__name__)

# Safe metadata keys that task_metadata may contain.
# Prevents callers from overriding protocol-level keys.
_SAFE_METADATA_KEYS = frozenset({
    "priority",
    "tags",
    "category",
    "source",
})


class SchedulerService:
    """
    Core scheduling service with distributed support.
    Manages scheduled task definitions and executes them via the agent mesh.
    """

    def __init__(
        self,
        session_factory: Callable[[], DBSession],
        namespace: str,
        instance_id: str,
        publish_func: Callable,
        core_a2a_service: CoreA2AService,
        config: Optional[Dict[str, Any]] = None,
        sse_manager: Optional[Any] = None,
    ):
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.publish_func = publish_func
        self.core_a2a_service = core_a2a_service

        config = config or {}
        self.default_timeout_seconds = config.get("default_timeout_seconds", 3600)
        self.max_concurrent_executions = config.get("max_concurrent_executions", 10)
        self.stale_execution_timeout_seconds = config.get("stale_execution_timeout_seconds", 7200)
        # FIX: Reduced stale cleanup interval from 3600s to 600s
        self.stale_cleanup_interval_seconds = config.get("stale_cleanup_interval_seconds", 600)

        # K8s mode configuration
        self.use_stateless_collector = config.get("use_stateless_collector", False)
        self.k8s_enabled = config.get("k8s_enabled", False)
        self.k8s_config = config.get("k8s", {})

        # Leader election configuration
        leader_config = config.get("leader_election", {})
        heartbeat_interval = leader_config.get("heartbeat_interval_seconds", 30)
        lease_duration = leader_config.get("lease_duration_seconds", 60)

        self.leader_election = LeaderElection(
            session_factory=session_factory,
            instance_id=instance_id,
            namespace=namespace,
            heartbeat_interval_seconds=heartbeat_interval,
            lease_duration_seconds=lease_duration,
        )

        # FIX: Set misfire_grace_time and coalesce on AsyncIOScheduler
        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "misfire_grace_time": 60,
                "coalesce": True,
            },
        )

        self.active_tasks: Dict[str, Any] = {}
        self.running_executions: Dict[str, asyncio.Task] = {}
        self._execution_lock = asyncio.Lock()

        # Initialize result handler
        self.result_handler: Union[ResultHandler, StatelessResultCollector]
        if self.use_stateless_collector:
            log.info(
                "[SchedulerService:%s] Using StatelessResultCollector for K8s horizontal scaling",
                instance_id,
            )
            self.result_handler = StatelessResultCollector(
                session_factory=session_factory,
                namespace=namespace,
                instance_id=instance_id,
            )
        else:
            self.result_handler = ResultHandler(
                session_factory=session_factory,
                namespace=namespace,
                instance_id=instance_id,
            )

        # Initialize K8s CronJob manager if enabled
        self.k8s_manager = None
        if self.k8s_enabled:
            try:
                from .k8s_manager import K8SCronJobManager

                k8s_namespace = self.k8s_config.get("namespace", "default")
                executor_image = self.k8s_config.get("executor_image")
                database_url_secret = self.k8s_config.get("database_url_secret", "sam-scheduler-db")
                broker_config_secret = self.k8s_config.get("broker_config_secret", "sam-scheduler-broker")

                if not executor_image:
                    log.warning(
                        "[SchedulerService:%s] K8s enabled but no executor_image configured. "
                        "K8s CronJob management will be disabled.",
                        instance_id,
                    )
                else:
                    self.k8s_manager = K8SCronJobManager(
                        namespace=k8s_namespace,
                        executor_image=executor_image,
                        database_url_secret=database_url_secret,
                        broker_config_secret=broker_config_secret,
                        a2a_namespace=namespace,
                    )
                    log.info(
                        "[SchedulerService:%s] K8s CronJob manager initialized "
                        "(namespace: %s, image: %s)",
                        instance_id, k8s_namespace, executor_image,
                    )
            except ImportError as e:
                log.warning(
                    "[SchedulerService:%s] K8s enabled but kubernetes package not installed: %s",
                    instance_id, e,
                )
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Failed to initialize K8s manager: %s",
                    instance_id, e,
                    exc_info=True,
                )

        # Initialize notification service
        self.notification_service = NotificationService(
            session_factory=session_factory,
            sse_manager=sse_manager,
            publish_func=publish_func,
            namespace=namespace,
            instance_id=instance_id,
        )

        self._stale_cleanup_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

        log.info(
            "[SchedulerService:%s] Initialized for namespace '%s' "
            "(stateless_collector=%s, k8s_enabled=%s)",
            instance_id, namespace, self.use_stateless_collector, self.k8s_enabled,
        )

    async def start(self):
        """Start the scheduler service."""
        log.info("[SchedulerService:%s] Starting scheduler service", self.instance_id)

        await self.leader_election.start()
        self.scheduler.start()
        log.info("[SchedulerService:%s] APScheduler started", self.instance_id)

        self._monitor_task = asyncio.create_task(self._monitor_leadership())

        self._stale_cleanup_task = asyncio.create_task(self._stale_cleanup_loop())
        log.info("[SchedulerService:%s] Stale cleanup task started", self.instance_id)

    async def stop(self):
        """Stop the scheduler service."""
        log.info("[SchedulerService:%s] Stopping scheduler service", self.instance_id)

        await self.leader_election.stop()
        self.scheduler.shutdown(wait=False)

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._stale_cleanup_task and not self._stale_cleanup_task.done():
            self._stale_cleanup_task.cancel()
            try:
                await self._stale_cleanup_task
            except asyncio.CancelledError:
                pass

        for execution_id, task in list(self.running_executions.items()):
            log.info("[SchedulerService:%s] Cancelling execution %s", self.instance_id, execution_id)
            task.cancel()

        await self.notification_service.cleanup()
        log.info("[SchedulerService:%s] Stopped", self.instance_id)

    async def _stale_cleanup_loop(self):
        """Periodically clean up stale executions."""
        while True:
            try:
                await asyncio.sleep(self.stale_cleanup_interval_seconds)
                if await self.leader_election.is_leader():
                    log.info("[SchedulerService:%s] Running stale execution cleanup", self.instance_id)
                    await self._cleanup_stale_executions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Error in stale cleanup loop: %s",
                    self.instance_id, e,
                    exc_info=True,
                )
                await asyncio.sleep(60)

    async def _cleanup_stale_executions(self):
        """Clean up executions that have been running too long."""
        try:
            if self.use_stateless_collector and hasattr(self.result_handler, 'cleanup_stale_executions'):
                await self.result_handler.cleanup_stale_executions(self.stale_execution_timeout_seconds)
                return

            cutoff_time = now_epoch_ms() - (self.stale_execution_timeout_seconds * 1000)

            with self.session_factory() as session:
                stmt = select(ScheduledTaskExecutionModel).where(
                    ScheduledTaskExecutionModel.status == ExecutionStatus.RUNNING,
                    ScheduledTaskExecutionModel.started_at < cutoff_time,
                )
                stale_executions = session.execute(stmt).scalars().all()

                for execution in stale_executions:
                    log.warning(
                        "[SchedulerService:%s] Found stale execution %s, marking as timeout",
                        self.instance_id, execution.id,
                    )
                    execution.status = ExecutionStatus.TIMEOUT
                    execution.completed_at = now_epoch_ms()
                    execution.error_message = f"Execution exceeded stale timeout of {self.stale_execution_timeout_seconds} seconds"

                    if not self.use_stateless_collector and execution.a2a_task_id:
                        if hasattr(self.result_handler, 'pending_executions_lock'):
                            async with self.result_handler.pending_executions_lock:
                                self.result_handler.pending_executions.pop(execution.a2a_task_id, None)
                                self.result_handler.execution_sessions.pop(execution.id, None)
                                event = self.result_handler.completion_events.pop(execution.id, None)
                            if event:
                                event.set()

                session.commit()

                if stale_executions:
                    log.info(
                        "[SchedulerService:%s] Cleaned up %s stale executions",
                        self.instance_id, len(stale_executions),
                    )

        except Exception as e:
            log.error(
                "[SchedulerService:%s] Error cleaning up stale executions: %s",
                self.instance_id, e,
                exc_info=True,
            )

    async def _monitor_leadership(self):
        """Monitor leadership status and react to changes."""
        was_leader = False

        while True:
            try:
                is_leader = await self.leader_election.is_leader()

                if is_leader and not was_leader:
                    log.info("[SchedulerService:%s] Became leader, loading tasks", self.instance_id)
                    await self._on_become_leader()
                    was_leader = True
                elif not is_leader and was_leader:
                    log.warning("[SchedulerService:%s] Lost leadership, unloading tasks", self.instance_id)
                    await self._on_lose_leadership()
                    was_leader = False

                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Error monitoring leadership: %s",
                    self.instance_id, e,
                    exc_info=True,
                )
                await asyncio.sleep(5)

    async def _on_become_leader(self):
        try:
            await self._load_scheduled_tasks()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to load tasks on becoming leader: %s",
                self.instance_id, e,
                exc_info=True,
            )

    async def _on_lose_leadership(self):
        try:
            # Cancel in-flight executions to prevent duplicate execution when a new
            # leader picks up the same tasks.
            async with self._execution_lock:
                for exec_id in list(self.running_executions.keys()):
                    log.warning(
                        "[SchedulerService:%s] Cancelling orphaned execution "
                        "%s due to leadership loss",
                        self.instance_id, exec_id,
                    )
                self.running_executions.clear()
            await self._unload_all_tasks()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to unload tasks on losing leadership: %s",
                self.instance_id, e,
                exc_info=True,
            )

    async def _load_scheduled_tasks(self):
        """Load all enabled scheduled tasks from database and schedule them."""
        log.info("[SchedulerService:%s] Loading scheduled tasks from database", self.instance_id)

        try:
            with self.session_factory() as session:
                stmt = (
                    select(ScheduledTaskModel)
                    .where(
                        ScheduledTaskModel.enabled == True,
                        ScheduledTaskModel.namespace == self.namespace,
                        ScheduledTaskModel.deleted_at == None,
                        # Only load active tasks (skip paused and error)
                        ScheduledTaskModel.status == "active",
                    )
                )
                tasks = session.execute(stmt).scalars().all()

                log.info("[SchedulerService:%s] Found %s enabled tasks", self.instance_id, len(tasks))

                for task in tasks:
                    try:
                        await self._schedule_task(task)
                    except Exception as e:
                        log.error(
                            "[SchedulerService:%s] Failed to schedule task %s: %s",
                            self.instance_id, task.id, e,
                            exc_info=True,
                        )

        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to load scheduled tasks: %s",
                self.instance_id, e,
                exc_info=True,
            )

    async def _unload_all_tasks(self):
        """Unload all scheduled tasks from APScheduler."""
        for task_id in list(self.active_tasks.keys()):
            try:
                await self._unschedule_task(task_id)
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Failed to unschedule task %s: %s",
                    self.instance_id, task_id, e,
                    exc_info=True,
                )

    async def _schedule_task(self, task: ScheduledTaskModel):
        """Schedule a single task in APScheduler or K8s CronJob."""
        job_id = f"scheduled_task_{task.id}"

        log.info(
            "[SchedulerService:%s] Scheduling task '%s' "
            "(ID: %s, Type: %s)",
            self.instance_id, task.name, task.id, task.schedule_type,
        )

        try:
            if self.k8s_manager:
                success = await self.k8s_manager.sync_task(task)
                if success:
                    self.active_tasks[task.id] = {
                        "job": None,
                        "task_name": task.name,
                        "schedule_type": task.schedule_type,
                        "k8s_managed": True,
                    }
                    return
                log.warning(
                    "[SchedulerService:%s] Failed to sync task to K8s, falling back to APScheduler",
                    self.instance_id,
                )

            trigger = self._create_trigger(task)

            job = self.scheduler.add_job(
                self._execute_scheduled_task,
                trigger=trigger,
                args=[task.id],
                id=job_id,
                replace_existing=True,
                max_instances=1,
            )

            self.active_tasks[task.id] = {
                "job": job,
                "task_name": task.name,
                "schedule_type": task.schedule_type,
                "k8s_managed": False,
            }

            if job.next_run_time:
                next_run_ms = int(job.next_run_time.timestamp() * 1000)
                with self.session_factory() as session:
                    db_task = session.get(ScheduledTaskModel, task.id)
                    if db_task:
                        db_task.next_run_at = next_run_ms
                        session.commit()

            log.info(
                "[SchedulerService:%s] Scheduled task '%s', next run: %s",
                self.instance_id, task.name, job.next_run_time,
            )

        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to schedule task %s: %s",
                self.instance_id, task.id, e,
                exc_info=True,
            )
            raise

    async def _unschedule_task(self, task_id: str):
        """Remove a task from APScheduler or K8s CronJob."""
        job_id = f"scheduled_task_{task_id}"

        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]

            if task_info.get("k8s_managed") and self.k8s_manager:
                try:
                    schedule_type = task_info.get("schedule_type")
                    await self.k8s_manager.delete_cronjob(task_id, schedule_type)
                    del self.active_tasks[task_id]
                    return
                except Exception as e:
                    log.error(
                        "[SchedulerService:%s] Failed to delete K8s CronJob for task %s: %s",
                        self.instance_id, task_id, e,
                        exc_info=True,
                    )

            try:
                self.scheduler.remove_job(job_id)
                del self.active_tasks[task_id]
            except Exception:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]

    def _create_trigger(self, task: ScheduledTaskModel):
        """Create an APScheduler trigger based on task configuration."""
        if task.schedule_type == ScheduleType.CRON:
            if not croniter.is_valid(task.schedule_expression):
                raise ValueError(f"Invalid cron expression: {task.schedule_expression}")
            return CronTrigger.from_crontab(task.schedule_expression, timezone=task.timezone)

        elif task.schedule_type == ScheduleType.INTERVAL:
            interval_seconds = self._parse_interval(task.schedule_expression)
            return IntervalTrigger(seconds=interval_seconds, timezone=task.timezone)

        elif task.schedule_type == ScheduleType.ONE_TIME:
            run_date = datetime.fromisoformat(task.schedule_expression)
            return DateTrigger(run_date=run_date, timezone=task.timezone)

        else:
            raise ValueError(f"Unsupported schedule type: {task.schedule_type}")

    def _parse_interval(self, interval_str: str) -> int:
        """Parse interval string to seconds."""
        interval_str = interval_str.strip().lower()

        if interval_str.endswith("s"):
            return int(interval_str[:-1])
        elif interval_str.endswith("m"):
            return int(interval_str[:-1]) * 60
        elif interval_str.endswith("h"):
            return int(interval_str[:-1]) * 3600
        elif interval_str.endswith("d"):
            return int(interval_str[:-1]) * 86400
        else:
            return int(interval_str)

    async def _execute_scheduled_task(self, task_id: str):
        """Execute a scheduled task by submitting it to the agent mesh.

        Retries are handled iteratively (not recursively) to avoid deep call
        stacks and unnecessary resource retention between attempts.
        """
        log.info(
            "[SchedulerService:%s] Executing scheduled task: %s",
            self.instance_id, task_id,
        )

        # Read task config once before the retry loop
        timeout_seconds = self.default_timeout_seconds
        max_retries = 0
        retry_delay_seconds = 60

        with self.session_factory() as session:
            task = session.get(ScheduledTaskModel, task_id)
            if not task:
                log.warning("[SchedulerService:%s] Task %s not found", self.instance_id, task_id)
                return
            timeout_seconds = task.timeout_seconds or self.default_timeout_seconds
            max_retries = task.max_retries or 0
            retry_delay_seconds = task.retry_delay_seconds or 60

        for attempt in range(max_retries + 1):
            execution_id = None
            try:
                # Check max concurrent executions
                async with self._execution_lock:
                    current_running = len(self.running_executions)
                    if current_running >= self.max_concurrent_executions:
                        log.warning(
                            "[SchedulerService:%s] Max concurrent executions reached, skipping task %s",
                            self.instance_id, task_id,
                        )
                        with self.session_factory() as session:
                            task = session.get(ScheduledTaskModel, task_id)
                            if task:
                                execution = ScheduledTaskExecutionModel(
                                    id=str(uuid.uuid4()),
                                    scheduled_task_id=task.id,
                                    status=ExecutionStatus.SKIPPED,
                                    scheduled_for=now_epoch_ms(),
                                    completed_at=now_epoch_ms(),
                                    error_message=f"Skipped: max concurrent executions ({self.max_concurrent_executions}) reached",
                                )
                                session.add(execution)
                                session.commit()
                        return

                with self.session_factory() as session:
                    task = session.get(ScheduledTaskModel, task_id)
                    if not task or not task.enabled or task.deleted_at:
                        log.warning("[SchedulerService:%s] Task %s not found, disabled, or deleted", self.instance_id, task_id)
                        return

                    # Skip tasks in error state
                    if task.status == "error":
                        log.warning("[SchedulerService:%s] Task %s is in error state, skipping", self.instance_id, task_id)
                        return

                    execution_id = str(uuid.uuid4())
                    current_time = now_epoch_ms()

                    execution = ScheduledTaskExecutionModel(
                        id=execution_id,
                        scheduled_task_id=task.id,
                        status=ExecutionStatus.PENDING,
                        scheduled_for=current_time,
                        retry_count=attempt,
                    )
                    session.add(execution)
                    task.last_run_at = current_time
                    session.commit()

                execution_task = asyncio.create_task(
                    self._submit_task_to_agent_mesh(task_id, execution_id)
                )

                async with self._execution_lock:
                    self.running_executions[execution_id] = execution_task

                execution_failed = False
                try:
                    await asyncio.wait_for(execution_task, timeout=timeout_seconds)

                    with self.session_factory() as session:
                        execution = session.get(ScheduledTaskExecutionModel, execution_id)
                        task = session.get(ScheduledTaskModel, task_id)
                        if execution and execution.status == ExecutionStatus.FAILED:
                            execution_failed = True
                        elif execution and execution.status == ExecutionStatus.COMPLETED:
                            # Phase 3.1: Reset failure count on success
                            if task:
                                task.consecutive_failure_count = 0
                                task.run_count = (task.run_count or 0) + 1
                                if task.status == "error":
                                    task.status = "active"
                                session.commit()
                                await self.notification_service.notify_execution_complete(
                                    execution=execution, task=task,
                                )

                except asyncio.TimeoutError:
                    log.error("[SchedulerService:%s] Execution %s timed out", self.instance_id, execution_id)
                    await self._handle_execution_timeout(execution_id)
                    execution_failed = True
                finally:
                    async with self._execution_lock:
                        self.running_executions.pop(execution_id, None)

                if not execution_failed:
                    # Success — exit the retry loop
                    break

                # Execution failed
                await self._track_failure(task_id)

                if attempt < max_retries:
                    log.info(
                        "[SchedulerService:%s] Scheduling retry %s/%s "
                        "for task %s in %ss",
                        self.instance_id, attempt + 1, max_retries, task_id, retry_delay_seconds,
                    )
                    await asyncio.sleep(retry_delay_seconds)
                else:
                    log.error(
                        "[SchedulerService:%s] Task %s failed after %s attempt(s)",
                        self.instance_id, task_id, attempt + 1,
                    )
                    with self.session_factory() as session:
                        execution = session.get(ScheduledTaskExecutionModel, execution_id)
                        task = session.get(ScheduledTaskModel, task_id)
                        if execution and task:
                            await self.notification_service.notify_execution_complete(
                                execution=execution, task=task,
                            )

            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Failed to execute scheduled task %s "
                    "(attempt %s): %s",
                    self.instance_id, task_id, attempt + 1, e,
                    exc_info=True,
                )
                if execution_id:
                    await self._handle_execution_failure(execution_id, "Execution failed due to an internal error")
                    await self._track_failure(task_id)

                if attempt < max_retries:
                    await asyncio.sleep(retry_delay_seconds)
                else:
                    break

            finally:
                # Execution history bounds: keep only last 100 (runs after every attempt)
                await self._enforce_execution_history_bounds(task_id)

    async def _track_failure(self, task_id: str):
        """Phase 3.1: Track consecutive failures and transition to error state."""
        try:
            with self.session_factory() as session:
                task = session.get(ScheduledTaskModel, task_id)
                if task:
                    task.consecutive_failure_count = (task.consecutive_failure_count or 0) + 1
                    if task.consecutive_failure_count >= 5:
                        task.status = "error"
                        log.warning(
                            "[SchedulerService:%s] Task %s reached 5 consecutive failures, "
                            "transitioning to error state",
                            self.instance_id, task_id,
                        )
                    session.commit()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to track failure for task %s: %s",
                self.instance_id, task_id, e,
                exc_info=True,
            )

    async def _enforce_execution_history_bounds(self, task_id: str):
        """Phase 3.4: Keep only the last 100 executions per task."""
        try:
            from ...repository.scheduled_task_repository import ScheduledTaskRepository
            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                deleted = repo.delete_oldest_executions(session, task_id, keep_count=100)
                if deleted > 0:
                    session.commit()
                    log.info(
                        "[SchedulerService:%s] Pruned %s old executions for task %s",
                        self.instance_id, deleted, task_id,
                    )
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to enforce execution history bounds: %s",
                self.instance_id, e,
                exc_info=True,
            )

    def _render_template_variables(self, text: str, task: ScheduledTaskModel, execution_id: str) -> str:
        """Phase 3.3: Render template variables in task message text.

        Uses simple str.replace() — no Jinja2 for security.
        """
        return self._render_template_variables_from_fields(
            text, task.name, task.run_count, execution_id
        )

    def _render_template_variables_from_fields(
        self, text: str, task_name: str, run_count: int, execution_id: str,
    ) -> str:
        """Render template variables using extracted field values (no ORM object needed)."""
        now = datetime.now(timezone.utc).isoformat()
        text = text.replace("{{schedule.name}}", task_name or "")
        text = text.replace("{{schedule.run_date}}", now)
        text = text.replace("{{schedule.run_count}}", str(run_count or 0))
        text = text.replace("{{execution.id}}", execution_id)
        return text

    async def _submit_task_to_agent_mesh(self, task_id: str, execution_id: str):
        """Submit the scheduled task to the agent mesh via A2A protocol.

        Reads task data and closes the DB session before performing any async
        I/O (publish, register, wait) so that a connection is not held open
        during network operations.
        """
        log.info(
            "[SchedulerService:%s] Submitting execution %s to agent mesh",
            self.instance_id, execution_id,
        )

        try:
            # --- Step 1: Read task data and build message (DB session scoped) ---
            with self.session_factory() as session:
                task = session.get(ScheduledTaskModel, task_id)
                if not task:
                    raise ValueError("Task %s not found" % task_id)

                # Extract all fields needed after session closes
                task_message_raw = task.task_message
                task_name = task.name
                task_run_count = task.run_count
                task_metadata_raw = task.task_metadata
                target_agent_name = task.target_agent_name
                task_user_id = task.user_id
                task_created_by = task.created_by

            # --- Step 2: Build A2A message (no session held) ---
            # Phase 3.3: Render template variables in message parts
            message_parts = []
            for part in task_message_raw:
                if part.get("type") == "text":
                    rendered_text = self._render_template_variables_from_fields(
                        part["text"], task_name, task_run_count, execution_id
                    )
                    message_parts.append(a2a.create_text_part(rendered_text))
                elif part.get("type") == "file":
                    message_parts.append(a2a.create_file_part_from_uri(part["uri"]))

            session_id = f"scheduler_{task_id}"
            context_id = f"scheduled_{execution_id}"
            a2a_task_id = f"task-{uuid.uuid4().hex}"

            # Filter task_metadata to safe keys only
            message_metadata = {}
            if task_metadata_raw:
                message_metadata = {
                    k: v for k, v in task_metadata_raw.items()
                    if k in _SAFE_METADATA_KEYS
                }
            message_metadata["sessionBehavior"] = "RUN_BASED"
            message_metadata["returnArtifacts"] = True

            a2a_message = a2a.create_user_message(
                parts=message_parts,
                context_id=context_id,
                task_id=a2a_task_id,
                metadata=message_metadata,
            )

            filtered_task_metadata = {
                k: v for k, v in (task_metadata_raw or {}).items()
                if k in _SAFE_METADATA_KEYS
            }
            request = a2a.create_send_streaming_message_request(
                message=a2a_message,
                task_id=a2a_task_id,
                metadata=filtered_task_metadata,
            )
            payload = request.model_dump(by_alias=True, exclude_none=True)

            target_topic = a2a.get_agent_request_topic(self.namespace, target_agent_name)
            reply_to_topic = f"{self.namespace}a2a/v1/scheduler/response/{self.instance_id}"
            status_topic = f"{self.namespace}a2a/v1/scheduler/status/{self.instance_id}"

            user_props = {
                "replyTo": reply_to_topic,
                "a2aStatusTopic": status_topic,
                "clientId": f"scheduler_{self.instance_id}",
                "userId": task_user_id or task_created_by or "system-scheduler",
            }

            # --- Step 3: Update execution status (brief session) ---
            with self.session_factory() as session:
                execution = session.get(ScheduledTaskExecutionModel, execution_id)
                if execution:
                    execution.status = ExecutionStatus.RUNNING
                    execution.a2a_task_id = a2a_task_id
                    execution.started_at = now_epoch_ms()
                    session.commit()

            # --- Step 4: Register, publish, and wait (no session held) ---
            if hasattr(self.result_handler, 'register_execution'):
                await self.result_handler.register_execution(execution_id, a2a_task_id, context_id)

            self.publish_func(target_topic, payload, user_props)

            log.info(
                "[SchedulerService:%s] Submitted execution %s as A2A task %s",
                self.instance_id, execution_id, a2a_task_id,
            )

            # Wait for the result handler to signal completion so the caller
            # sees the final execution status (COMPLETED / FAILED) rather than
            # the stale RUNNING state.
            if hasattr(self.result_handler, 'wait_for_completion'):
                await self.result_handler.wait_for_completion(execution_id)

        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to submit execution %s: %s",
                self.instance_id, execution_id, e,
                exc_info=True,
            )
            await self._handle_execution_failure(execution_id, "Execution failed due to an internal error")
            raise

    async def _handle_execution_failure(self, execution_id: str, error_message: str):
        """Mark an execution as failed."""
        try:
            with self.session_factory() as session:
                execution = session.get(ScheduledTaskExecutionModel, execution_id)
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = error_message
                    execution.completed_at = now_epoch_ms()
                    session.commit()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to mark execution %s as failed: %s",
                self.instance_id, execution_id, e,
                exc_info=True,
            )

    async def _handle_execution_timeout(self, execution_id: str):
        """Mark an execution as timed out."""
        try:
            with self.session_factory() as session:
                execution = session.get(ScheduledTaskExecutionModel, execution_id)
                if execution:
                    execution.status = ExecutionStatus.TIMEOUT
                    execution.error_message = "Execution timed out"
                    execution.completed_at = now_epoch_ms()
                    session.commit()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to mark execution %s as timeout: %s",
                self.instance_id, execution_id, e,
                exc_info=True,
            )

    async def is_leader(self) -> bool:
        """Check if this instance is the current leader."""
        return await self.leader_election.is_leader()

    async def handle_a2a_response(self, message_data: Dict[str, Any]):
        """Handle an A2A response message."""
        await self.result_handler.handle_response(message_data)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the scheduler service."""
        pending_count = 0
        if hasattr(self.result_handler, 'get_pending_count'):
            pending_count = self.result_handler.get_pending_count()

        k8s_managed_count = sum(1 for t in self.active_tasks.values() if t.get("k8s_managed", False))

        return {
            "instance_id": self.instance_id,
            "namespace": self.namespace,
            "is_leader": getattr(self.leader_election, '_is_leader', False),
            "active_tasks_count": len(self.active_tasks),
            "k8s_managed_tasks_count": k8s_managed_count,
            "apscheduler_managed_tasks_count": len(self.active_tasks) - k8s_managed_count,
            "running_executions_count": len(self.running_executions),
            "pending_results_count": pending_count,
            "scheduler_running": self.scheduler.running if self.scheduler else False,
            "leader_info": self.leader_election.get_leader_info() if self.leader_election else None,
            "use_stateless_collector": self.use_stateless_collector,
            "k8s_enabled": self.k8s_enabled,
            "k8s_manager_active": self.k8s_manager is not None,
        }
