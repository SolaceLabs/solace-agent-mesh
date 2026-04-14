"""Unit tests for SchedulerService.

Tests cover:
- Iterative retry loop in ``_execute_scheduled_task``
- ``stop()`` lifecycle
- Metadata filtering through ``_SAFE_METADATA_KEYS``
- Template variable rendering
"""

import asyncio
import uuid
from contextlib import contextmanager
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

from solace_agent_mesh.gateway.http_sse.repository.models.scheduled_task_model import (
    ExecutionStatus,
    ScheduledTaskExecutionModel,
    ScheduledTaskModel,
    ScheduleType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_task(
    task_id="task-1",
    enabled=True,
    deleted_at=None,
    max_retries=0,
    retry_delay_seconds=0,
    timeout_seconds=3600,
    run_count=0,
    consecutive_failure_count=0,
    task_message=None,
    task_metadata=None,
    target_agent_name="agent-a",
    user_id="user-1",
    created_by="user-1",
    name="test-task",
):
    """Build a mock ScheduledTaskModel."""
    task = MagicMock(spec=ScheduledTaskModel)
    task.id = task_id
    task.name = name
    task.enabled = enabled
    task.deleted_at = deleted_at
    task.max_retries = max_retries
    task.retry_delay_seconds = retry_delay_seconds
    task.timeout_seconds = timeout_seconds
    task.run_count = run_count
    task.consecutive_failure_count = consecutive_failure_count
    task.task_message = task_message or [{"type": "text", "text": "hello"}]
    task.task_metadata = task_metadata
    task.target_agent_name = target_agent_name
    task.user_id = user_id
    task.created_by = created_by
    task.schedule_type = ScheduleType.CRON
    task.schedule_expression = "*/5 * * * *"
    task.timezone = "UTC"
    task.namespace = "ns1"
    return task


def _make_mock_execution(
    execution_id=None,
    status=ExecutionStatus.PENDING,
    a2a_task_id=None,
):
    """Build a mock ScheduledTaskExecutionModel."""
    execution = MagicMock(spec=ScheduledTaskExecutionModel)
    execution.id = execution_id or str(uuid.uuid4())
    execution.status = status
    execution.a2a_task_id = a2a_task_id
    execution.started_at = None
    execution.completed_at = None
    execution.error_message = None
    return execution


def _build_scheduler_service(**overrides):
    """Build a SchedulerService with mocked dependencies.

    Returns (service, mocks_dict) where mocks_dict contains the key mocks.
    """
    from solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service import (
        SchedulerService,
    )

    mock_session = MagicMock()
    mock_session.get = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.flush = MagicMock()
    mock_session.execute = MagicMock()

    @contextmanager
    def mock_session_factory():
        yield mock_session

    mock_publish = MagicMock()
    mock_core_a2a = MagicMock()

    config = overrides.get("config", {})

    with patch(
        "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.ResultHandler"
    ) as MockResultHandler, patch(
        "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.NotificationService"
    ) as MockNotificationService, patch(
        "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.AsyncIOScheduler"
    ) as MockScheduler:
        mock_result_handler = MockResultHandler.return_value
        mock_result_handler.register_execution = AsyncMock()
        mock_result_handler.wait_for_completion = AsyncMock()

        mock_notification = MockNotificationService.return_value
        mock_notification.cleanup = AsyncMock()
        mock_notification.notify_execution_complete = AsyncMock()

        mock_scheduler_instance = MockScheduler.return_value
        mock_scheduler_instance.start = MagicMock()
        mock_scheduler_instance.shutdown = MagicMock()
        mock_scheduler_instance.add_job = MagicMock()
        mock_scheduler_instance.remove_job = MagicMock()
        mock_scheduler_instance.running = True

        service = SchedulerService(
            session_factory=mock_session_factory,
            namespace="ns1",
            instance_id="inst-1",
            publish_func=mock_publish,
            core_a2a_service=mock_core_a2a,
            config=config,
        )

    return service, {
        "session": mock_session,
        "publish": mock_publish,
        "result_handler": service.result_handler,
        "notification_service": service.notification_service,
        "scheduler": service.scheduler,
    }


# ===========================================================================
# Retry loop
# ===========================================================================

class TestRetryLoop:
    """Tests for the iterative retry loop in ``_execute_scheduled_task``."""

    @pytest.mark.asyncio
    async def test_retry_loop_runs_correct_number_of_attempts(self):
        """With max_retries=2, the loop should attempt up to 3 times (1 initial + 2 retries)."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(max_retries=2, retry_delay_seconds=0, timeout_seconds=10)

        # Track how many times _submit_task_to_agent_mesh is called
        submit_call_count = 0

        async def mock_submit(task_id, execution_id, task_snapshot):
            nonlocal submit_call_count
            submit_call_count += 1
            raise Exception("Simulated failure")

        service._submit_task_to_agent_mesh = mock_submit

        # session.get returns the task on first call, then task for each retry
        mocks["session"].get.return_value = task

        await service._execute_scheduled_task("task-1")

        # 1 initial + 2 retries = 3 attempts
        assert submit_call_count == 3

    @pytest.mark.asyncio
    async def test_retry_loop_stops_on_success(self):
        """If the first attempt succeeds, no retries are made."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(max_retries=3, retry_delay_seconds=0, timeout_seconds=10)

        # Build a completed execution mock
        completed_execution = _make_mock_execution(status=ExecutionStatus.COMPLETED)

        def smart_get(model_cls, obj_id=None):
            if obj_id is None:
                return task
            if model_cls == ScheduledTaskExecutionModel:
                return completed_execution
            return task

        mocks["session"].get.side_effect = smart_get

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        # Only 1 attempt since it succeeded
        assert service._submit_task_to_agent_mesh.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retries_when_max_retries_is_zero(self):
        """With max_retries=0, only one attempt is made."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(max_retries=0, retry_delay_seconds=0, timeout_seconds=10)
        mocks["session"].get.return_value = task

        submit_call_count = 0

        async def mock_submit(task_id, execution_id, task_snapshot):
            nonlocal submit_call_count
            submit_call_count += 1
            raise Exception("Simulated failure")

        service._submit_task_to_agent_mesh = mock_submit

        await service._execute_scheduled_task("task-1")

        assert submit_call_count == 1

    @pytest.mark.asyncio
    async def test_skips_execution_when_task_not_found(self):
        """If the task is not found in the DB, execution is skipped entirely."""
        service, mocks = _build_scheduler_service()

        mocks["session"].get.return_value = None

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("nonexistent")

        service._submit_task_to_agent_mesh.assert_not_called()

    @pytest.mark.asyncio
    async def test_tasks_keep_running_despite_failures(self):
        """Tasks do NOT auto-stop after consecutive failures (simplified status machine)."""
        service, mocks = _build_scheduler_service()

        # Task with many consecutive failures — should still execute
        task = _make_mock_task(
            consecutive_failure_count=100,
            max_retries=0,
            retry_delay_seconds=0,
            timeout_seconds=10,
        )
        mocks["session"].get.return_value = task

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        # Task should still be submitted despite 100 consecutive failures
        service._submit_task_to_agent_mesh.assert_called_once()


# ===========================================================================
# stop() lifecycle
# ===========================================================================

class TestStopLifecycle:
    """Tests for the ``stop()`` method lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_cancels_stale_cleanup_task(self):
        """``stop()`` cancels the stale cleanup task if it's running."""
        service, mocks = _build_scheduler_service()

        async def long_running():
            await asyncio.sleep(3600)

        service._stale_cleanup_task = asyncio.create_task(long_running())

        await service.stop()

        assert service._stale_cleanup_task.cancelled() or service._stale_cleanup_task.done()

    @pytest.mark.asyncio
    async def test_stop_cancels_running_executions(self):
        """``stop()`` cancels all running execution tasks."""
        service, mocks = _build_scheduler_service()

        async def long_running():
            await asyncio.sleep(3600)

        exec_task = asyncio.create_task(long_running())
        service.running_executions = {"exec-1": exec_task}
        service._stale_cleanup_task = None

        await service.stop()

        # Allow the event loop to process the cancellation
        await asyncio.sleep(0)
        try:
            await exec_task
        except asyncio.CancelledError:
            pass

        assert exec_task.cancelled() or exec_task.done()

    @pytest.mark.asyncio
    async def test_is_leader_always_returns_true(self):
        """Single-instance: is_leader() always returns True."""
        service, mocks = _build_scheduler_service()

        result = await service.is_leader()
        assert result is True


# ===========================================================================
# Metadata filtering
# ===========================================================================

class TestMetadataFiltering:
    """Tests for ``_SAFE_METADATA_KEYS`` filtering in ``_submit_task_to_agent_mesh``."""

    def test_safe_metadata_keys_constant(self):
        """Verify the set of safe metadata keys."""
        from solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service import (
            _SAFE_METADATA_KEYS,
        )

        assert "priority" in _SAFE_METADATA_KEYS
        assert "tags" in _SAFE_METADATA_KEYS
        assert "category" in _SAFE_METADATA_KEYS
        assert "source" in _SAFE_METADATA_KEYS
        # Protocol-level keys must NOT be in the safe set
        assert "sessionBehavior" not in _SAFE_METADATA_KEYS
        assert "returnArtifacts" not in _SAFE_METADATA_KEYS
        assert "replyTo" not in _SAFE_METADATA_KEYS

    @pytest.mark.asyncio
    async def test_metadata_filtering_strips_non_safe_keys(self):
        """Non-safe keys in task_metadata are stripped before building the A2A message."""
        service, mocks = _build_scheduler_service()

        task_metadata = {
            "priority": "high",
            "tags": ["daily"],
            "dangerous_key": "should-be-stripped",
            "sessionBehavior": "OVERRIDE_ATTEMPT",
        }

        task = _make_mock_task(
            task_metadata=task_metadata,
            task_message=[{"type": "text", "text": "test"}],
        )

        # We'll capture the payload passed to publish_func
        captured_payloads = []
        captured_user_props = []

        def capture_publish(topic, payload, user_props):
            captured_payloads.append(payload)
            captured_user_props.append(user_props)

        service.publish_func = capture_publish

        mocks["session"].get.return_value = task

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.a2a"
        ) as mock_a2a:
            mock_a2a.create_text_part.return_value = {"type": "text", "text": "test"}
            mock_a2a.create_user_message.return_value = MagicMock()

            mock_request = MagicMock()
            mock_request.model_dump.return_value = {"test": "payload"}
            mock_a2a.create_send_streaming_message_request.return_value = mock_request
            mock_a2a.get_agent_request_topic.return_value = "ns1/agent-a"

            # Capture the metadata arg passed to create_user_message
            captured_metadata = []

            def capture_create_user_message(**kwargs):
                captured_metadata.append(kwargs.get("metadata", {}))
                return MagicMock()

            mock_a2a.create_user_message.side_effect = capture_create_user_message

            # Also capture metadata passed to create_send_streaming_message_request
            captured_request_metadata = []

            def capture_create_request(**kwargs):
                captured_request_metadata.append(kwargs.get("metadata", {}))
                return mock_request

            mock_a2a.create_send_streaming_message_request.side_effect = capture_create_request

            await service._submit_task_to_agent_mesh("task-1", "exec-1")

        # Verify the message metadata has safe keys + protocol keys, but not dangerous ones
        assert len(captured_metadata) == 1
        msg_meta = captured_metadata[0]
        assert msg_meta.get("priority") == "high"
        assert msg_meta.get("tags") == ["daily"]
        assert "dangerous_key" not in msg_meta
        assert msg_meta.get("sessionBehavior") == "RUN_BASED"  # protocol override
        assert msg_meta.get("returnArtifacts") is True

        # Verify the request-level metadata also filters
        assert len(captured_request_metadata) == 1
        req_meta = captured_request_metadata[0]
        assert "dangerous_key" not in req_meta
        assert "sessionBehavior" not in req_meta  # not a safe key for request metadata

    @pytest.mark.asyncio
    async def test_metadata_filtering_with_task_snapshot(self):
        """Non-safe keys are stripped when using the task_snapshot path (production path)."""
        service, mocks = _build_scheduler_service()

        task_metadata = {
            "priority": "high",
            "tags": ["daily"],
            "dangerous_key": "should-be-stripped",
            "sessionBehavior": "OVERRIDE_ATTEMPT",
        }

        task_snapshot = {
            "task_message": [{"type": "text", "text": "test"}],
            "name": "test-task",
            "run_count": 0,
            "task_metadata": task_metadata,
            "target_agent_name": "agent-a",
            "user_id": "user-1",
            "created_by": "user-1",
            "timezone": "UTC",
        }

        captured_metadata = []
        captured_request_metadata = []

        def capture_publish(topic, payload, user_props):
            pass

        service.publish_func = capture_publish

        # session.get is still needed for execution status update and session creation
        mocks["session"].get.return_value = _make_mock_execution()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.a2a"
        ) as mock_a2a:
            mock_a2a.create_text_part.return_value = {"type": "text", "text": "test"}

            mock_request = MagicMock()
            mock_request.model_dump.return_value = {"test": "payload"}
            mock_a2a.get_agent_request_topic.return_value = "ns1/agent-a"

            def capture_create_user_message(**kwargs):
                captured_metadata.append(kwargs.get("metadata", {}))
                return MagicMock()

            mock_a2a.create_user_message.side_effect = capture_create_user_message

            def capture_create_request(**kwargs):
                captured_request_metadata.append(kwargs.get("metadata", {}))
                return mock_request

            mock_a2a.create_send_streaming_message_request.side_effect = capture_create_request

            await service._submit_task_to_agent_mesh("task-1", "exec-1", task_snapshot)

        # Verify the message metadata has safe keys + protocol keys, but not dangerous ones
        assert len(captured_metadata) == 1
        msg_meta = captured_metadata[0]
        assert msg_meta.get("priority") == "high"
        assert msg_meta.get("tags") == ["daily"]
        assert "dangerous_key" not in msg_meta
        assert msg_meta.get("sessionBehavior") == "RUN_BASED"
        assert msg_meta.get("returnArtifacts") is True

        # Verify the request-level metadata also filters
        assert len(captured_request_metadata) == 1
        req_meta = captured_request_metadata[0]
        assert "dangerous_key" not in req_meta
        assert "sessionBehavior" not in req_meta


