"""Unit tests for the get_scheduled_task_artifact endpoint."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from solace_agent_mesh.gateway.http_sse.routers.artifacts import (
    get_scheduled_task_artifact,
)

log = logging.getLogger(__name__)


def _make_component(namespace="test-ns"):
    component = MagicMock()
    component.get_namespace.return_value = namespace
    component.get_config.return_value = "TestApp"
    return component


def _make_task(created_by, namespace="test-ns"):
    task = MagicMock()
    task.created_by = created_by
    task.namespace = namespace
    return task


def _make_execution(scheduled_task_id="task-1"):
    execution = MagicMock()
    execution.scheduled_task_id = scheduled_task_id
    return execution


@pytest.mark.asyncio
async def test_non_owner_gets_404():
    """A user who does not own the task should receive a 404 response."""
    execution = _make_execution()
    task = _make_task(created_by="other-user")

    mock_repo = MagicMock()
    mock_repo.find_execution_by_session_id.return_value = execution
    mock_repo.find_by_id.return_value = task

    with patch(
        "solace_agent_mesh.gateway.http_sse.repository.scheduled_task_repository.ScheduledTaskRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_scheduled_task_artifact(
                session_id="scheduled_abc",
                filename="report.pdf",
                download=False,
                artifact_service=MagicMock(),
                user_id="requesting-user",
                component=_make_component(),
                user_config={},
                db=MagicMock(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Artifact not found."


@pytest.mark.asyncio
async def test_path_traversal_rejected():
    """A filename containing path traversal sequences should be rejected with 400."""
    with pytest.raises(HTTPException) as exc_info:
        await get_scheduled_task_artifact(
            session_id="scheduled_abc",
            filename="../etc/passwd",
            download=False,
            artifact_service=MagicMock(),
            user_id="user-1",
            component=_make_component(),
            user_config={},
            db=MagicMock(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid artifact filename."


@pytest.mark.asyncio
async def test_valid_owner_gets_streaming_response():
    """A valid owner should receive a streaming response with the artifact data."""
    execution = _make_execution()
    task = _make_task(created_by="user-1")

    mock_repo = MagicMock()
    mock_repo.find_execution_by_session_id.return_value = execution
    mock_repo.find_by_id.return_value = task

    inline_data = MagicMock()
    inline_data.data = b"file-content"
    inline_data.mime_type = "application/pdf"

    artifact_part = MagicMock()
    artifact_part.inline_data = inline_data

    mock_artifact_service = AsyncMock()
    mock_artifact_service.load_artifact.return_value = artifact_part

    with patch(
        "solace_agent_mesh.gateway.http_sse.repository.scheduled_task_repository.ScheduledTaskRepository",
        return_value=mock_repo,
    ):
        response = await get_scheduled_task_artifact(
            session_id="scheduled_abc",
            filename="report.pdf",
            download=False,
            artifact_service=mock_artifact_service,
            user_id="user-1",
            component=_make_component(),
            user_config={},
            db=MagicMock(),
        )

    assert response.media_type == "application/pdf"
    body = b"".join([chunk async for chunk in response.body_iterator])
    assert body == b"file-content"
    mock_artifact_service.load_artifact.assert_awaited_once()
