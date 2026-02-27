#!/usr/bin/env python3
"""
Tests for _check_project_has_bm25_index in the tasks router.

Uses the real in-memory artifact service to verify actual behavior
rather than mocking the artifact service interface.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from google.genai import types as adk_types

from sam_test_infrastructure.artifact_service.service import TestInMemoryArtifactService
from src.solace_agent_mesh.agent.utils.artifact_helpers import BM25_INDEX_FILENAME
from src.solace_agent_mesh.gateway.http_sse.routers.tasks import (
    _check_project_has_bm25_index,
)


@pytest.fixture
def artifact_service():
    return TestInMemoryArtifactService()


@pytest.fixture
def project():
    p = Mock()
    p.id = "test-project-123"
    p.user_id = "owner-user-456"
    return p


@pytest.fixture
def project_service():
    svc = Mock()
    svc.app_name = "test-app"
    return svc


@pytest.fixture
def component(artifact_service):
    comp = Mock()
    comp.get_shared_artifact_service.return_value = artifact_service
    return comp


@pytest.mark.asyncio
async def test_returns_false_when_no_index_exists(
    project, project_service, component
):
    """No BM25 index artifact has been saved — should return False."""
    result = await _check_project_has_bm25_index(
        project=project,
        project_service=project_service,
        component=component,
        log_prefix="[Test] ",
    )
    assert result is False


@pytest.mark.asyncio
async def test_returns_true_when_index_exists(
    project, project_service, component, artifact_service
):
    """BM25 index artifact exists — should return True."""
    # Save a real artifact into the in-memory service
    await artifact_service.save_artifact(
        app_name=project_service.app_name,
        user_id=project.user_id,
        session_id=f"project-{project.id}",
        filename=BM25_INDEX_FILENAME,
        artifact=adk_types.Part(
            inline_data=adk_types.Blob(data=b"fake-index-zip", mime_type="application/zip")
        ),
    )

    result = await _check_project_has_bm25_index(
        project=project,
        project_service=project_service,
        component=component,
        log_prefix="[Test] ",
    )
    assert result is True


@pytest.mark.asyncio
async def test_returns_false_when_no_artifact_service(
    project, project_service
):
    """No artifact service configured — should return False."""
    comp = Mock()
    comp.get_shared_artifact_service.return_value = None

    result = await _check_project_has_bm25_index(
        project=project,
        project_service=project_service,
        component=comp,
        log_prefix="[Test] ",
    )
    assert result is False


@pytest.mark.asyncio
async def test_returns_true_on_artifact_service_error(
    project, project_service
):
    """Artifact service raises an exception — should return True (permissive fallback)."""
    broken_service = Mock()
    broken_service.list_versions = AsyncMock(side_effect=RuntimeError("S3 unavailable"))

    comp = Mock()
    comp.get_shared_artifact_service.return_value = broken_service

    result = await _check_project_has_bm25_index(
        project=project,
        project_service=project_service,
        component=comp,
        log_prefix="[Test] ",
    )
    assert result is True
