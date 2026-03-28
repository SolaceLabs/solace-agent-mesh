"""Unit tests for scheduled-tasks router RBAC logic.

Tests cover:
- Namespace-level task restriction (non-admin blocked)
- Target agent validation and authorization
- _validate_scheduling_permission gating
"""

import uuid
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.scheduled_tasks import (
    create_scheduled_task,
    _validate_scheduling_permission,
)


# ---------------------------------------------------------------------------
# _validate_scheduling_permission
# ---------------------------------------------------------------------------

class TestValidateSchedulingPermission:
    """Tests for the _validate_scheduling_permission helper."""

    def test_raises_403_when_not_valid(self):
        user_config = {}
        config_resolver = MagicMock()
        config_resolver.validate_operation_config.return_value = {"valid": False}
        with pytest.raises(HTTPException) as exc_info:
            _validate_scheduling_permission(user_config, config_resolver)
        assert exc_info.value.status_code == 403

    def test_passes_when_valid(self):
        user_config = {}
        config_resolver = MagicMock()
        config_resolver.validate_operation_config.return_value = {"valid": True}
        _validate_scheduling_permission(user_config, config_resolver)


# ---------------------------------------------------------------------------
# create_scheduled_task – namespace-level restriction
# ---------------------------------------------------------------------------

class TestCreateTaskNamespaceRestriction:
    """Non-admin users cannot create namespace-level tasks."""

    @pytest.mark.asyncio
    async def test_non_admin_blocked_for_namespace_task(self):
        request = MagicMock()
        request.user_level = False  # namespace-level
        request.name = "ns-task"
        user = {"id": "user-1", "roles": ["viewer"]}
        user_config = {}
        config_resolver = MagicMock()
        config_resolver.validate_operation_config.return_value = {"valid": True}

        with pytest.raises(HTTPException) as exc_info:
            await create_scheduled_task(
                request=request,
                db=MagicMock(),
                user=user,
                scheduler_service=MagicMock(),
                user_config=user_config,
                config_resolver=config_resolver,
                agent_registry=MagicMock(),
            )
        assert exc_info.value.status_code == 403
        assert "administrators" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_allowed_for_namespace_task(self):
        request = MagicMock()
        request.user_level = False
        request.name = "ns-task"
        request.target_agent_name = None
        request.description = "d"
        request.schedule_type = "cron"
        request.schedule_expression = "0 9 * * *"
        request.timezone = "UTC"
        request.target_type = "agent"
        request.task_message = []
        request.task_metadata = None
        request.enabled = True
        request.max_retries = 0
        request.retry_delay_seconds = 60
        request.timeout_seconds = 3600
        request.notification_config = None

        user = {"id": "admin-1", "roles": ["admin"]}
        user_config = {}
        config_resolver = MagicMock()
        config_resolver.validate_operation_config.return_value = {"valid": True}
        scheduler_service = MagicMock()
        scheduler_service.namespace = "default"
        scheduler_service._schedule_task = AsyncMock()

        mock_repo = MagicMock()
        mock_task = MagicMock()
        mock_task.enabled = True
        mock_repo.create_task.return_value = mock_task
        mock_db = MagicMock()

        with patch(
            "solace_agent_mesh.gateway.http_sse.routers.scheduled_tasks.ScheduledTaskRepository",
            return_value=mock_repo,
        ), patch(
            "solace_agent_mesh.gateway.http_sse.routers.scheduled_tasks.ScheduledTaskResponse"
        ) as mock_response_cls:
            mock_response_cls.from_orm.return_value = MagicMock()
            await create_scheduled_task(
                request=request,
                db=mock_db,
                user=user,
                scheduler_service=scheduler_service,
                user_config=user_config,
                config_resolver=config_resolver,
                agent_registry=MagicMock(),
            )
            mock_repo.create_task.assert_called_once()


# ---------------------------------------------------------------------------
# create_scheduled_task – target agent RBAC
# ---------------------------------------------------------------------------

class TestCreateTaskAgentRBAC:
    """Target agent access is validated via config_resolver."""

    @pytest.mark.asyncio
    async def test_unknown_agent_returns_404(self):
        request = MagicMock()
        request.user_level = True
        request.target_agent_name = "nonexistent-agent"

        user = {"id": "user-1", "roles": []}
        user_config = {}
        config_resolver = MagicMock()
        config_resolver.validate_operation_config.return_value = {"valid": True}
        agent_registry = MagicMock()
        agent_registry.get_agent.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await create_scheduled_task(
                request=request,
                db=MagicMock(),
                user=user,
                scheduler_service=MagicMock(),
                user_config=user_config,
                config_resolver=config_resolver,
                agent_registry=agent_registry,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_agent_returns_403(self):
        request = MagicMock()
        request.user_level = True
        request.target_agent_name = "restricted-agent"

        user = {"id": "user-1", "roles": []}
        user_config = {}
        config_resolver = MagicMock()
        # First call: scheduling permission passes; second call: agent access fails
        config_resolver.validate_operation_config.side_effect = [
            {"valid": True},
            {"valid": False},
        ]
        agent_registry = MagicMock()
        agent_registry.get_agent.return_value = MagicMock()  # agent exists

        with pytest.raises(HTTPException) as exc_info:
            await create_scheduled_task(
                request=request,
                db=MagicMock(),
                user=user,
                scheduler_service=MagicMock(),
                user_config=user_config,
                config_resolver=config_resolver,
                agent_registry=agent_registry,
            )
        assert exc_info.value.status_code == 403
        assert "restricted-agent" in exc_info.value.detail
