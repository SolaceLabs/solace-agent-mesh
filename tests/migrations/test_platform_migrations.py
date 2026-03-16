"""
Migration tests for the platform service Alembic tree.

Alembic dir: src/solace_agent_mesh/services/platform/alembic/

Both tests are fully dynamic:
- No revision IDs are hardcoded.
- No model classes are imported individually; the package import
  `import solace_agent_mesh.shared.outbox` triggers __init__.py which
  registers OutboxEventModel (and any future models added to the package)
  on Base. New models added to __init__.py are picked up automatically
  with zero test changes.
"""

import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


@pytest.fixture(
    params=["sqlite", "postgresql", "mysql"],
    ids=["sqlite", "postgresql", "mysql"],
)
def db_url(request, pg_platform_url, mysql_platform_url, tmp_path):
    """Platform tree: sqlite uses a fresh file; PG/MySQL use the platform database."""
    db_type = request.config.getoption("--db-type", default=None)
    if db_type and request.param != db_type:
        pytest.skip(f"Skipping {request.param} (--db-type={db_type})")
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'platform_migration.db'}"
    elif request.param == "postgresql":
        yield pg_platform_url
    else:
        yield mysql_platform_url


def _make_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        os.path.join(
            os.path.dirname(__file__),
            "..", "..",
            "src", "solace_agent_mesh", "services", "platform", "alembic",
        ),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_platform_upgrade_applies_all_revisions(db_url):
    """Full base→head upgrade runs without error and records the correct head revision."""
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


def test_platform_schema_matches_models(db_url):
    """After upgrade, the live DB schema matches the SQLAlchemy model metadata exactly."""
    import solace_agent_mesh.shared.outbox  # noqa: F401 — registers all outbox models on Base
    from solace_agent_mesh.shared.database import Base

    cfg = _make_cfg(db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"Schema drift on {engine.dialect.name}: {diff}"
    finally:
        engine.dispose()
