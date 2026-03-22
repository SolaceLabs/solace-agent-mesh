import time

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from solace_agent_mesh.shared.database import Base
from solace_agent_mesh.shared.outbox import (
    CreateOutboxEventModel,
    OutboxEventModel,
    OutboxEventRepository,
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def cleanup_tables(engine):
    yield
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM outbox_events"))
        conn.commit()


@pytest.fixture
def outbox_repo():
    return OutboxEventRepository()


@pytest.fixture
def create_event(db_session, outbox_repo):
    def _create(
        entity_type="agent",
        entity_id="agt-001",
        event_type="auto_upgrade",
        status="pending",
        payload=None,
        next_retry_at=0,
    ):
        return outbox_repo.create_event(
            db_session,
            CreateOutboxEventModel(
                entity_type=entity_type,
                entity_id=entity_id,
                event_type=event_type,
                status=status,
                payload=payload,
                next_retry_at=next_retry_at,
            ),
        )

    return _create
