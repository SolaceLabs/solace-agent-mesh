"""DB-level tests for the router's per-task latest-execution helpers.

These exercise ``_fetch_last_and_completed_executions`` against a real
SQLite session because the helper uses a SQL CASE-filtered MAX subquery and
an OR-disjunction join — the kind of thing a pure mock test can't validate.

Coverage:
- A task with only in-flight (running/pending) executions has a "last" but
  no "last_completed".
- A task with both completed and running executions returns the running row
  as "last" (newest scheduled_for) and the completed row as "last_completed".
- Multiple tasks are partitioned correctly in one round-trip.
- Empty task_ids short-circuits to two empty maps.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models.base import Base
from solace_agent_mesh.gateway.http_sse.repository.models.scheduled_task_model import (
    ExecutionStatus,
    ScheduledTaskExecutionModel,
    ScheduledTaskModel,
    ScheduleType,
)
from solace_agent_mesh.gateway.http_sse.routers.scheduled_tasks import (
    _fetch_last_and_completed_executions,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


def _make_task(session, *, task_id=None, name="t") -> ScheduledTaskModel:
    task = ScheduledTaskModel(
        id=task_id or str(uuid.uuid4()),
        name=name,
        namespace="ns1",
        user_id="user-1",
        created_by="user-1",
        schedule_type=ScheduleType.CRON,
        schedule_expression="0 9 * * *",
        timezone="UTC",
        target_agent_name="agent-a",
        target_type="agent",
        task_message=[{"type": "text", "text": "hi"}],
        enabled=True,
        max_retries=0,
        retry_delay_seconds=60,
        timeout_seconds=3600,
        source="ui",
        consecutive_failure_count=0,
        run_count=0,
    )
    session.add(task)
    session.flush()
    return task


def _make_exec(
    session,
    task_id,
    *,
    status,
    scheduled_for,
    started_at=None,
    exec_id=None,
):
    ex = ScheduledTaskExecutionModel(
        id=exec_id or str(uuid.uuid4()),
        scheduled_task_id=task_id,
        status=status,
        scheduled_for=scheduled_for,
        started_at=started_at,
    )
    session.add(ex)
    session.flush()
    return ex


class TestFetchLastAndCompletedExecutions:
    def test_empty_task_ids_returns_empty_maps(self, session):
        last, completed = _fetch_last_and_completed_executions(session, [])
        assert last == {}
        assert completed == {}

    def test_running_only_task_has_no_completed(self, session):
        task = _make_task(session)
        running = _make_exec(
            session,
            task.id,
            status=ExecutionStatus.RUNNING,
            scheduled_for=1700,
            started_at=1701,
        )

        last, completed = _fetch_last_and_completed_executions(session, [task.id])
        assert task.id in last
        assert last[task.id].id == running.id
        assert task.id not in completed

    def test_running_after_completed_returns_both_correctly(self, session):
        """The canonical case the reviewer flagged: a task with a completed
        execution and a *newer* running execution should expose both — the
        running one as "last" and the completed one as "last_completed".
        Previously two separate queries did this; this test pins the
        single-query equivalent."""
        task = _make_task(session)
        completed_row = _make_exec(
            session,
            task.id,
            status=ExecutionStatus.COMPLETED,
            scheduled_for=1000,
            started_at=1001,
        )
        running_row = _make_exec(
            session,
            task.id,
            status=ExecutionStatus.RUNNING,
            scheduled_for=2000,
            started_at=2001,
        )

        last, completed = _fetch_last_and_completed_executions(session, [task.id])
        assert last[task.id].id == running_row.id
        assert completed[task.id].id == completed_row.id

    def test_failed_counts_as_terminal(self, session):
        """FAILED, TIMEOUT, CANCELLED, SKIPPED are all treated as terminal."""
        task = _make_task(session)
        failed_row = _make_exec(
            session,
            task.id,
            status=ExecutionStatus.FAILED,
            scheduled_for=1000,
            started_at=1001,
        )

        last, completed = _fetch_last_and_completed_executions(session, [task.id])
        assert last[task.id].id == failed_row.id
        assert completed[task.id].id == failed_row.id

    def test_multiple_tasks_partitioned_correctly(self, session):
        """Two tasks with different histories must not bleed into each other."""
        task_a = _make_task(session, name="a")
        task_b = _make_task(session, name="b")

        a_completed = _make_exec(
            session,
            task_a.id,
            status=ExecutionStatus.COMPLETED,
            scheduled_for=100,
            started_at=101,
        )
        _make_exec(
            session,
            task_b.id,
            status=ExecutionStatus.RUNNING,
            scheduled_for=200,
            started_at=201,
        )

        last, completed = _fetch_last_and_completed_executions(
            session, [task_a.id, task_b.id]
        )
        assert last[task_a.id].id == a_completed.id
        assert completed[task_a.id].id == a_completed.id
        # task_b has only a running execution — present in last, absent in completed
        assert task_b.id in last
        assert task_b.id not in completed
