"""
Core scheduler service for managing and executing scheduled tasks.
Integrates with APScheduler for cron/interval scheduling.

Single-instance architecture — no leader election or multi-instance coordination.
Tasks run forever while enabled; failures are tracked for observability only.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from solace_agent_mesh.common import a2a
from solace_agent_mesh.common.middleware.registry import MiddlewareRegistry
from solace_agent_mesh.core_a2a.service import CoreA2AService
from ...repository.models import (
    ExecutionStatus,
    ScheduledTaskExecutionModel,
    ScheduledTaskModel,
    ScheduleType,
)
from ...repository.models import SessionModel
from ...repository.scheduled_task_repository import ScheduledTaskRepository
from ...shared import now_epoch_ms, parse_interval_to_seconds
from .result_handler import ResultHandler
from .notification_service import NotificationService

log = logging.getLogger(__name__)

# Safe metadata keys that task_metadata may contain.
# Prevents callers from overriding protocol-level keys.
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_CONCURRENT_EXECUTIONS = 10
DEFAULT_STALE_EXECUTION_TIMEOUT_SECONDS = 7200
DEFAULT_STALE_CLEANUP_INTERVAL_SECONDS = 600
DEFAULT_RETRY_DELAY_SECONDS = 60
DEFAULT_EXECUTION_HISTORY_KEEP_COUNT = 100
DEFAULT_MISFIRE_GRACE_TIME = 60

_SAFE_METADATA_KEYS = frozenset({
    "priority",
    "tags",
    "category",
    "source",
})


class SchedulerService:
    """
    Core scheduling service for single-instance deployments.
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
        self.default_timeout_seconds = config.get("default_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        self.max_concurrent_executions = config.get("max_concurrent_executions", DEFAULT_MAX_CONCURRENT_EXECUTIONS)
        self.stale_execution_timeout_seconds = config.get("stale_execution_timeout_seconds", DEFAULT_STALE_EXECUTION_TIMEOUT_SECONDS)
        self.stale_cleanup_interval_seconds = config.get("stale_cleanup_interval_seconds", DEFAULT_STALE_CLEANUP_INTERVAL_SECONDS)

        self.scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "misfire_grace_time": DEFAULT_MISFIRE_GRACE_TIME,
                "coalesce": True,
            },
        )

        self.active_tasks: Dict[str, Any] = {}
        self.running_executions: Dict[str, asyncio.Task] = {}
        self._execution_lock = asyncio.Lock()
        # Per-task locks prevent overlapping executions of the same scheduled
        # task from corrupting the shared persistent ADK session.
        self._task_locks: Dict[str, asyncio.Lock] = {}

        # Initialize result handler (in-memory tracking)
        self.result_handler = ResultHandler(
            session_factory=session_factory,
            namespace=namespace,
            instance_id=instance_id,
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

        log.info(
            "[SchedulerService:%s] Initialized for namespace '%s'",
            instance_id, namespace,
        )

    async def start(self):
        """Start the scheduler service."""
        log.info("[SchedulerService:%s] Starting scheduler service", self.instance_id)

        self.scheduler.start()
        log.info("[SchedulerService:%s] APScheduler started", self.instance_id)

        # Single instance — load tasks directly on startup
        await self._load_scheduled_tasks()

        self._stale_cleanup_task = asyncio.create_task(self._stale_cleanup_loop())
        log.info("[SchedulerService:%s] Stale cleanup task started", self.instance_id)

    async def stop(self):
        """Stop the scheduler service."""
        log.info("[SchedulerService:%s] Stopping scheduler service", self.instance_id)

        self.scheduler.shutdown(wait=False)

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
                await asyncio.sleep(DEFAULT_RETRY_DELAY_SECONDS)

    async def _cleanup_stale_executions(self):
        """Clean up executions that have been running too long."""
        try:
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

                    # Clean up in-memory tracking
                    if execution.a2a_task_id:
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
                    )
                )
                tasks = session.execute(stmt).scalars().all()

                log.info("[SchedulerService:%s] Found %s enabled tasks", self.instance_id, len(tasks))

                for task in tasks:
                    try:
                        await self.schedule_task(task)
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
                await self.unschedule_task(task_id)
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Failed to unschedule task %s: %s",
                    self.instance_id, task_id, e,
                    exc_info=True,
                )

    async def schedule_task(self, task: ScheduledTaskModel):
        """Schedule a single task in APScheduler."""
        job_id = f"scheduled_task_{task.id}"

        log.info(
            "[SchedulerService:%s] Scheduling task '%s' "
            "(ID: %s, Type: %s)",
            self.instance_id, task.name, task.id, task.schedule_type,
        )

        try:
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

    async def unschedule_task(self, task_id: str):
        """Remove a task from APScheduler."""
        job_id = f"scheduled_task_{task_id}"

        if task_id in self.active_tasks:
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
        """Parse interval string to seconds (delegates to shared utility)."""
        return parse_interval_to_seconds(interval_str)

    async def _execute_scheduled_task(self, task_id: str):
        """Execute a scheduled task by submitting it to the agent mesh.

        Retries are handled iteratively (not recursively) to avoid deep call
        stacks and unnecessary resource retention between attempts.

        A per-task lock ensures only one execution is in-flight at a time,
        preventing concurrent writes to the shared persistent ADK session.
        """
        # Acquire a per-task lock so overlapping cron triggers for the same
        # task wait rather than corrupting the persistent session.
        if task_id not in self._task_locks:
            self._task_locks[task_id] = asyncio.Lock()
        task_lock = self._task_locks[task_id]

        if task_lock.locked():
            log.warning(
                "[SchedulerService:%s] Task %s already in-flight, skipping overlapping trigger",
                self.instance_id, task_id,
            )
            return

        async with task_lock:
            await self._execute_scheduled_task_inner(task_id)

    async def _execute_scheduled_task_inner(self, task_id: str):
        """Inner implementation of scheduled task execution (holds per-task lock)."""
        log.info(
            "[SchedulerService:%s] Executing scheduled task: %s",
            self.instance_id, task_id,
        )

        # Read task config once before the retry loop so retry behavior
        # is consistent even if the task is updated mid-execution.
        timeout_seconds = self.default_timeout_seconds
        max_retries = 0
        retry_delay_seconds = DEFAULT_RETRY_DELAY_SECONDS

        with self.session_factory() as session:
            task = session.get(ScheduledTaskModel, task_id)
            if not task:
                log.warning("[SchedulerService:%s] Task %s not found", self.instance_id, task_id)
                return
            timeout_seconds = task.timeout_seconds or self.default_timeout_seconds
            max_retries = task.max_retries or 0
            retry_delay_seconds = task.retry_delay_seconds or DEFAULT_RETRY_DELAY_SECONDS
            # Snapshot task fields for the retry loop so we don't re-read
            task_snapshot = {
                "task_message": task.task_message,
                "name": task.name,
                "run_count": task.run_count,
                "task_metadata": task.task_metadata,
                "target_agent_name": task.target_agent_name,
                "user_id": task.user_id,
                "created_by": task.created_by,
                "timezone": task.timezone,
            }

        for attempt in range(max_retries + 1):
            execution_id = None
            try:
                # Hold the lock from count check through insertion to prevent
                # concurrent coroutines from exceeding max_concurrent_executions.
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
                        self._submit_task_to_agent_mesh(task_id, execution_id, task_snapshot)
                    )

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
                            if task:
                                task.consecutive_failure_count = 0
                                task.run_count = (task.run_count or 0) + 1
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

                # Execution failed — track for observability (does not stop scheduling)
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
        """Track consecutive failures for observability. Does not affect scheduling."""
        try:
            with self.session_factory() as session:
                task = session.get(ScheduledTaskModel, task_id)
                if task:
                    task.consecutive_failure_count = (task.consecutive_failure_count or 0) + 1
                    session.commit()
        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to track failure for task %s: %s",
                self.instance_id, task_id, e,
                exc_info=True,
            )

    async def _enforce_execution_history_bounds(self, task_id: str):
        """Keep only the last 100 executions per task."""
        try:
            repo = ScheduledTaskRepository()
            with self.session_factory() as session:
                deleted = repo.delete_oldest_executions(session, task_id, keep_count=DEFAULT_EXECUTION_HISTORY_KEEP_COUNT)
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
        """Render template variables in task message text.

        Uses simple str.replace() — no Jinja2 for security.
        """
        return self._render_template_variables_from_fields(
            text, task.name, task.run_count, execution_id, task.timezone
        )

    def _render_template_variables_from_fields(
        self, text: str, task_name: str, run_count: int, execution_id: str,
        task_timezone: str = "UTC",
    ) -> str:
        """Render template variables using extracted field values (no ORM object needed).

        {{schedule.run_date}} is rendered in the task's configured timezone,
        not UTC, so the value matches the user's scheduling context.
        """
        try:
            tz = pytz.timezone(task_timezone)
            now = datetime.now(tz).isoformat()
        except Exception:
            now = datetime.now(timezone.utc).isoformat()
        text = text.replace("{{schedule.name}}", task_name or "")
        text = text.replace("{{schedule.run_date}}", now)
        text = text.replace("{{schedule.run_count}}", str(run_count or 0))
        text = text.replace("{{execution.id}}", execution_id)
        return text

    async def _submit_task_to_agent_mesh(self, task_id: str, execution_id: str, task_snapshot: Dict[str, Any] = None):
        """Submit the scheduled task to the agent mesh via A2A protocol.

        Uses a pre-read task_snapshot when available so that retry behaviour
        stays consistent even if the task definition is updated concurrently.
        """
        log.info(
            "[SchedulerService:%s] Submitting execution %s to agent mesh",
            self.instance_id, execution_id,
        )

        try:
            # --- Step 1: Use snapshot or read task data (DB session scoped) ---
            if task_snapshot:
                task_message_raw = task_snapshot["task_message"]
                task_name = task_snapshot["name"]
                task_run_count = task_snapshot["run_count"]
                task_metadata_raw = task_snapshot["task_metadata"]
                target_agent_name = task_snapshot["target_agent_name"]
                task_user_id = task_snapshot["user_id"]
                task_created_by = task_snapshot["created_by"]
                task_timezone = task_snapshot["timezone"]
            else:
                with self.session_factory() as session:
                    task = session.get(ScheduledTaskModel, task_id)
                    if not task:
                        raise ValueError("Task %s not found" % task_id)

                    task_message_raw = task.task_message
                    task_name = task.name
                    task_run_count = task.run_count
                    task_metadata_raw = task.task_metadata
                    target_agent_name = task.target_agent_name
                    task_user_id = task.user_id
                    task_created_by = task.created_by
                    task_timezone = task.timezone

            # --- Step 1b: Create session and mark execution RUNNING in a single transaction ---
            # This makes scheduled task outputs visible in the chat session list
            # and ensures artifacts flow through the standard artifact service.
            # Both operations are committed together to avoid orphaned session records
            # if the execution status update were to fail separately.
            user_id = task_user_id or task_created_by or "system-scheduler"
            stable_session_id = f"scheduled_task_{task_id}"
            session_id = f"scheduled_{execution_id}"
            try:
                with self.session_factory() as sess:
                    now = now_epoch_ms()
                    session_record = SessionModel(
                        id=session_id,
                        name=f"{task_name}",
                        user_id=user_id,
                        agent_id=target_agent_name,
                        source="scheduler",
                        created_time=now,
                        updated_time=now,
                    )
                    sess.add(session_record)

                    # Also mark execution as RUNNING in the same transaction
                    execution = sess.get(ScheduledTaskExecutionModel, execution_id)
                    if execution:
                        execution.status = ExecutionStatus.RUNNING
                        execution.started_at = now
                    sess.commit()

                    # Verify session was persisted to avoid inconsistent state
                    # if the commit partially failed or was rolled back.
                    persisted = sess.get(SessionModel, session_id)
                    if not persisted:
                        raise RuntimeError(
                            "Session %s was not found after commit" % session_id
                        )
            except Exception as e:
                log.error(
                    "[SchedulerService:%s] Failed to create session for execution %s: %s",
                    self.instance_id, execution_id, e,
                    exc_info=True,
                )
                raise RuntimeError(
                    "Cannot proceed without a valid session for execution %s" % execution_id
                ) from e

            # --- Step 2: Build A2A message (no session held) ---
            message_parts = []
            for part in task_message_raw:
                if part.get("type") == "text":
                    rendered_text = self._render_template_variables_from_fields(
                        part["text"], task_name, task_run_count, execution_id, task_timezone
                    )
                    message_parts.append(a2a.create_text_part(rendered_text))
                elif part.get("type") == "file":
                    message_parts.append(a2a.create_file_part_from_uri(part["uri"]))

            context_id = session_id
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

            # Resolve user config for the task creator so the enterprise capability
            # filter allows peer agent tools.  Without this, the orchestrator's
            # _filter_tools_by_capability_callback strips peer tools because
            # _enterprise_capabilities is empty.
            a2a_user_config = await self._resolve_user_config_for_task(
                user_id, task_created_by
            )

            user_props = {
                "replyTo": reply_to_topic,
                "a2aStatusTopic": status_topic,
                "clientId": f"scheduler_{self.instance_id}",
                "userId": task_user_id or task_created_by or "system-scheduler",
            }
            if a2a_user_config:
                user_props["a2aUserConfig"] = a2a_user_config

            # --- Step 3: Set a2a_task_id on execution (brief session) ---
            with self.session_factory() as session:
                execution = session.get(ScheduledTaskExecutionModel, execution_id)
                if execution:
                    execution.a2a_task_id = a2a_task_id
                    session.commit()

            # --- Step 4: Register, publish, and wait (no session held) ---
            await self.result_handler.register_execution(execution_id, a2a_task_id, session_id)

            self.publish_func(target_topic, payload, user_props)

            log.info(
                "[SchedulerService:%s] Submitted execution %s as A2A task %s",
                self.instance_id, execution_id, a2a_task_id,
            )

            # Wait for the result handler to signal completion
            await self.result_handler.wait_for_completion(execution_id)

        except Exception as e:
            log.error(
                "[SchedulerService:%s] Failed to submit execution %s: %s",
                self.instance_id, execution_id, e,
                exc_info=True,
            )
            await self._handle_execution_failure(execution_id, "Execution failed due to an internal error")
            raise

    async def _resolve_user_config_for_task(
        self, user_id: str, created_by: str
    ) -> Optional[Dict[str, Any]]:
        """Resolve user configuration for a scheduled task execution.

        The enterprise capability filter requires ``_enterprise_capabilities``
        in the ``a2aUserConfig`` user-property so that the orchestrator's
        ``_filter_tools_by_capability_callback`` does not strip peer-agent
        tools.  Regular chat requests get this from the gateway's
        ``resolve_user_config`` call; scheduled tasks must do the same.

        Returns the resolved user config dict, or ``None`` on failure.
        """
        effective_user = user_id or created_by or "system-scheduler"
        try:
            config_resolver = MiddlewareRegistry.get_config_resolver()
            user_identity = {"id": effective_user, "name": effective_user}
            gateway_context = {
                "gateway_id": f"scheduler_{self.instance_id}",
                "gateway_app_config": {},
            }
            user_config = await config_resolver.resolve_user_config(
                user_identity, gateway_context, {}
            )
            user_config["user_profile"] = user_identity
            log.info(
                "[SchedulerService:%s] Resolved user config for '%s' with %d enterprise capabilities",
                self.instance_id,
                effective_user,
                len(user_config.get("_enterprise_capabilities", [])),
            )
            return user_config
        except Exception as e:
            log.warning(
                "[SchedulerService:%s] Failed to resolve user config for '%s': %s. "
                "Proceeding without user config — enterprise capability filter may restrict tools.",
                self.instance_id, effective_user, e,
            )
            return None

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
        """Always True — single-instance architecture."""
        return True

    async def handle_a2a_response(self, message_data: Dict[str, Any]):
        """Handle an A2A response message."""
        await self.result_handler.handle_response(message_data)

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the scheduler service."""
        pending_count = self.result_handler.get_pending_count()

        return {
            "instance_id": self.instance_id,
            "namespace": self.namespace,
            "active_tasks_count": len(self.active_tasks),
            "running_executions_count": len(self.running_executions),
            "pending_results_count": pending_count,
            "scheduler_running": self.scheduler.running if self.scheduler else False,
        }
