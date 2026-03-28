"""Unit tests for ScheduledTaskRepository using SQLite in-memory database.

Tests cover:
- create_task uniqueness check
- find_by_id with user_id filtering
- soft_delete behaviour
- find_execution_by_session_id parsing ``scheduled_{execution_id}`` pattern
- find_execution_by_a2a_task_id
- pagination on find_by_namespace / find_executions_by_task
- delete_oldest_executions (execution history bounds)
- enable_task / disable_task state transitions
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models.base import Base
from solace_agent_mesh.gateway.http_sse.repository.models.scheduled_task_model import (
    ExecutionStatus,
    ScheduledTaskExecutionModel,
    ScheduledTaskModel,
    ScheduleType,
)
from solace_agent_mesh.gateway.http_sse.repository.scheduled_task_repository import (
    ScheduledTaskRepository,
)
from solace_agent_mesh.gateway.http_sse.shared.pagination import PaginationParams


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine with all tables."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Provide a transactional DB session that rolls back after each test."""
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture()
def repo():
    return ScheduledTaskRepository()


def _make_task_data(**overrides) -> dict:
    """Helper to build a valid task_data dict."""
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "test-task",
        "namespace": "ns1",
        "user_id": "user-1",
        "created_by": "user-1",
        "schedule_type": ScheduleType.CRON,
        "schedule_expression": "*/5 * * * *",
        "timezone": "UTC",
        "target_agent_name": "agent-a",
        "target_type": "agent",
        "task_message": [{"type": "text", "text": "hello"}],
        "enabled": True,
        "max_retries": 0,
        "retry_delay_seconds": 60,
        "timeout_seconds": 3600,
        "source": "ui",
        "consecutive_failure_count": 0,
        "run_count": 0,
    }
    defaults.update(overrides)
    return defaults


