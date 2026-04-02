"""Unit tests for the scheduled-tasks router.

Focuses on the authorization logic in the
``GET /executions/by-a2a-task/{a2a_task_id}`` endpoint which verifies
``task.created_by == user.get("id")``.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.scheduled_tasks import (
    get_execution_by_a2a_task_id,
    _check_task_ownership,
    preview_schedule,
    get_scheduler_status,
    get_scheduled_task,
    delete_scheduled_task,
    enable_scheduled_task,
    disable_scheduled_task,
    update_scheduled_task,
)
from solace_agent_mesh.gateway.http_sse.services.scheduled_task_service import ScheduledTaskService


def _mock_config_resolver(valid=True):
    """Build a mock config_resolver that passes scheduling permission."""
    resolver = MagicMock()
    resolver.validate_operation_config.return_value = {"valid": valid}
    return resolver


def _mock_execution(scheduled_task_id="task-1", a2a_task_id="a2a-123", **overrides):
    """Build a mock ScheduledTaskExecutionModel."""
    execution = MagicMock()
    execution.id = overrides.get("id", "exec-1")
    execution.scheduled_task_id = scheduled_task_id
    execution.a2a_task_id = a2a_task_id
    execution.status = overrides.get("status", "completed")
    execution.scheduled_for = 1700000000000
    execution.started_at = 1700000001000
    execution.completed_at = 1700000010000
    execution.result_summary = None
    execution.error_message = None
    execution.retry_count = 0
    execution.artifacts = None
    execution.notifications_sent = None
    return execution


def _mock_task(task_id="task-1", created_by="owner-user", **overrides):
    """Build a mock ScheduledTaskModel."""
    task = MagicMock()
    task.id = task_id
    task.created_by = created_by
    task.user_id = overrides.get("user_id", created_by)
    task.deleted_at = None
    return task


class TestGetExecutionByA2aTaskId:
    """Tests for the ``get_execution_by_a2a_task_id`` endpoint."""

    @pytest.mark.asyncio
    async def test_returns_execution_when_user_is_owner(self):
        """The endpoint returns the execution when the requesting user owns the parent task."""
        execution = _mock_execution()
        task = _mock_task(created_by="owner-user")

        mock_repo = MagicMock()
        mock_repo.find_execution_by_a2a_task_id.return_value = execution
        mock_repo.find_by_id.return_value = task

        user = {"id": "owner-user", "sub": "owner-user"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            result = await get_execution_by_a2a_task_id(
                a2a_task_id="a2a-123",
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
            )

        assert result.id == "exec-1"
        assert result.a2a_task_id == "a2a-123"

    @pytest.mark.asyncio
    async def test_returns_404_when_user_is_not_owner(self):
        """The endpoint returns 404 (not 403) when the requesting user does NOT own the parent task.

        This prevents confirming existence to unauthorized users.
        """
        execution = _mock_execution()
        task = _mock_task(created_by="owner-user")

        mock_repo = MagicMock()
        mock_repo.find_execution_by_a2a_task_id.return_value = execution
        mock_repo.find_by_id.return_value = task

        user = {"id": "other-user", "sub": "other-user"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_execution_by_a2a_task_id(
                    a2a_task_id="a2a-123",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_404_when_execution_not_found(self):
        """The endpoint returns 404 when no execution matches the A2A task ID."""
        mock_repo = MagicMock()
        mock_repo.find_execution_by_a2a_task_id.return_value = None

        user = {"id": "any-user", "sub": "any-user"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_execution_by_a2a_task_id(
                    a2a_task_id="nonexistent",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_parent_task_not_found(self):
        """The endpoint returns 404 when the parent task has been deleted."""
        execution = _mock_execution()

        mock_repo = MagicMock()
        mock_repo.find_execution_by_a2a_task_id.return_value = execution
        mock_repo.find_by_id.return_value = None  # task deleted

        user = {"id": "owner-user", "sub": "owner-user"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_execution_by_a2a_task_id(
                    a2a_task_id="a2a-123",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestCheckTaskOwnership
# ---------------------------------------------------------------------------


class TestCheckTaskOwnership:
    """Tests for the ``_check_task_ownership`` helper."""

    def test_no_exception_when_user_owns_task(self):
        """No exception is raised when user_id matches the task owner."""
        task = _mock_task(user_id="user-1")
        user = {"id": "user-1", "roles": []}
        # Should not raise
        _check_task_ownership(task, "user-1", user)

    def test_raises_403_when_user_does_not_own_task(self):
        """Raises 403 when the requesting user is not the task owner."""
        task = _mock_task(user_id="owner-user")
        user = {"id": "other-user", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            _check_task_ownership(task, "other-user", user)
        assert exc_info.value.status_code == 403

    def test_namespace_task_allowed_for_admin(self):
        """Admin users may access namespace-level tasks (user_id=None)."""
        task = _mock_task(user_id=None)
        task.user_id = None
        user = {"id": "admin-user", "roles": ["admin"]}
        # Should not raise
        _check_task_ownership(task, "admin-user", user)

    def test_namespace_task_forbidden_for_non_admin(self):
        """Non-admin users cannot access namespace-level tasks."""
        task = _mock_task(user_id=None)
        task.user_id = None
        user = {"id": "regular-user", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            _check_task_ownership(task, "regular-user", user)
        assert exc_info.value.status_code == 403
        assert "administrator" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# TestPreviewSchedule
# ---------------------------------------------------------------------------


class TestPreviewSchedule:
    """Tests for the ``preview_schedule`` endpoint."""

    @pytest.mark.asyncio
    async def test_returns_next_cron_execution_times(self):
        """Returns a list of next execution times for a cron expression."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            SchedulePreviewRequest,
        )

        request = SchedulePreviewRequest(
            schedule_type="cron",
            schedule_expression="0 9 * * *",
            timezone="UTC",
            count=3,
        )
        user = {"id": "user-1"}

        result = await preview_schedule(request=request, user=user)

        assert len(result.next_times) == 3
        assert result.schedule_type == "cron"

    @pytest.mark.asyncio
    async def test_returns_next_interval_execution_times(self):
        """Returns a list of next execution times for an interval expression."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            SchedulePreviewRequest,
        )

        request = SchedulePreviewRequest(
            schedule_type="interval",
            schedule_expression="30m",
            timezone="UTC",
            count=3,
        )
        user = {"id": "user-1"}

        result = await preview_schedule(request=request, user=user)

        assert len(result.next_times) == 3
        assert result.schedule_type == "interval"

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_cron_expression(self):
        """Returns 400 when the cron expression is invalid."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            SchedulePreviewRequest,
        )

        request = SchedulePreviewRequest(
            schedule_type="cron",
            schedule_expression="not-a-cron",
            timezone="UTC",
            count=3,
        )
        user = {"id": "user-1"}

        with pytest.raises(HTTPException) as exc_info:
            await preview_schedule(request=request, user=user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_unsupported_schedule_type(self):
        """Returns 400 when the schedule_type is not supported for preview."""
        # Build request manually to bypass pydantic validation
        request = MagicMock()
        request.schedule_type = "one_time"
        request.schedule_expression = "2025-01-01T00:00:00"
        request.timezone = "UTC"
        request.count = 3

        user = {"id": "user-1"}

        with pytest.raises(HTTPException) as exc_info:
            await preview_schedule(request=request, user=user)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# TestGetSchedulerStatus
# ---------------------------------------------------------------------------


class TestGetSchedulerStatus:
    """Tests for the ``get_scheduler_status`` endpoint."""

    @pytest.mark.asyncio
    async def test_returns_status_for_admin(self):
        """Admin users receive the scheduler status."""
        user = {"id": "admin-user", "roles": ["admin"]}
        mock_service = MagicMock()
        mock_service.get_status.return_value = {
            "instance_id": "inst-1",
            "namespace": "ns-1",
            "active_tasks_count": 2,
            "running_executions_count": 1,
            "scheduler_running": True,
            "pending_results_count": 0,
        }

        result = await get_scheduler_status(user=user, scheduler_service=mock_service)

        assert result.instance_id == "inst-1"
        assert result.namespace == "ns-1"
        assert result.active_tasks_count == 2
        assert result.running_executions_count == 1
        assert result.scheduler_running is True

    @pytest.mark.asyncio
    async def test_returns_403_for_non_admin(self):
        """Non-admin users are denied access to scheduler status."""
        user = {"id": "regular-user", "roles": []}
        mock_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_scheduler_status(user=user, scheduler_service=mock_service)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# TestGetScheduledTask
# ---------------------------------------------------------------------------


class TestGetScheduledTask:
    """Tests for the ``get_scheduled_task`` endpoint."""

    @pytest.mark.asyncio
    async def test_returns_task_when_user_owns_it(self):
        """Returns the task when the requesting user is the owner."""
        task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")
        task.name = "My Task"
        task.description = None
        task.namespace = "ns"
        task.schedule_type = "cron"
        task.schedule_expression = "0 9 * * *"
        task.timezone = "UTC"
        task.target_agent_name = "agent-1"
        task.target_type = "agent"
        task.task_message = []
        task.task_metadata = None
        task.enabled = True
        task.max_retries = 0
        task.retry_delay_seconds = 60
        task.timeout_seconds = 3600
        task.source = "ui"
        task.consecutive_failure_count = 0
        task.run_count = 5
        task.notification_config = None
        task.created_at = 1700000000000
        task.updated_at = 1700000000000
        task.next_run_at = None
        task.last_run_at = None

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task

        user = {"id": "user-1"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            result = await get_scheduled_task(
                task_id="task-1",
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
            )

        assert result.id == "task-1"

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self):
        """Returns 404 when the task does not exist."""
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        user = {"id": "user-1"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_scheduled_task(
                    task_id="nonexistent",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_user_id_does_not_match(self):
        """Returns 404 (not 403) when the requesting user is not the owner."""
        task = _mock_task(task_id="task-1", created_by="owner-user", user_id="owner-user")

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task

        user = {"id": "other-user"}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_scheduled_task(
                    task_id="task-1",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestDeleteScheduledTask
# ---------------------------------------------------------------------------


class TestDeleteScheduledTask:
    """Tests for the ``delete_scheduled_task`` endpoint."""

    @pytest.mark.asyncio
    async def test_soft_deletes_and_unschedules(self):
        """Soft-deletes the task and calls unschedule."""
        task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task
        mock_repo.soft_delete.return_value = True

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()
        mock_scheduler_service._unschedule_task = AsyncMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            await delete_scheduled_task(
                task_id="task-1",
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                user_config={},
                config_resolver=_mock_config_resolver(),
            )

        mock_repo.soft_delete.assert_called_once_with(mock_db, "task-1", "user-1")
        mock_db.commit.assert_called_once()
        mock_scheduler_service._unschedule_task.assert_awaited_once_with("task-1")

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self):
        """Returns 404 when the task does not exist."""
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_scheduled_task(
                    task_id="nonexistent",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                    user_config={},
                    config_resolver=_mock_config_resolver(),
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestEnableDisableTask
# ---------------------------------------------------------------------------


class TestEnableDisableTask:
    """Tests for ``enable_scheduled_task`` and ``disable_scheduled_task``."""

    @pytest.mark.asyncio
    async def test_enable_schedules_task(self):
        """Enabling a task calls _schedule_task on the scheduler service."""
        task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")
        enabled_task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task
        mock_repo.enable_task.return_value = enabled_task

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()
        mock_scheduler_service._schedule_task = AsyncMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            result = await enable_scheduled_task(
                task_id="task-1",
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                user_config={},
                config_resolver=_mock_config_resolver(),
            )

        assert result.success is True
        mock_repo.enable_task.assert_called_once_with(mock_db, "task-1")
        mock_scheduler_service._schedule_task.assert_awaited_once_with(enabled_task)

    @pytest.mark.asyncio
    async def test_disable_unschedules_task(self):
        """Disabling a task calls _unschedule_task on the scheduler service."""
        task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")
        disabled_task = _mock_task(task_id="task-1", created_by="user-1", user_id="user-1")

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task
        mock_repo.disable_task.return_value = disabled_task

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()
        mock_scheduler_service._unschedule_task = AsyncMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            result = await disable_scheduled_task(
                task_id="task-1",
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                user_config={},
                config_resolver=_mock_config_resolver(),
            )

        assert result.success is True
        mock_repo.disable_task.assert_called_once_with(mock_db, "task-1")
        mock_scheduler_service._unschedule_task.assert_awaited_once_with("task-1")

    @pytest.mark.asyncio
    async def test_enable_returns_404_for_missing_task(self):
        """Enable returns 404 when the task does not exist."""
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await enable_scheduled_task(
                    task_id="nonexistent",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                    user_config={},
                    config_resolver=_mock_config_resolver(),
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disable_returns_404_for_missing_task(self):
        """Disable returns 404 when the task does not exist."""
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await disable_scheduled_task(
                    task_id="nonexistent",
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                    user_config={},
                    config_resolver=_mock_config_resolver(),
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestConfigSourceUpdateRestriction
# ---------------------------------------------------------------------------


class TestConfigSourceUpdateRestriction:
    """Tests that non-enable/disable updates on config-sourced tasks return 403."""

    @pytest.mark.asyncio
    async def test_config_source_blocks_name_update(self):
        """Updating a field other than 'enabled' on a config-sourced task returns 403."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            UpdateScheduledTaskRequest,
        )

        task = _mock_task(task_id="task-cfg", created_by="user-1", user_id="user-1")
        task.source = "config"

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task

        request = UpdateScheduledTaskRequest(name="New Name")

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()
        mock_agent_registry = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_scheduled_task(
                    task_id="task-cfg",
                    request=request,
                    db=mock_db,
                    user=user,
                    task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                    user_config={},
                    config_resolver=_mock_config_resolver(),
                    agent_registry=mock_agent_registry,
                )

        assert exc_info.value.status_code == 403
        assert "config" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_config_source_allows_enable_update(self):
        """Updating only 'enabled' on a config-sourced task is allowed."""
        from solace_agent_mesh.gateway.http_sse.routers.dto.scheduled_task_dto import (
            UpdateScheduledTaskRequest,
        )

        task = _mock_task(task_id="task-cfg", created_by="user-1", user_id="user-1")
        task.source = "config"

        updated_task = _mock_task(task_id="task-cfg", created_by="user-1", user_id="user-1")
        updated_task.source = "config"
        updated_task.name = "My Task"
        updated_task.description = None
        updated_task.namespace = "ns"
        updated_task.schedule_type = "cron"
        updated_task.schedule_expression = "0 9 * * *"
        updated_task.timezone = "UTC"
        updated_task.target_agent_name = "agent-1"
        updated_task.target_type = "agent"
        updated_task.task_message = []
        updated_task.task_metadata = None
        updated_task.enabled = True
        updated_task.max_retries = 0
        updated_task.retry_delay_seconds = 60
        updated_task.timeout_seconds = 3600
        updated_task.consecutive_failure_count = 0
        updated_task.run_count = 0
        updated_task.notification_config = None
        updated_task.created_at = 1700000000000
        updated_task.updated_at = 1700000000000
        updated_task.next_run_at = None
        updated_task.last_run_at = None

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = task
        mock_repo.update_task.return_value = updated_task

        request = UpdateScheduledTaskRequest(enabled=True)

        user = {"id": "user-1", "roles": []}
        mock_db = MagicMock()
        mock_scheduler_service = MagicMock()
        mock_agent_registry = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.services.scheduled_task_service.ScheduledTaskRepository",
            return_value=mock_repo,
        ):
            result = await update_scheduled_task(
                task_id="task-cfg",
                request=request,
                db=mock_db,
                user=user,
                task_service=ScheduledTaskService(scheduler_service=mock_scheduler_service),
                user_config={},
                config_resolver=_mock_config_resolver(),
                agent_registry=mock_agent_registry,
            )

        assert result.id == "task-cfg"
