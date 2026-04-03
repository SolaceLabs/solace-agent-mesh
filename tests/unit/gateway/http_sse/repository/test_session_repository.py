import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models.base import Base
from solace_agent_mesh.gateway.http_sse.repository.models.session_model import SessionModel
from solace_agent_mesh.gateway.http_sse.repository.models.project_model import ProjectModel  # register FK target
from solace_agent_mesh.gateway.http_sse.repository.session_repository import SessionRepository
from solace_agent_mesh.shared.api.pagination import PaginationParams


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
def repo():
    return SessionRepository()


USER_ID = "user-1"


def _seed_sessions(session: DBSession):
    """Insert one chat session and one scheduler session for USER_ID."""
    chat = SessionModel(
        id="session-chat",
        name="Chat session",
        user_id=USER_ID,
        source="chat",
        created_time=1700000000000,
        updated_time=1700000000000,
    )
    scheduler = SessionModel(
        id="session-sched",
        name="Scheduler session",
        user_id=USER_ID,
        source="scheduler",
        created_time=1700000001000,
        updated_time=1700000001000,
    )
    session.add_all([chat, scheduler])
    session.flush()


# ---------------------------------------------------------------------------
# find_by_user tests
# ---------------------------------------------------------------------------

class TestFindByUserSourceFilter:
    def test_source_chat_excludes_scheduler(self, session, repo):
        _seed_sessions(session)
        results = repo.find_by_user(session, USER_ID, source="chat")
        assert len(results) == 1
        assert results[0].id == "session-chat"

    def test_source_scheduler_excludes_chat(self, session, repo):
        _seed_sessions(session)
        results = repo.find_by_user(session, USER_ID, source="scheduler")
        assert len(results) == 1
        assert results[0].id == "session-sched"

    def test_source_none_returns_all(self, session, repo):
        _seed_sessions(session)
        results = repo.find_by_user(session, USER_ID, source=None)
        assert len(results) == 2
        returned_ids = {r.id for r in results}
        assert returned_ids == {"session-chat", "session-sched"}


# ---------------------------------------------------------------------------
# count_by_user tests
# ---------------------------------------------------------------------------

class TestCountByUserSourceFilter:
    def test_count_source_chat(self, session, repo):
        _seed_sessions(session)
        count = repo.count_by_user(session, USER_ID, source="chat")
        assert count == 1

    def test_count_source_scheduler(self, session, repo):
        _seed_sessions(session)
        count = repo.count_by_user(session, USER_ID, source="scheduler")
        assert count == 1

    def test_count_source_none_returns_total(self, session, repo):
        _seed_sessions(session)
        count = repo.count_by_user(session, USER_ID, source=None)
        assert count == 2