def _make_execution_data(task_id: str, **overrides) -> dict:
    """Helper to build a valid execution_data dict."""
    defaults = {
        "id": str(uuid.uuid4()),
        "scheduled_task_id": task_id,
        "status": ExecutionStatus.PENDING,
        "scheduled_for": 1700000000000,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# create_task
# ===========================================================================

class TestCreateTask:
    """Tests for ScheduledTaskRepository.create_task."""

    def test_create_task_success(self, repo, session):
        """A new task is persisted and returned."""
        data = _make_task_data()
        task = repo.create_task(session, data)

        assert task.id == data["id"]
        assert task.name == "test-task"
        assert task.namespace == "ns1"

    def test_create_task_uniqueness_check(self, repo, session):
        """Creating a second active task with the same (namespace, name) raises ValueError."""
        data1 = _make_task_data(name="unique-name", namespace="ns1")
        repo.create_task(session, data1)
        session.flush()

        data2 = _make_task_data(name="unique-name", namespace="ns1")
        with pytest.raises(ValueError, match="already exists"):
            repo.create_task(session, data2)

    def test_create_task_allows_same_name_after_soft_delete(self, repo, session):
        """A soft-deleted task does not block creation of a new task with the same name."""
        data1 = _make_task_data(name="reusable", namespace="ns1")
        task1 = repo.create_task(session, data1)
        session.flush()

        repo.soft_delete(session, task1.id, "user-1")
        session.flush()

        data2 = _make_task_data(name="reusable", namespace="ns1")
        task2 = repo.create_task(session, data2)
        assert task2.id != task1.id

    def test_create_task_allows_same_name_different_namespace(self, repo, session):
        """Same name in different namespaces is allowed."""
        data1 = _make_task_data(name="shared-name", namespace="ns-a")
        repo.create_task(session, data1)
        session.flush()

        data2 = _make_task_data(name="shared-name", namespace="ns-b")
        task2 = repo.create_task(session, data2)
        assert task2.name == "shared-name"


# ===========================================================================
# find_by_id
# ===========================================================================

class TestFindById:
    """Tests for ScheduledTaskRepository.find_by_id."""

    def test_find_by_id_returns_task(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()

        found = repo.find_by_id(session, data["id"])
        assert found is not None
        assert found.id == data["id"]

    def test_find_by_id_returns_none_for_missing(self, repo, session):
        assert repo.find_by_id(session, "nonexistent") is None

    def test_find_by_id_excludes_soft_deleted(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()
        repo.soft_delete(session, data["id"], "user-1")
        session.flush()

        assert repo.find_by_id(session, data["id"]) is None

    def test_find_by_id_with_user_id_filters_correctly(self, repo, session):
        """When user_id is provided, only tasks owned by that user or namespace-level (user_id=None) are returned."""
        # User-level task for user-1
        data_user1 = _make_task_data(user_id="user-1")
        repo.create_task(session, data_user1)

        # Namespace-level task (user_id=None)
        data_ns = _make_task_data(name="ns-task", user_id=None)
        repo.create_task(session, data_ns)
        session.flush()

        # user-1 can see their own task
        assert repo.find_by_id(session, data_user1["id"], user_id="user-1") is not None
        # user-1 can see namespace-level task
        assert repo.find_by_id(session, data_ns["id"], user_id="user-1") is not None
        # user-2 cannot see user-1's task
        assert repo.find_by_id(session, data_user1["id"], user_id="user-2") is None
        # user-2 can see namespace-level task
        assert repo.find_by_id(session, data_ns["id"], user_id="user-2") is not None


# ===========================================================================
# soft_delete
# ===========================================================================

class TestSoftDelete:
    """Tests for ScheduledTaskRepository.soft_delete."""

    def test_soft_delete_marks_task(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()

        result = repo.soft_delete(session, data["id"], "deleter")
        assert result is True

        # Verify the raw row
        raw = session.get(ScheduledTaskModel, data["id"])
        assert raw.deleted_at is not None
        assert raw.deleted_by == "deleter"
        assert raw.enabled is False

    def test_soft_delete_returns_false_for_missing(self, repo, session):
        assert repo.soft_delete(session, "nonexistent", "user") is False

    def test_soft_delete_returns_false_for_already_deleted(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()

        repo.soft_delete(session, data["id"], "user")
        session.flush()

        assert repo.soft_delete(session, data["id"], "user") is False


# ===========================================================================
# find_execution_by_session_id
# ===========================================================================

class TestFindExecutionBySessionId:
    """Tests for ScheduledTaskRepository.find_execution_by_session_id."""

    def test_parses_scheduled_prefix(self, repo, session):
        """Session IDs matching ``scheduled_{execution_id}`` resolve to the execution."""
        task_data = _make_task_data()
        repo.create_task(session, task_data)
        session.flush()

        exec_id = str(uuid.uuid4())
        exec_data = _make_execution_data(task_data["id"], id=exec_id)
        repo.create_execution(session, exec_data)
        session.flush()

        found = repo.find_execution_by_session_id(session, f"scheduled_{exec_id}")
        assert found is not None
        assert found.id == exec_id

    def test_returns_none_for_non_scheduled_prefix(self, repo, session):
        """Session IDs that don't start with ``scheduled_`` return None."""
        assert repo.find_execution_by_session_id(session, "random-session-id") is None

    def test_returns_none_for_unknown_execution_id(self, repo, session):
        """A well-formed session ID with a non-existent execution ID returns None."""
        assert repo.find_execution_by_session_id(session, "scheduled_nonexistent") is None


# ===========================================================================
# find_execution_by_a2a_task_id
# ===========================================================================

class TestFindExecutionByA2aTaskId:
    """Tests for ScheduledTaskRepository.find_execution_by_a2a_task_id."""

    def test_finds_execution_by_a2a_task_id(self, repo, session):
        task_data = _make_task_data()
        repo.create_task(session, task_data)
        session.flush()

        a2a_id = f"task-{uuid.uuid4().hex}"
        exec_data = _make_execution_data(task_data["id"], a2a_task_id=a2a_id)
        repo.create_execution(session, exec_data)
        session.flush()

        found = repo.find_execution_by_a2a_task_id(session, a2a_id)
        assert found is not None
        assert found.a2a_task_id == a2a_id

    def test_returns_none_for_unknown_a2a_task_id(self, repo, session):
        assert repo.find_execution_by_a2a_task_id(session, "task-unknown") is None


# ===========================================================================
# Pagination
# ===========================================================================

class TestPagination:
    """Tests for paginated queries."""

    def test_find_by_namespace_pagination(self, repo, session):
        """Pagination limits results correctly."""
        for i in range(5):
            data = _make_task_data(name=f"task-{i}", user_id="user-1")
            repo.create_task(session, data)
        session.flush()

        page1 = PaginationParams(page_number=1, page_size=2)
        results = repo.find_by_namespace(session, "ns1", user_id="user-1", pagination=page1)
        assert len(results) == 2

        page2 = PaginationParams(page_number=2, page_size=2)
        results2 = repo.find_by_namespace(session, "ns1", user_id="user-1", pagination=page2)
        assert len(results2) == 2

        page3 = PaginationParams(page_number=3, page_size=2)
        results3 = repo.find_by_namespace(session, "ns1", user_id="user-1", pagination=page3)
        assert len(results3) == 1

    def test_count_by_namespace(self, repo, session):
        for i in range(3):
            data = _make_task_data(name=f"task-{i}", user_id="user-1")
            repo.create_task(session, data)
        session.flush()

        count = repo.count_by_namespace(session, "ns1", user_id="user-1")
        assert count == 3

    def test_find_by_namespace_enabled_only(self, repo, session):
        data_enabled = _make_task_data(name="enabled", enabled=True, user_id="user-1")
        data_disabled = _make_task_data(name="disabled", enabled=False, user_id="user-1")
        repo.create_task(session, data_enabled)
        repo.create_task(session, data_disabled)
        session.flush()

        results = repo.find_by_namespace(session, "ns1", user_id="user-1", enabled_only=True)
        assert len(results) == 1
        assert results[0].name == "enabled"

    def test_find_executions_by_task_pagination(self, repo, session):
        task_data = _make_task_data()
        repo.create_task(session, task_data)
        session.flush()

        for i in range(5):
            exec_data = _make_execution_data(
                task_data["id"],
                scheduled_for=1700000000000 + i * 1000,
            )
            repo.create_execution(session, exec_data)
        session.flush()

        page = PaginationParams(page_number=1, page_size=3)
        results = repo.find_executions_by_task(session, task_data["id"], pagination=page)
        assert len(results) == 3

        total = repo.count_executions_by_task(session, task_data["id"])
        assert total == 5


# ===========================================================================
# delete_oldest_executions (execution history bounds)
# ===========================================================================

class TestDeleteOldestExecutions:
    """Tests for ScheduledTaskRepository.delete_oldest_executions."""

    def test_keeps_only_specified_count(self, repo, session):
        task_data = _make_task_data()
        repo.create_task(session, task_data)
        session.flush()

        for i in range(10):
            exec_data = _make_execution_data(
                task_data["id"],
                scheduled_for=1700000000000 + i * 1000,
            )
            repo.create_execution(session, exec_data)
        session.flush()

        deleted = repo.delete_oldest_executions(session, task_data["id"], keep_count=3)
        assert deleted == 7

        remaining = repo.count_executions_by_task(session, task_data["id"])
        assert remaining == 3

    def test_no_deletion_when_under_limit(self, repo, session):
        task_data = _make_task_data()
        repo.create_task(session, task_data)
        session.flush()

        for i in range(2):
            exec_data = _make_execution_data(
                task_data["id"],
                scheduled_for=1700000000000 + i * 1000,
            )
            repo.create_execution(session, exec_data)
        session.flush()

        deleted = repo.delete_oldest_executions(session, task_data["id"], keep_count=5)
        assert deleted == 0


# ===========================================================================
# enable_task / disable_task
# ===========================================================================

class TestEnableDisableTask:
    """Tests for enable_task and disable_task state transitions."""

    def test_enable_task_sets_enabled(self, repo, session):
        data = _make_task_data(enabled=False)
        repo.create_task(session, data)
        session.flush()

        task = repo.enable_task(session, data["id"])
        assert task is not None
        assert task.enabled is True

    def test_disable_task_sets_disabled(self, repo, session):
        data = _make_task_data(enabled=True)
        repo.create_task(session, data)
        session.flush()

        task = repo.disable_task(session, data["id"])
        assert task is not None
        assert task.enabled is False

    def test_enable_returns_none_for_deleted_task(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()
        repo.soft_delete(session, data["id"], "user")
        session.flush()

        assert repo.enable_task(session, data["id"]) is None

    def test_disable_returns_none_for_missing_task(self, repo, session):
        assert repo.disable_task(session, "nonexistent") is None


# ===========================================================================
# update_task
# ===========================================================================

class TestUpdateTask:
    """Tests for ScheduledTaskRepository.update_task."""

    def test_update_task_changes_fields(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()

        updated = repo.update_task(session, data["id"], {"name": "new-name", "max_retries": 3})
        assert updated is not None
        assert updated.name == "new-name"
        assert updated.max_retries == 3

    def test_update_task_returns_none_for_deleted(self, repo, session):
        data = _make_task_data()
        repo.create_task(session, data)
        session.flush()
        repo.soft_delete(session, data["id"], "user")
        session.flush()

        assert repo.update_task(session, data["id"], {"name": "x"}) is None

    def test_update_task_returns_none_for_missing(self, repo, session):
        assert repo.update_task(session, "nonexistent", {"name": "x"}) is None