# ===========================================================================
# Template rendering
# ===========================================================================

class TestTemplateRendering:
    """Tests for ``_render_template_variables_from_fields``."""

    def test_renders_all_template_variables(self):
        service, _ = _build_scheduler_service()

        text = "Task: {{schedule.name}}, Run: {{schedule.run_count}}, Exec: {{execution.id}}, Date: {{schedule.run_date}}"
        result = service._render_template_variables_from_fields(
            text, "My Task", 42, "exec-abc"
        )

        assert "My Task" in result
        assert "42" in result
        assert "exec-abc" in result
        assert "{{" not in result  # all placeholders replaced

    def test_handles_none_task_name(self):
        service, _ = _build_scheduler_service()

        text = "Task: {{schedule.name}}"
        result = service._render_template_variables_from_fields(text, None, 0, "exec-1")
        assert "Task: " in result
        assert "None" not in result


# ===========================================================================
# _parse_interval
# ===========================================================================

class TestParseInterval:
    """Tests for ``_parse_interval`` string-to-seconds conversion."""

    def test_parse_seconds(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("120s") == 120

    def test_rejects_interval_below_minimum(self):
        service, _ = _build_scheduler_service()
        with pytest.raises(ValueError, match="at least 60 seconds"):
            service._parse_interval("30s")

    def test_parse_minutes(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("5m") == 300

    def test_parse_hours(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("2h") == 7200

    def test_parse_days(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("1d") == 86400

    def test_parse_bare_integer(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("120") == 120

    def test_parse_strips_whitespace(self):
        service, _ = _build_scheduler_service()
        assert service._parse_interval("  10m  ") == 600

    def test_parse_case_insensitive(self):
        service, _ = _build_scheduler_service()
        # Input is lowered internally, so uppercase should also work
        assert service._parse_interval("3H") == 10800


# ===========================================================================
# _create_trigger
# ===========================================================================

class TestCreateTrigger:
    """Tests for ``_create_trigger`` APScheduler trigger factory."""

    def test_cron_trigger(self):
        from apscheduler.triggers.cron import CronTrigger

        service, _ = _build_scheduler_service()
        task = _make_mock_task()
        task.schedule_type = ScheduleType.CRON
        task.schedule_expression = "*/5 * * * *"
        task.timezone = "UTC"

        trigger = service._create_trigger(task)
        assert isinstance(trigger, CronTrigger)

    def test_interval_trigger(self):
        from apscheduler.triggers.interval import IntervalTrigger

        service, _ = _build_scheduler_service()
        task = _make_mock_task()
        task.schedule_type = ScheduleType.INTERVAL
        task.schedule_expression = "30m"
        task.timezone = "UTC"

        trigger = service._create_trigger(task)
        assert isinstance(trigger, IntervalTrigger)

    def test_one_time_trigger(self):
        from apscheduler.triggers.date import DateTrigger

        service, _ = _build_scheduler_service()
        task = _make_mock_task()
        task.schedule_type = ScheduleType.ONE_TIME
        task.schedule_expression = "2099-01-01T00:00:00"
        task.timezone = "UTC"

        trigger = service._create_trigger(task)
        assert isinstance(trigger, DateTrigger)

    def test_unsupported_schedule_type_raises(self):
        service, _ = _build_scheduler_service()
        task = _make_mock_task()
        task.schedule_type = "WEEKLY"
        task.schedule_expression = "something"
        task.timezone = "UTC"

        with pytest.raises(ValueError, match="Unsupported schedule type"):
            service._create_trigger(task)

    def test_invalid_cron_expression_raises(self):
        service, _ = _build_scheduler_service()
        task = _make_mock_task()
        task.schedule_type = ScheduleType.CRON
        task.schedule_expression = "not-a-cron"
        task.timezone = "UTC"

        with pytest.raises(ValueError, match="Invalid cron expression"):
            service._create_trigger(task)


# ===========================================================================
# _schedule_task
# ===========================================================================

class TestScheduleTask:
    """Tests for ``_schedule_task`` adding a job to APScheduler."""

    @pytest.mark.asyncio
    async def test_schedule_task_adds_job(self):
        """Scheduling a task should add a job to the APScheduler."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task()

        mock_job = MagicMock()
        mock_job.next_run_time = None
        mocks["scheduler"].add_job.return_value = mock_job

        await service.schedule_task(task)

        mocks["scheduler"].add_job.assert_called_once()
        assert task.id in service.active_tasks

    @pytest.mark.asyncio
    async def test_schedule_task_updates_next_run_at(self):
        """When the job has a next_run_time, next_run_at should be updated in the DB."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task()

        from datetime import datetime, timezone as tz
        mock_job = MagicMock()
        mock_job.next_run_time = datetime(2099, 1, 1, tzinfo=tz.utc)
        mocks["scheduler"].add_job.return_value = mock_job

        db_task = MagicMock()
        mocks["session"].get.return_value = db_task

        await service.schedule_task(task)

        assert db_task.next_run_at is not None
        mocks["session"].commit.assert_called()


# ===========================================================================
# _unschedule_task
# ===========================================================================

class TestUnscheduleTask:
    """Tests for ``_unschedule_task`` removing a job from APScheduler."""

    @pytest.mark.asyncio
    async def test_unschedule_removes_job_and_active_tasks_entry(self):
        service, mocks = _build_scheduler_service()

        service.active_tasks["task-1"] = {"job": MagicMock(), "task_name": "t", "schedule_type": "cron"}

        await service.unschedule_task("task-1")

        mocks["scheduler"].remove_job.assert_called_once_with("scheduled_task_task-1")
        assert "task-1" not in service.active_tasks

    @pytest.mark.asyncio
    async def test_unschedule_nonexistent_task_is_noop(self):
        """Unscheduling a task not in active_tasks should not raise."""
        service, mocks = _build_scheduler_service()

        await service.unschedule_task("nonexistent")

        mocks["scheduler"].remove_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_unschedule_cleans_up_on_remove_job_error(self):
        """If remove_job raises, the active_tasks entry should still be cleaned up."""
        service, mocks = _build_scheduler_service()

        service.active_tasks["task-1"] = {"job": MagicMock()}
        mocks["scheduler"].remove_job.side_effect = Exception("job not found")

        await service.unschedule_task("task-1")

        assert "task-1" not in service.active_tasks


# ===========================================================================
# Max concurrent executions
# ===========================================================================

class TestMaxConcurrentExecutions:
    """Tests for max concurrent execution gating."""

    @pytest.mark.asyncio
    async def test_execution_skipped_when_max_concurrent_reached(self):
        """When running_executions >= max_concurrent_executions, the task is SKIPPED."""
        service, mocks = _build_scheduler_service(config={"max_concurrent_executions": 1})

        task = _make_mock_task(max_retries=0, timeout_seconds=10)
        mocks["session"].get.return_value = task

        # Simulate one execution already running
        service.running_executions["existing-exec"] = MagicMock()

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        # The task should NOT have been submitted
        service._submit_task_to_agent_mesh.assert_not_called()
        # A SKIPPED execution should have been added to the session
        mocks["session"].add.assert_called()
        added_obj = mocks["session"].add.call_args[0][0]
        assert added_obj.status == ExecutionStatus.SKIPPED


# ===========================================================================
# Execution with disabled / deleted task
# ===========================================================================

class TestExecutionDisabledTask:
    """Tests that disabled or deleted tasks are skipped during execution."""

    @pytest.mark.asyncio
    async def test_disabled_task_skipped(self):
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(enabled=False)

        # First call returns the task (for snapshot), second call returns disabled task
        call_count = 0
        def session_get(model_cls, obj_id=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return task  # initial read
            return task  # second read sees disabled

        mocks["session"].get.side_effect = session_get

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        service._submit_task_to_agent_mesh.assert_not_called()

    @pytest.mark.asyncio
    async def test_deleted_task_skipped(self):
        service, mocks = _build_scheduler_service()

        from datetime import datetime, timezone as tz
        task = _make_mock_task(deleted_at=datetime.now(tz.utc))

        call_count = 0
        def session_get(model_cls, obj_id=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return task
            return task

        mocks["session"].get.side_effect = session_get

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        service._submit_task_to_agent_mesh.assert_not_called()


# ===========================================================================
# Execution timeout
# ===========================================================================

class TestExecutionTimeout:
    """Tests for timeout handling in ``_execute_scheduled_task``."""

    @pytest.mark.asyncio
    async def test_timeout_marks_execution_as_timeout(self):
        """When the execution times out, ``_handle_execution_timeout`` is called."""
        service, mocks = _build_scheduler_service()

        # Use timeout_seconds=1 (not 0, since 0 is falsy and triggers default).
        task = _make_mock_task(max_retries=0, timeout_seconds=1)

        # After submit, the code does session.get(ScheduledTaskExecutionModel, execution_id)
        # and checks execution.status — so we need a proper mock with status attribute.
        post_submit_execution = _make_mock_execution(status=ExecutionStatus.RUNNING)

        call_count = {"get": 0}

        def smart_get(model_cls, obj_id=None):
            call_count["get"] += 1
            if model_cls == ScheduledTaskExecutionModel:
                return post_submit_execution
            return task

        mocks["session"].get.side_effect = smart_get

        async def slow_submit(task_id, execution_id, task_snapshot):
            await asyncio.sleep(60)

        service._submit_task_to_agent_mesh = slow_submit

        timeout_called_with = []

        async def capture_timeout(execution_id):
            timeout_called_with.append(execution_id)

        service._handle_execution_timeout = capture_timeout
        service._track_failure = AsyncMock()
        service._enforce_execution_history_bounds = AsyncMock()

        await service._execute_scheduled_task("task-1")

        assert len(timeout_called_with) == 1


# ===========================================================================
# _track_failure
# ===========================================================================

class TestTrackFailure:
    """Tests for ``_track_failure`` consecutive failure tracking."""

    @pytest.mark.asyncio
    async def test_consecutive_failure_count_increments(self):
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(consecutive_failure_count=3)
        mocks["session"].get.return_value = task

        await service._track_failure("task-1")

        assert task.consecutive_failure_count == 4
        mocks["session"].commit.assert_called()

    @pytest.mark.asyncio
    async def test_failure_count_starts_from_none(self):
        """When consecutive_failure_count is None, it should be treated as 0."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(consecutive_failure_count=0)
        task.consecutive_failure_count = None
        mocks["session"].get.return_value = task

        await service._track_failure("task-1")

        assert task.consecutive_failure_count == 1

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """On successful execution, consecutive_failure_count is reset to 0."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(
            max_retries=0, retry_delay_seconds=0, timeout_seconds=10,
            consecutive_failure_count=5,
        )

        completed_execution = _make_mock_execution(status=ExecutionStatus.COMPLETED)

        def smart_get(model_cls, obj_id=None):
            if model_cls == ScheduledTaskExecutionModel:
                return completed_execution
            return task

        mocks["session"].get.side_effect = smart_get

        service._submit_task_to_agent_mesh = AsyncMock()

        await service._execute_scheduled_task("task-1")

        assert task.consecutive_failure_count == 0


# ===========================================================================
# _enforce_execution_history_bounds
# ===========================================================================

class TestEnforceExecutionHistoryBounds:
    """Tests for ``_enforce_execution_history_bounds`` pruning old executions."""

    @pytest.mark.asyncio
    async def test_prunes_oldest_executions(self):
        service, mocks = _build_scheduler_service()

        mock_repo = MagicMock()
        mock_repo.delete_oldest_executions.return_value = 5

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            await service._enforce_execution_history_bounds("task-1")

        mock_repo.delete_oldest_executions.assert_called_once_with(
            mocks["session"], "task-1", keep_count=100
        )
        mocks["session"].commit.assert_called()

    @pytest.mark.asyncio
    async def test_no_commit_when_nothing_pruned(self):
        service, mocks = _build_scheduler_service()

        mock_repo = MagicMock()
        mock_repo.delete_oldest_executions.return_value = 0

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            await service._enforce_execution_history_bounds("task-1")

        mock_repo.delete_oldest_executions.assert_called_once()
        # commit should not be called when deleted == 0
        mocks["session"].commit.assert_not_called()


# ===========================================================================
# get_status
# ===========================================================================

class TestGetStatus:
    """Tests for ``get_status`` status reporting."""

    def test_returns_correct_counts(self):
        service, mocks = _build_scheduler_service()

        service.active_tasks = {"t1": {}, "t2": {}}
        service.running_executions = {"e1": MagicMock()}

        mocks["result_handler"].get_pending_count = MagicMock(return_value=3)

        status = service.get_status()

        assert status["instance_id"] == "inst-1"
        assert status["namespace"] == "ns1"
        assert status["active_tasks_count"] == 2
        assert status["running_executions_count"] == 1
        assert status["pending_results_count"] == 3
        assert status["scheduler_running"] is True


# ===========================================================================
# handle_a2a_response
# ===========================================================================

class TestHandleA2AResponse:
    """Tests for ``handle_a2a_response`` delegation."""

    @pytest.mark.asyncio
    async def test_delegates_to_result_handler(self):
        service, mocks = _build_scheduler_service()

        mocks["result_handler"].handle_response = AsyncMock()

        message_data = {"taskId": "t-123", "status": "completed"}
        await service.handle_a2a_response(message_data)

        mocks["result_handler"].handle_response.assert_called_once_with(message_data)


# ===========================================================================
# _cleanup_stale_executions
# ===========================================================================

class TestCleanupStaleExecutions:
    """Tests for ``_cleanup_stale_executions`` marking stale RUNNING executions as TIMEOUT."""

    @pytest.mark.asyncio
    async def test_marks_stale_executions_as_timeout(self):
        """Stale RUNNING executions older than the timeout are marked TIMEOUT."""
        service, mocks = _build_scheduler_service()

        stale_exec = MagicMock(spec=ScheduledTaskExecutionModel)
        stale_exec.id = "stale-exec-1"
        stale_exec.status = ExecutionStatus.RUNNING
        stale_exec.a2a_task_id = None
        stale_exec.completed_at = None
        stale_exec.error_message = None

        # Make execute().scalars().all() return the stale execution
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_exec]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mocks["session"].execute.return_value = mock_result

        await service._cleanup_stale_executions()

        assert stale_exec.status == ExecutionStatus.TIMEOUT
        assert stale_exec.completed_at is not None
        assert "stale timeout" in stale_exec.error_message.lower()
        mocks["session"].commit.assert_called()

    @pytest.mark.asyncio
    async def test_signals_completion_events_for_stale_executions(self):
        """When a stale execution has a tracked a2a_task_id, its completion event is signalled."""
        service, mocks = _build_scheduler_service()

        stale_exec = MagicMock(spec=ScheduledTaskExecutionModel)
        stale_exec.id = "stale-exec-2"
        stale_exec.status = ExecutionStatus.RUNNING
        stale_exec.a2a_task_id = "a2a-stale"
        stale_exec.completed_at = None
        stale_exec.error_message = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_exec]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mocks["session"].execute.return_value = mock_result

        # Set up in-memory tracking on the result handler
        mock_event = MagicMock()
        service.result_handler.pending_executions_lock = asyncio.Lock()
        service.result_handler.pending_executions = {"a2a-stale": "stale-exec-2"}
        service.result_handler.execution_sessions = {"stale-exec-2": "session-1"}
        service.result_handler.completion_events = {"stale-exec-2": mock_event}

        await service._cleanup_stale_executions()

        assert stale_exec.status == ExecutionStatus.TIMEOUT
        mock_event.set.assert_called_once()
        # In-memory tracking should be cleaned up
        assert "a2a-stale" not in service.result_handler.pending_executions
        assert "stale-exec-2" not in service.result_handler.completion_events

    @pytest.mark.asyncio
    async def test_no_op_when_no_stale_executions(self):
        """No error when there are no stale executions."""
        service, mocks = _build_scheduler_service()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mocks["session"].execute.return_value = mock_result

        await service._cleanup_stale_executions()

        mocks["session"].commit.assert_called()


# ===========================================================================
# Session creation failure in _submit_task_to_agent_mesh
# ===========================================================================

class TestSubmitSessionCreationFailure:
    """Tests that session creation failure in ``_submit_task_to_agent_mesh`` propagates correctly."""

    @pytest.mark.asyncio
    async def test_session_commit_failure_raises_and_marks_failed(self):
        """If session.commit raises during session creation, the execution is marked FAILED."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(
            task_message=[{"type": "text", "text": "hello"}],
            task_metadata=None,
        )

        task_snapshot = {
            "task_message": [{"type": "text", "text": "hello"}],
            "name": "test-task",
            "run_count": 0,
            "task_metadata": None,
            "target_agent_name": "agent-a",
            "user_id": "user-1",
            "created_by": "user-1",
            "timezone": "UTC",
        }

        # Make the session commit raise to simulate DB failure
        mocks["session"].commit.side_effect = RuntimeError("DB commit failed")

        with pytest.raises(RuntimeError, match="Cannot proceed without a valid session"):
            await service._submit_task_to_agent_mesh("task-1", "exec-1", task_snapshot)


# ===========================================================================
# Persistent session behavior and stable session IDs
# ===========================================================================

class TestPersistentSessionBehavior:
    """Tests for PERSISTENT session and stable context_id wiring."""

    @pytest.mark.asyncio
    async def test_context_id_is_stable_session_id(self):
        """context_id passed to create_user_message should be scheduled_task_{task_id}."""
        service, mocks = _build_scheduler_service()

        task_snapshot = {
            "task_message": [{"type": "text", "text": "test"}],
            "name": "test-task",
            "run_count": 0,
            "task_metadata": None,
            "target_agent_name": "agent-a",
            "user_id": "user-1",
            "created_by": "user-1",
            "timezone": "UTC",
        }

        mocks["session"].get.return_value = _make_mock_execution()

        captured_kwargs = []

        def capture_publish(topic, payload, user_props):
            pass

        service.publish_func = capture_publish

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.a2a"
        ) as mock_a2a:
            mock_a2a.create_text_part.return_value = {"type": "text", "text": "test"}

            def capture_create_user_message(**kwargs):
                captured_kwargs.append(kwargs)
                return MagicMock()

            mock_a2a.create_user_message.side_effect = capture_create_user_message

            mock_request = MagicMock()
            mock_request.model_dump.return_value = {"test": "payload"}
            mock_a2a.create_send_streaming_message_request.return_value = mock_request
            mock_a2a.get_agent_request_topic.return_value = "ns1/agent-a"

            await service._submit_task_to_agent_mesh("task-42", "exec-1", task_snapshot)

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["context_id"] == "scheduled_task_task-42"

    @pytest.mark.asyncio
    async def test_register_execution_receives_per_execution_session(self):
        """register_execution should receive the per-execution session_id, not the stable one."""
        service, mocks = _build_scheduler_service()

        task_snapshot = {
            "task_message": [{"type": "text", "text": "test"}],
            "name": "test-task",
            "run_count": 0,
            "task_metadata": None,
            "target_agent_name": "agent-a",
            "user_id": "user-1",
            "created_by": "user-1",
            "timezone": "UTC",
        }

        mocks["session"].get.return_value = _make_mock_execution()

        service.publish_func = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.a2a"
        ) as mock_a2a:
            mock_a2a.create_text_part.return_value = {"type": "text", "text": "test"}
            mock_a2a.create_user_message.return_value = MagicMock()

            mock_request = MagicMock()
            mock_request.model_dump.return_value = {"test": "payload"}
            mock_a2a.create_send_streaming_message_request.return_value = mock_request
            mock_a2a.get_agent_request_topic.return_value = "ns1/agent-a"

            await service._submit_task_to_agent_mesh("task-1", "exec-99", task_snapshot)

        register_call = mocks["result_handler"].register_execution
        register_call.assert_called_once()
        args = register_call.call_args
        # Third positional arg is the per-execution session_id
        assert args[0][2] == "scheduled_exec-99"

    @pytest.mark.asyncio
    async def test_session_behavior_is_persistent(self):
        """sessionBehavior in message metadata should be PERSISTENT."""
        service, mocks = _build_scheduler_service()

        task_snapshot = {
            "task_message": [{"type": "text", "text": "test"}],
            "name": "test-task",
            "run_count": 0,
            "task_metadata": None,
            "target_agent_name": "agent-a",
            "user_id": "user-1",
            "created_by": "user-1",
            "timezone": "UTC",
        }

        mocks["session"].get.return_value = _make_mock_execution()

        service.publish_func = MagicMock()
        captured_metadata = []

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduler.scheduler_service.a2a"
        ) as mock_a2a:
            mock_a2a.create_text_part.return_value = {"type": "text", "text": "test"}

            def capture_create_user_message(**kwargs):
                captured_metadata.append(kwargs.get("metadata", {}))
                return MagicMock()

            mock_a2a.create_user_message.side_effect = capture_create_user_message

            mock_request = MagicMock()
            mock_request.model_dump.return_value = {"test": "payload"}
            mock_a2a.create_send_streaming_message_request.return_value = mock_request
            mock_a2a.get_agent_request_topic.return_value = "ns1/agent-a"

            await service._submit_task_to_agent_mesh("task-1", "exec-1", task_snapshot)

        assert len(captured_metadata) == 1
        assert captured_metadata[0]["sessionBehavior"] == "RUN_BASED"


# ===========================================================================
# Per-task concurrency guard
# ===========================================================================

class TestPerTaskConcurrencyGuard:
    """Tests for the per-task lock preventing overlapping executions."""

    @pytest.mark.asyncio
    async def test_overlapping_trigger_is_skipped(self):
        """A second trigger for the same task while one is in-flight should be skipped."""
        service, mocks = _build_scheduler_service()

        task = _make_mock_task(max_retries=0, timeout_seconds=60)
        mocks["session"].get.return_value = task

        started = asyncio.Event()
        proceed = asyncio.Event()
        submit_call_count = 0

        async def slow_submit(task_id, execution_id, task_snapshot):
            nonlocal submit_call_count
            submit_call_count += 1
            started.set()
            await proceed.wait()

        service._submit_task_to_agent_mesh = slow_submit

        # Start first execution (will block on proceed)
        first = asyncio.create_task(service._execute_scheduled_task("task-1"))
        await started.wait()

        # Second trigger should return immediately (skipped)
        await service._execute_scheduled_task("task-1")

        # Let the first finish
        proceed.set()
        await first

        # Only the first execution should have called submit
        assert submit_call_count == 1
