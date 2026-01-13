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
        """
        Initialize the scheduler service.

        Args:
            session_factory: Factory function to create database sessions
            namespace: Namespace for A2A communication
            instance_id: Unique identifier for this scheduler instance
            publish_func: Function to publish messages to the broker
            core_a2a_service: Service for A2A protocol operations
            config: Optional configuration dictionary
            sse_manager: Optional SSE manager for notifications
        """
        self.session_factory = session_factory
        self.namespace = namespace
        self.instance_id = instance_id
        self.publish_func = publish_func
        self.core_a2a_service = core_a2a_service

        # Configuration
        config = config or {}
        self.default_timeout_seconds = config.get("default_timeout_seconds", 3600)
        self.max_concurrent_executions = config.get("max_concurrent_executions", 10)
        self.stale_execution_timeout_seconds = config.get("stale_execution_timeout_seconds", 7200)
        self.stale_cleanup_interval_seconds = config.get("stale_cleanup_interval_seconds", 3600)
        
        # K8s mode configuration
        self.use_stateless_collector = config.get("use_stateless_collector", False)
        self.k8s_enabled = config.get("k8s_enabled", False)
        self.k8s_config = config.get("k8s", {})

        # Leader election configuration
        leader_config = config.get("leader_election", {})
        heartbeat_interval = leader_config.get("heartbeat_interval_seconds", 30)
        lease_duration = leader_config.get("lease_duration_seconds", 60)

        # Initialize leader election
        self.leader_election = LeaderElection(
            session_factory=session_factory,
            instance_id=instance_id,
            namespace=namespace,
            heartbeat_interval_seconds=heartbeat_interval,
            lease_duration_seconds=lease_duration,
        )

        # APScheduler instance
        self.scheduler = AsyncIOScheduler(timezone="UTC")

        # Track active scheduled tasks
        self.active_tasks: Dict[str, Any] = {}

        # Track running executions
        self.running_executions: Dict[str, asyncio.Task] = {}
        
        # Lock for concurrent execution tracking
        self._execution_lock = asyncio.Lock()

        # Initialize result handler (stateless or in-memory based on config)
        self.result_handler: Union[ResultHandler, StatelessResultCollector]
        if self.use_stateless_collector:
            log.info(
                f"[SchedulerService:{instance_id}] Using StatelessResultCollector for K8s horizontal scaling"
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
                        f"[SchedulerService:{instance_id}] K8s enabled but no executor_image configured. "
                        "K8s CronJob management will be disabled."
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
                        f"[SchedulerService:{instance_id}] K8s CronJob manager initialized "
                        f"(namespace: {k8s_namespace}, image: {executor_image})"
                    )
            except ImportError as e:
                log.warning(
                    f"[SchedulerService:{instance_id}] K8s enabled but kubernetes package not installed: {e}"
                )
            except Exception as e:
                log.error(
                    f"[SchedulerService:{instance_id}] Failed to initialize K8s manager: {e}",
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
        
        # Stale cleanup task
        self._stale_cleanup_task: Optional[asyncio.Task] = None

        log.info(
            f"[SchedulerService:{instance_id}] Initialized for namespace '{namespace}' "
            f"(stateless_collector={self.use_stateless_collector}, k8s_enabled={self.k8s_enabled})"
        )

    async def start(self):
        """Start the scheduler service."""
        log.info(f"[SchedulerService:{self.instance_id}] Starting scheduler service")

        # Start leader election
        await self.leader_election.start()

        # Start APScheduler
        self.scheduler.start()
        log.info(f"[SchedulerService:{self.instance_id}] APScheduler started")

        # Monitor leadership and load tasks when we become leader
        asyncio.create_task(self._monitor_leadership())
        
        # Start stale execution cleanup task
        self._stale_cleanup_task = asyncio.create_task(self._stale_cleanup_loop())
        log.info(f"[SchedulerService:{self.instance_id}] Stale cleanup task started")

    async def stop(self):
        """Stop the scheduler service."""
        log.info(f"[SchedulerService:{self.instance_id}] Stopping scheduler service")

        # Stop leader election
        await self.leader_election.stop()

        # Shutdown APScheduler
        self.scheduler.shutdown(wait=False)
        
        # Cancel stale cleanup task
        if self._stale_cleanup_task and not self._stale_cleanup_task.done():
            self._stale_cleanup_task.cancel()
            try:
                await self._stale_cleanup_task
            except asyncio.CancelledError:
                pass
            log.info(f"[SchedulerService:{self.instance_id}] Stale cleanup task stopped")

        # Cancel running executions
        for execution_id, task in list(self.running_executions.items()):
            log.info(
                f"[SchedulerService:{self.instance_id}] Cancelling execution {execution_id}"
            )
            task.cancel()
        
        # Cleanup notification service
        await self.notification_service.cleanup()

        log.info(f"[SchedulerService:{self.instance_id}] Stopped")
    
    async def _stale_cleanup_loop(self):
        """Periodically clean up stale executions."""
        while True:
            try:
                await asyncio.sleep(self.stale_cleanup_interval_seconds)
                
                # Only run cleanup if we're the leader
                if await self.leader_election.is_leader():
                    log.info(f"[SchedulerService:{self.instance_id}] Running stale execution cleanup")
                    await self._cleanup_stale_executions()
                    
            except asyncio.CancelledError:
                log.info(f"[SchedulerService:{self.instance_id}] Stale cleanup loop cancelled")
                break
            except Exception as e:
                log.error(
                    f"[SchedulerService:{self.instance_id}] Error in stale cleanup loop: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(60)  # Back off on error
    
    async def _cleanup_stale_executions(self):
        """Clean up executions that have been running too long."""
        try:
            # Use the result handler's cleanup method if it's a StatelessResultCollector
            if self.use_stateless_collector and hasattr(self.result_handler, 'cleanup_stale_executions'):
                await self.result_handler.cleanup_stale_executions(self.stale_execution_timeout_seconds)
                return
            
            cutoff_time = now_epoch_ms() - (self.stale_execution_timeout_seconds * 1000)
            
            with self.session_factory() as session:
                # Find running executions older than cutoff
                stmt = select(ScheduledTaskExecutionModel).where(
                    ScheduledTaskExecutionModel.status == ExecutionStatus.RUNNING,
                    ScheduledTaskExecutionModel.started_at < cutoff_time,
                )
                stale_executions = session.execute(stmt).scalars().all()
                
                for execution in stale_executions:
                    log.warning(
                        f"[SchedulerService:{self.instance_id}] Found stale execution {execution.id}, marking as timeout"
                    )
                    execution.status = ExecutionStatus.TIMEOUT
                    execution.completed_at = now_epoch_ms()
                    execution.error_message = f"Execution exceeded stale timeout of {self.stale_execution_timeout_seconds} seconds"
                    
                    # Remove from pending in result handler (only for non-stateless mode)
                    if not self.use_stateless_collector and execution.a2a_task_id:
                        if hasattr(self.result_handler, 'pending_executions_lock'):
                            async with self.result_handler.pending_executions_lock:
                                if execution.a2a_task_id in self.result_handler.pending_executions:
                                    del self.result_handler.pending_executions[execution.a2a_task_id]
                
                session.commit()
                
                if stale_executions:
                    log.info(
                        f"[SchedulerService:{self.instance_id}] Cleaned up {len(stale_executions)} stale executions"
                    )
                    
        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Error cleaning up stale executions: {e}",
                exc_info=True,
            )

    async def _monitor_leadership(self):
        """Monitor leadership status and react to changes."""
        was_leader = False

        while True:
            try:
                is_leader = await self.leader_election.is_leader()

                if is_leader and not was_leader:
                    # We just became the leader
                    log.info(
                        f"[SchedulerService:{self.instance_id}] Became leader, loading tasks"
                    )
                    await self._on_become_leader()
                    was_leader = True

                elif not is_leader and was_leader:
                    # We lost leadership
                    log.warning(
                        f"[SchedulerService:{self.instance_id}] Lost leadership, unloading tasks"
                    )
                    await self._on_lose_leadership()
                    was_leader = False

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(
                    f"[SchedulerService:{self.instance_id}] Error monitoring leadership: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(5)

    async def _on_become_leader(self):
        """Called when this instance becomes the leader."""
        try:
            await self._load_scheduled_tasks()
        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to load tasks on becoming leader: {e}",
                exc_info=True,
            )

    async def _on_lose_leadership(self):
        """Called when this instance loses leadership."""
        try:
            await self._unload_all_tasks()
        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to unload tasks on losing leadership: {e}",
                exc_info=True,
            )

    async def _load_scheduled_tasks(self):
        """Load all enabled scheduled tasks from database and schedule them."""
        log.info(
            f"[SchedulerService:{self.instance_id}] Loading scheduled tasks from database"
        )

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

                log.info(
                    f"[SchedulerService:{self.instance_id}] Found {len(tasks)} enabled tasks"
                )

                for task in tasks:
                    try:
                        await self._schedule_task(task)
                    except Exception as e:
                        log.error(
                            f"[SchedulerService:{self.instance_id}] Failed to schedule task {task.id}: {e}",
                            exc_info=True,
                        )

        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to load scheduled tasks: {e}",
                exc_info=True,
            )

    async def _unload_all_tasks(self):
        """Unload all scheduled tasks from APScheduler."""
        log.info(
            f"[SchedulerService:{self.instance_id}] Unloading all scheduled tasks"
        )

        for task_id in list(self.active_tasks.keys()):
            try:
                await self._unschedule_task(task_id)
            except Exception as e:
                log.error(
                    f"[SchedulerService:{self.instance_id}] Failed to unschedule task {task_id}: {e}",
                    exc_info=True,
                )

    async def _schedule_task(self, task: ScheduledTaskModel):
        """
        Schedule a single task in APScheduler or K8s CronJob.

        Args:
            task: The scheduled task model to schedule
        """
        job_id = f"scheduled_task_{task.id}"

        log.info(
            f"[SchedulerService:{self.instance_id}] Scheduling task '{task.name}' (ID: {task.id}, Type: {task.schedule_type})"
        )

        try:
            # If K8s manager is enabled, sync to K8s CronJob
            if self.k8s_manager:
                log.info(
                    f"[SchedulerService:{self.instance_id}] Syncing task '{task.name}' to K8s CronJob"
                )
                success = await self.k8s_manager.sync_task(task)
                if success:
                    self.active_tasks[task.id] = {
                        "job": None,  # K8s manages the job
                        "task_name": task.name,
                        "schedule_type": task.schedule_type,
                        "k8s_managed": True,
                    }
                    log.info(
                        f"[SchedulerService:{self.instance_id}] Task '{task.name}' synced to K8s"
                    )
                    return
                else:
                    log.warning(
                        f"[SchedulerService:{self.instance_id}] Failed to sync task '{task.name}' to K8s, falling back to APScheduler"
                    )
            
            # Create appropriate trigger based on schedule type
            trigger = self._create_trigger(task)

            # Add job to APScheduler
            job = self.scheduler.add_job(
                self._execute_scheduled_task,
                trigger=trigger,
                args=[task.id],
                id=job_id,
                replace_existing=True,
                max_instances=1,  # Prevent concurrent executions of same task
            )

            self.active_tasks[task.id] = {
                "job": job,
                "task_name": task.name,
                "schedule_type": task.schedule_type,
                "k8s_managed": False,
            }

            # Update next_run_at in database
            if job.next_run_time:
                next_run_ms = int(job.next_run_time.timestamp() * 1000)
                with self.session_factory() as session:
                    db_task = session.get(ScheduledTaskModel, task.id)
                    if db_task:
                        db_task.next_run_at = next_run_ms
                        session.commit()

            log.info(
                f"[SchedulerService:{self.instance_id}] Scheduled task '{task.name}', next run: {job.next_run_time}"
            )

        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to schedule task {task.id}: {e}",
                exc_info=True,
            )
            raise

    async def _unschedule_task(self, task_id: str):
        """
        Remove a task from APScheduler or K8s CronJob.

        Args:
            task_id: ID of the task to unschedule
        """
        job_id = f"scheduled_task_{task_id}"

        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            
            # If K8s managed, delete from K8s
            if task_info.get("k8s_managed") and self.k8s_manager:
                try:
                    schedule_type = task_info.get("schedule_type")
                    await self.k8s_manager.delete_cronjob(task_id, schedule_type)
                    del self.active_tasks[task_id]
                    log.info(
                        f"[SchedulerService:{self.instance_id}] Deleted K8s CronJob for task {task_id}"
                    )
                    return
                except Exception as e:
                    log.error(
                        f"[SchedulerService:{self.instance_id}] Failed to delete K8s CronJob for task {task_id}: {e}",
                        exc_info=True,
                    )
            
            # Remove from APScheduler
            try:
                self.scheduler.remove_job(job_id)
                del self.active_tasks[task_id]
                log.info(
                    f"[SchedulerService:{self.instance_id}] Unscheduled task {task_id}"
                )
            except Exception as e:
                # Job might have already been removed (e.g., one-time task that executed)
                # This is not an error, just clean up our tracking
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                log.debug(
                    f"[SchedulerService:{self.instance_id}] Task {task_id} not in scheduler (may have already executed): {e}"
                )

    def _create_trigger(self, task: ScheduledTaskModel):
        """
        Create an APScheduler trigger based on task configuration.

        Args:
            task: The scheduled task model

        Returns:
            APScheduler trigger instance
        """
        if task.schedule_type == ScheduleType.CRON:
            # Validate cron expression
            if not croniter.is_valid(task.schedule_expression):
                raise ValueError(
                    f"Invalid cron expression: {task.schedule_expression}"
                )

            return CronTrigger.from_crontab(
                task.schedule_expression, timezone=task.timezone
            )

        elif task.schedule_type == ScheduleType.INTERVAL:
            # Parse interval (expecting format like "30s", "5m", "1h", "1d")
            interval_seconds = self._parse_interval(task.schedule_expression)
            return IntervalTrigger(seconds=interval_seconds, timezone=task.timezone)

        elif task.schedule_type == ScheduleType.ONE_TIME:
            # Parse ISO 8601 datetime
            run_date = datetime.fromisoformat(task.schedule_expression)
            return DateTrigger(run_date=run_date, timezone=task.timezone)

        else:
            raise ValueError(f"Unsupported schedule type: {task.schedule_type}")

    def _parse_interval(self, interval_str: str) -> int:
        """
        Parse interval string to seconds.

        Args:
            interval_str: Interval string (e.g., "30s", "5m", "1h", "1d")

        Returns:
            Interval in seconds
        """
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
            # Assume seconds if no unit
            return int(interval_str)

    async def _execute_scheduled_task(self, task_id: str, retry_count: int = 0):
        """
        Execute a scheduled task by submitting it to the agent mesh.

        Args:
            task_id: ID of the scheduled task to execute
            retry_count: Current retry attempt (0 = first attempt)
        """
        log.info(
            f"[SchedulerService:{self.instance_id}] Executing scheduled task: {task_id} (attempt {retry_count + 1})"
        )

        execution_id = None
        timeout_seconds = self.default_timeout_seconds
        max_retries = 0
        retry_delay_seconds = 60
        task_name = None

        try:
            # Check max concurrent executions limit
            async with self._execution_lock:
                current_running = len(self.running_executions)
                if current_running >= self.max_concurrent_executions:
                    log.warning(
                        f"[SchedulerService:{self.instance_id}] Max concurrent executions ({self.max_concurrent_executions}) reached, skipping task {task_id}"
                    )
                    # Record skipped execution
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

            # Load task from database and get configuration
            with self.session_factory() as session:
                task = session.get(ScheduledTaskModel, task_id)
                if not task or not task.enabled or task.deleted_at:
                    log.warning(
                        f"[SchedulerService:{self.instance_id}] Task {task_id} not found, disabled, or deleted"
                    )
                    return

                # Get configuration before session closes
                timeout_seconds = task.timeout_seconds
                max_retries = task.max_retries or 0
                retry_delay_seconds = task.retry_delay_seconds or 60
                task_name = task.name

                # Create execution record
                execution_id = str(uuid.uuid4())
                current_time = now_epoch_ms()

                execution = ScheduledTaskExecutionModel(
                    id=execution_id,
                    scheduled_task_id=task.id,
                    status=ExecutionStatus.PENDING,
                    scheduled_for=current_time,
                    retry_count=retry_count,
                )
                session.add(execution)

                # Update last_run_at
                task.last_run_at = current_time
                session.commit()

            # Submit task to agent mesh
            execution_task = asyncio.create_task(
                self._submit_task_to_agent_mesh(task_id, execution_id)
            )
            
            async with self._execution_lock:
                self.running_executions[execution_id] = execution_task

            # Wait for completion (with timeout)
            execution_failed = False
            error_message = None
            try:
                await asyncio.wait_for(
                    execution_task,
                    timeout=timeout_seconds,
                )
                
                # Check if execution completed successfully
                with self.session_factory() as session:
                    execution = session.get(ScheduledTaskExecutionModel, execution_id)
                    task = session.get(ScheduledTaskModel, task_id)
                    if execution and execution.status == ExecutionStatus.FAILED:
                        execution_failed = True
                        error_message = execution.error_message
                    elif execution and execution.status == ExecutionStatus.COMPLETED:
                        # Send success notification
                        if task:
                            await self.notification_service.notify_execution_complete(
                                execution=execution,
                                task=task,
                            )
                        
            except asyncio.TimeoutError:
                log.error(
                    f"[SchedulerService:{self.instance_id}] Execution {execution_id} timed out"
                )
                await self._handle_execution_timeout(execution_id)
                execution_failed = True
                error_message = "Execution timed out"
            finally:
                async with self._execution_lock:
                    if execution_id in self.running_executions:
                        del self.running_executions[execution_id]

            # Handle retry logic if execution failed
            if execution_failed and retry_count < max_retries:
                log.info(
                    f"[SchedulerService:{self.instance_id}] Scheduling retry {retry_count + 1}/{max_retries} for task {task_id} in {retry_delay_seconds}s"
                )
                # Schedule retry after delay
                await asyncio.sleep(retry_delay_seconds)
                await self._execute_scheduled_task(task_id, retry_count + 1)
            elif execution_failed:
                # All retries exhausted, send failure notification
                log.error(
                    f"[SchedulerService:{self.instance_id}] Task {task_id} failed after {retry_count + 1} attempts"
                )
                # Send failure notification
                with self.session_factory() as session:
                    execution = session.get(ScheduledTaskExecutionModel, execution_id)
                    task = session.get(ScheduledTaskModel, task_id)
                    if execution and task:
                        await self.notification_service.notify_execution_complete(
                            execution=execution,
                            task=task,
                        )

        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to execute scheduled task {task_id}: {e}",
                exc_info=True,
            )
            if execution_id:
                await self._handle_execution_failure(execution_id, str(e))
                
                # Attempt retry on exception
                if retry_count < max_retries:
                    log.info(
                        f"[SchedulerService:{self.instance_id}] Scheduling retry {retry_count + 1}/{max_retries} for task {task_id} after exception"
                    )
                    await asyncio.sleep(retry_delay_seconds)
                    await self._execute_scheduled_task(task_id, retry_count + 1)
                else:
                    # Send failure notification
                    with self.session_factory() as session:
                        execution = session.get(ScheduledTaskExecutionModel, execution_id)
                        task = session.get(ScheduledTaskModel, task_id)
                        if execution and task:
                            await self.notification_service.notify_execution_complete(
                                execution=execution,
                                task=task,
                            )

    async def _submit_task_to_agent_mesh(self, task_id: str, execution_id: str):
        """
        Submit the scheduled task to the agent mesh via A2A protocol.

        Args:
            task_id: ID of the scheduled task
            execution_id: ID of the execution record
        """
        log.info(
            f"[SchedulerService:{self.instance_id}] Submitting execution {execution_id} to agent mesh"
        )

        try:
            with self.session_factory() as session:
                task = session.get(ScheduledTaskModel, task_id)
                if not task:
                    raise ValueError(f"Task {task_id} not found")

                # Create A2A message from task configuration
                message_parts = []
                for part in task.task_message:
                    if part.get("type") == "text":
                        message_parts.append(a2a.create_text_part(part["text"]))
                    elif part.get("type") == "file":
                        message_parts.append(
                            a2a.create_file_part_from_uri(part["uri"])
                        )

                # Create session and context IDs
                session_id = f"scheduler_{task.id}"
                context_id = f"scheduled_{execution_id}"
                a2a_task_id = f"task-{uuid.uuid4().hex}"

                # Prepare message metadata with RUN_BASED session behavior
                # This prevents the agent from filtering text in the final response
                message_metadata = task.task_metadata.copy() if task.task_metadata else {}
                message_metadata["sessionBehavior"] = "RUN_BASED"
                # Request artifact listing in the final response for scheduled tasks
                message_metadata["returnArtifacts"] = True

                # Create A2A message with metadata
                a2a_message = a2a.create_user_message(
                    parts=message_parts,
                    context_id=context_id,
                    task_id=a2a_task_id,
                    metadata=message_metadata
                )

                # Build A2A request manually (bypass CoreA2AService due to contextId bug)
                request = a2a.create_send_streaming_message_request(
                    message=a2a_message,
                    task_id=a2a_task_id,
                    metadata=task.task_metadata,  # Keep original task metadata in request
                )
                payload = request.model_dump(by_alias=True, exclude_none=True)

                # Create topics
                target_topic = a2a.get_agent_request_topic(self.namespace, task.target_agent_name)
                reply_to_topic = f"{self.namespace}a2a/v1/scheduler/response/{self.instance_id}"
                status_topic = f"{self.namespace}a2a/v1/scheduler/status/{self.instance_id}"

                # Create user properties
                user_props = {
                    "replyTo": reply_to_topic,
                    "a2aStatusTopic": status_topic,
                    "clientId": f"scheduler_{self.instance_id}",
                    "userId": task.user_id or "system",
                }

                topic = target_topic

                # Update execution record
                execution = session.get(ScheduledTaskExecutionModel, execution_id)
                if execution:
                    execution.status = ExecutionStatus.RUNNING
                    execution.a2a_task_id = a2a_task_id
                    execution.started_at = now_epoch_ms()
                    session.commit()

                # Register execution with result handler (pass session_id for artifact URIs)
                # Note: StatelessResultCollector doesn't need registration (uses DB lookup)
                if hasattr(self.result_handler, 'register_execution'):
                    await self.result_handler.register_execution(execution_id, a2a_task_id, context_id)

                # Publish to broker
                self.publish_func(topic, payload, user_props)

                log.info(
                    f"[SchedulerService:{self.instance_id}] Submitted execution {execution_id} as A2A task {a2a_task_id}"
                )

        except Exception as e:
            log.error(
                f"[SchedulerService:{self.instance_id}] Failed to submit execution {execution_id}: {e}",
                exc_info=True,
            )
            await self._handle_execution_failure(execution_id, str(e))
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
                f"[SchedulerService:{self.instance_id}] Failed to mark execution {execution_id} as failed: {e}",
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
                f"[SchedulerService:{self.instance_id}] Failed to mark execution {execution_id} as timeout: {e}",
                exc_info=True,
            )

    async def is_leader(self) -> bool:
        """Check if this instance is the current leader."""
        return await self.leader_election.is_leader()

    async def handle_a2a_response(self, message_data: Dict[str, Any]):
        """
        Handle an A2A response message.
        
        Args:
            message_data: Dictionary containing topic, payload, and user_properties
        """
        await self.result_handler.handle_response(message_data)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the scheduler service.

        Returns:
            Dictionary with status information
        """
        # Get pending count (only available for non-stateless mode)
        pending_count = 0
        if hasattr(self.result_handler, 'get_pending_count'):
            pending_count = self.result_handler.get_pending_count()
        
        # Count K8s managed vs APScheduler managed tasks
        k8s_managed_count = sum(1 for t in self.active_tasks.values() if t.get("k8s_managed", False))
        apscheduler_managed_count = len(self.active_tasks) - k8s_managed_count
        
        return {
            "instance_id": self.instance_id,
            "namespace": self.namespace,
            "is_leader": getattr(self.leader_election, '_is_leader', False),
            "active_tasks_count": len(self.active_tasks),
            "k8s_managed_tasks_count": k8s_managed_count,
            "apscheduler_managed_tasks_count": apscheduler_managed_count,
            "running_executions_count": len(self.running_executions),
            "pending_results_count": pending_count,
            "scheduler_running": self.scheduler.running if self.scheduler else False,
            "leader_info": self.leader_election.get_leader_info() if self.leader_election else None,
            "use_stateless_collector": self.use_stateless_collector,
            "k8s_enabled": self.k8s_enabled,
            "k8s_manager_active": self.k8s_manager is not None,
        }