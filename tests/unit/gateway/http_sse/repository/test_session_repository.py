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


# ---------------------------------------------------------------------------
# agent_id filter tests (embedded single-agent surface)
# ---------------------------------------------------------------------------

def _seed_agent_sessions(session: DBSession):
    """Insert chat sessions for USER_ID owned by different agents, plus one with no agent."""
    session.add_all([
        SessionModel(id="s-alpha", name="Alpha chat", user_id=USER_ID, source="chat", agent_id="AlphaAgent", created_time=1700000000000, updated_time=1700000000000),
        SessionModel(id="s-beta", name="Beta chat", user_id=USER_ID, source="chat", agent_id="BetaAgent", created_time=1700000001000, updated_time=1700000001000),
        SessionModel(id="s-none", name="No agent", user_id=USER_ID, source="chat", agent_id=None, created_time=1700000002000, updated_time=1700000002000),
    ])
    session.flush()


class TestFindByUserAgentFilter:
    def test_agent_filter_returns_only_that_agent(self, session, repo):
        _seed_agent_sessions(session)
        results = repo.find_by_user(session, USER_ID, agent_id="AlphaAgent")
        assert [r.id for r in results] == ["s-alpha"]

    def test_agent_filter_excludes_null_agent_sessions(self, session, repo):
        _seed_agent_sessions(session)
        results = repo.find_by_user(session, USER_ID, agent_id="BetaAgent")
        assert {r.id for r in results} == {"s-beta"}

    def test_agent_filter_none_returns_all(self, session, repo):
        _seed_agent_sessions(session)
        results = repo.find_by_user(session, USER_ID, agent_id=None)
        assert len(results) == 3


class TestCountByUserAgentFilter:
    def test_count_agent_filter(self, session, repo):
        _seed_agent_sessions(session)
        assert repo.count_by_user(session, USER_ID, agent_id="AlphaAgent") == 1

    def test_count_agent_none_returns_total(self, session, repo):
        _seed_agent_sessions(session)
        assert repo.count_by_user(session, USER_ID, agent_id=None) == 3


class TestSearchAgentFilter:
    def test_search_scoped_to_agent(self, session, repo):
        _seed_agent_sessions(session)  # names: "Alpha chat", "Beta chat", "No agent"
        results = repo.search(session, USER_ID, "chat", agent_id="AlphaAgent")
        assert [r.id for r in results] == ["s-alpha"]

    def test_search_without_agent_matches_all(self, session, repo):
        _seed_agent_sessions(session)
        results = repo.search(session, USER_ID, "chat")
        assert {r.id for r in results} == {"s-alpha", "s-beta"}

    def test_count_search_scoped_to_agent(self, session, repo):
        _seed_agent_sessions(session)
        assert repo.count_search_results(session, USER_ID, "chat", agent_id="BetaAgent") == 1
