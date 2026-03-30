"""Shared database fixtures for all tests."""
import pytest
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def sqlite_engine():
    """Create a session-scoped SQLite engine for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        database_url = f"sqlite:///{db_path}"

        engine = create_engine(database_url)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        yield engine
        engine.dispose()


@pytest.fixture
def sqlite_session_factory(sqlite_engine):
    """Create SQLite session factory."""
    return sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)


@pytest.fixture
def sqlite_session(sqlite_session_factory):
    """Create a SQLite session for a test."""
    session = sqlite_session_factory()
    yield session
    session.close()

