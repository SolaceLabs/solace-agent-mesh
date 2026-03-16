"""
Migration tests for the ADK agent Alembic tree.

Alembic dir: src/solace_agent_mesh/agent/adk/alembic/

The ADK tree migrates on top of Google ADK's own `events` table.
`Base` from `google.adk.sessions.database_session_service` is the same
import used by env.py — it is an infrastructure dependency, not a
SAM-specific model. `Base.metadata.create_all()` bootstraps the base
ADK schema before SAM's migration runs.

Both tests are fully dynamic:
- No revision IDs are hardcoded.
- No SAM model classes are imported.
- No column names are hardcoded.
- New ADK migrations added in the future are covered automatically.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


@pytest.fixture(
    params=["sqlite", "postgresql", "mysql"],
    ids=["sqlite", "postgresql", "mysql"],
)
def db_url(request, pg_adk_url, mysql_adk_url, tmp_path):
    """ADK tree: sqlite uses a fresh file; PG/MySQL use the adk database."""
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'adk_migration.db'}"
    elif request.param == "postgresql":
        yield pg_adk_url
    else:
        yield mysql_adk_url


def _make_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        os.path.join(
            os.path.dirname(__file__),
            "..", "..",
            "src", "solace_agent_mesh", "agent", "adk", "alembic",
        ),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _bootstrap_adk_schema(db_url: str) -> None:
    """Create the base ADK schema (the `events` table SAM migrates on top of)."""
    from google.adk.sessions.database_session_service import (
        Base,  # same import as env.py
    )

    engine = create_engine(db_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def test_adk_upgrade_applies_all_revisions(db_url):
    """Full upgrade runs without error and records the correct head revision."""
    _bootstrap_adk_schema(db_url)

    cfg = _make_cfg(db_url)
    command.upgrade(cfg, "head")

    script = ScriptDirectory.from_config(cfg)
    expected_head = script.get_current_head()

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert row is not None and row[0] == expected_head
    finally:
        engine.dispose()


def test_adk_upgrade_is_idempotent(db_url):
    """Running upgrade twice must not raise (migrations use column_exists guards)."""
    _bootstrap_adk_schema(db_url)

    cfg = _make_cfg(db_url)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # second run must be a no-op, not an error
