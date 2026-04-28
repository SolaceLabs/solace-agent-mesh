"""
Tests for SessionService._find_sessions_with_running_background_tasks.

Covers the SQL-side filtering semantics introduced when the unbounded
find_background_tasks_by_status scan was replaced with a scoped join: a
running task must surface, a task with terminal task_metadata must not, a
foreground task must not, and tasks belonging to other users must not.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models.base import Base
from solace_agent_mesh.gateway.http_sse.repository.models.chat_task_model import (
    ChatTaskModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.project_model import (
    ProjectModel,  # register FK target for SessionModel.project_id
)  # noqa: F401
from solace_agent_mesh.gateway.http_sse.repository.models.session_model import (
    SessionModel,
)
from solace_agent_mesh.gateway.http_sse.repository.models.task_model import TaskModel
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService


USER_ID = "user-1"
OTHER_USER_ID = "user-2"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.rollback()
    sess.close()


@pytest.fixture()
def service():
    return SessionService()


def _make_session(db: DBSession, session_id: str, user_id: str = USER_ID) -> None:
    db.add(
        SessionModel(
            id=session_id,
            name=session_id,
            user_id=user_id,
            source="chat",
            created_time=1700000000000,
            updated_time=1700000000000,
        )
    )


def _make_task(
    db: DBSession,
    task_id: str,
    session_id: str,
    *,
    user_id: str = USER_ID,
    execution_mode: str = "background",
    end_time: int | None = None,
    status: str | None = None,
    metadata_status: str | None = None,
) -> None:
    db.add(
        TaskModel(
            id=task_id,
            user_id=user_id,
            start_time=1700000000000,
            end_time=end_time,
            status=status,
            execution_mode=execution_mode,
        )
    )
    chat_metadata = (
        json.dumps({"status": metadata_status}) if metadata_status else None
    )
    db.add(
        ChatTaskModel(
            id=task_id,
            session_id=session_id,
            user_id=user_id,
            message_bubbles="[]",
            task_metadata=chat_metadata,
            created_time=1700000000000,
        )
    )


class TestFindSessionsWithRunningBackgroundTasks:
    def test_running_background_task_surfaces(self, session, service):
        _make_session(session, "s-running")
        _make_task(session, "t-running", "s-running", status="running")
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-running"]
        )
        assert result == {"s-running"}

    def test_task_with_terminal_metadata_is_excluded(self, session, service):
        # TaskModel still says "running" but the chat_tasks metadata was already
        # marked completed — the filter must respect that.
        _make_session(session, "s-done")
        _make_task(
            session,
            "t-done",
            "s-done",
            status="running",
            metadata_status="completed",
        )
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-done"]
        )
        assert result == set()

    def test_foreground_task_is_excluded(self, session, service):
        _make_session(session, "s-foreground")
        _make_task(
            session,
            "t-foreground",
            "s-foreground",
            execution_mode="foreground",
            status="running",
        )
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-foreground"]
        )
        assert result == set()

    def test_completed_task_with_end_time_is_excluded(self, session, service):
        _make_session(session, "s-finished")
        _make_task(
            session,
            "t-finished",
            "s-finished",
            status="completed",
            end_time=1700000005000,
        )
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-finished"]
        )
        assert result == set()

    def test_other_users_task_does_not_leak(self, session, service):
        # Other user has a running background task in their own session — it
        # must never surface even when the requested session_ids include the
        # other user's session id.
        _make_session(session, "s-other", user_id=OTHER_USER_ID)
        _make_task(
            session,
            "t-other",
            "s-other",
            user_id=OTHER_USER_ID,
            status="running",
        )
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-other"]
        )
        assert result == set()

    def test_empty_session_ids_short_circuits(self, session, service):
        # No DB hit; expectation is just an empty set without errors.
        assert (
            service._find_sessions_with_running_background_tasks(session, USER_ID, [])
            == set()
        )

    def test_status_pending_surfaces(self, session, service):
        _make_session(session, "s-pending")
        _make_task(session, "t-pending", "s-pending", status="pending")
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-pending"]
        )
        assert result == {"s-pending"}

    def test_status_null_with_no_end_time_surfaces(self, session, service):
        _make_session(session, "s-null")
        _make_task(session, "t-null", "s-null", status=None)
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-null"]
        )
        assert result == {"s-null"}

    def test_only_requested_sessions_returned(self, session, service):
        _make_session(session, "s-in-page")
        _make_session(session, "s-out-of-page")
        _make_task(session, "t-in", "s-in-page", status="running")
        _make_task(session, "t-out", "s-out-of-page", status="running")
        session.flush()

        result = service._find_sessions_with_running_background_tasks(
            session, USER_ID, ["s-in-page"]
        )
        assert result == {"s-in-page"}
