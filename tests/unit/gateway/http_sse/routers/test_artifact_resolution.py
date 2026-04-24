"""Unit tests for scheduled task artifact resolution helpers.

Tests cover:
- ``_is_execution_session`` — session ID classification
- ``_resolve_execution_context`` — combined storage session + artifact info lookup
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.gateway.http_sse.routers.artifacts import (
    _is_execution_session,
    _resolve_execution_context,
)

# Patch targets for the lazy imports inside _get_execution_from_db
_REPO_PATCH = "solace_agent_mesh.gateway.http_sse.repository.scheduled_task_repository.ScheduledTaskRepository"
_SESSION_LOCAL_PATCH = "solace_agent_mesh.gateway.http_sse.dependencies.SessionLocal"


@contextmanager
def _mock_execution_lookup(execution):
    """Patch the DB lookup to return a given execution object."""
    mock_repo = MagicMock()
    mock_repo.find_execution_by_session_id.return_value = execution

    mock_session = MagicMock()

    @contextmanager
    def session_factory():
        yield mock_session

    with patch(_REPO_PATCH, return_value=mock_repo), \
         patch(_SESSION_LOCAL_PATCH, session_factory):
        yield mock_repo


# ---------------------------------------------------------------------------
# _is_execution_session
# ---------------------------------------------------------------------------


class TestIsExecutionSession:
    """Session ID classification: scheduled_{execution_id} vs scheduled_task_{task_id}."""

    def test_execution_session(self):
        assert _is_execution_session("scheduled_abc123") is True

    def test_task_level_session(self):
        """scheduled_task_ prefix means stable storage session, NOT an execution."""
        assert _is_execution_session("scheduled_task_42") is False

    def test_regular_session(self):
        assert _is_execution_session("some-regular-session") is False

    def test_none(self):
        assert _is_execution_session(None) is False

    def test_empty_string(self):
        assert _is_execution_session("") is False

    def test_scheduled_prefix_only(self):
        """The bare prefix 'scheduled_' with content after it is an execution session."""
        assert _is_execution_session("scheduled_") is True

    def test_scheduled_task_prefix_only(self):
        assert _is_execution_session("scheduled_task_") is False


# ---------------------------------------------------------------------------
# _resolve_execution_context
# ---------------------------------------------------------------------------


class TestResolveExecutionContext:
    """Single-lookup resolution of storage session and artifact version info."""

    def test_non_execution_session_returns_none(self):
        """Non-execution sessions should short-circuit without a DB lookup."""
        stable, info = _resolve_execution_context("regular-session")
        assert stable is None
        assert info is None

    def test_maps_to_stable_session(self):
        """Execution sessions are mapped to scheduled_task_{task_id}."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-42"
        mock_execution.artifacts = None

        with _mock_execution_lookup(mock_execution):
            stable, info = _resolve_execution_context("scheduled_exec-1")

        assert stable == "scheduled_task_task-42"
        assert info is None

    def test_returns_artifact_version_mapping(self):
        """When execution has a produced_artifacts manifest, return name->version mapping."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-7"
        mock_execution.artifacts = [
            {"name": "report.pdf", "version": 3},
            {"name": "summary.txt", "version": 1},
        ]

        with _mock_execution_lookup(mock_execution):
            stable, info = _resolve_execution_context("scheduled_exec-2")

        assert stable == "scheduled_task_task-7"
        assert info == {"report.pdf": 3, "summary.txt": 1}

    def test_artifact_with_filename_key(self):
        """Artifacts using 'filename' instead of 'name' are also recognized."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-9"
        mock_execution.artifacts = [{"filename": "data.csv", "version": 2}]

        with _mock_execution_lookup(mock_execution):
            _, info = _resolve_execution_context("scheduled_exec-3")

        assert info == {"data.csv": 2}

    def test_artifact_with_no_version(self):
        """Artifacts without a version key map to None."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-5"
        mock_execution.artifacts = [{"name": "output.txt"}]

        with _mock_execution_lookup(mock_execution):
            _, info = _resolve_execution_context("scheduled_exec-4")

        assert info == {"output.txt": None}

    def test_empty_artifacts_list_returns_none(self):
        """An empty artifacts list should return None for artifact info."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-1"
        mock_execution.artifacts = []

        with _mock_execution_lookup(mock_execution):
            stable, info = _resolve_execution_context("scheduled_exec-5")

        assert stable == "scheduled_task_task-1"
        assert info is None

    def test_malformed_artifact_entries_skipped(self):
        """Non-dict entries and entries without name/filename are skipped."""
        mock_execution = MagicMock()
        mock_execution.scheduled_task_id = "task-1"
        mock_execution.artifacts = [
            "not-a-dict",
            {"irrelevant_key": "value"},
            {"name": "good.txt", "version": 1},
        ]

        with _mock_execution_lookup(mock_execution):
            _, info = _resolve_execution_context("scheduled_exec-6")

        assert info == {"good.txt": 1}

    def test_db_lookup_failure_returns_none(self):
        """If the DB lookup raises, return (None, None) gracefully."""
        with patch(_REPO_PATCH, side_effect=Exception("DB down")), \
             patch(_SESSION_LOCAL_PATCH, MagicMock()):
            stable, info = _resolve_execution_context("scheduled_exec-fail")

        assert stable is None
        assert info is None

    def test_execution_not_found_returns_none(self):
        """If the execution record doesn't exist, return (None, None)."""
        with _mock_execution_lookup(None):
            stable, info = _resolve_execution_context("scheduled_exec-missing")

        assert stable is None
        assert info is None

    def test_no_session_local_returns_none(self):
        """If SessionLocal is None (no DB configured), return (None, None)."""
        with patch(_SESSION_LOCAL_PATCH, None):
            stable, info = _resolve_execution_context("scheduled_exec-nodb")

        assert stable is None
        assert info is None
