"""
Migration tests for the HTTP/SSE gateway Alembic tree.

Alembic dir: src/solace_agent_mesh/gateway/http_sse/alembic/
Models pkg:  solace_agent_mesh.gateway.http_sse.repository.models

Both tests are fully dynamic:
- No revision IDs are hardcoded.
- No model classes are imported individually; the package import triggers
  __init__.py which registers all models on Base. New models added to
  __init__.py are picked up automatically with zero test changes.
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
def db_url(request, pg_gateway_url, mysql_gateway_url, tmp_path):
    """Gateway tree: sqlite uses a fresh file; PG/MySQL use the gateway database."""
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'gateway_migration.db'}"
    elif request.param == "postgresql":
        yield pg_gateway_url
    else:
        yield mysql_gateway_url


def _make_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        os.path.join(
            os.path.dirname(__file__),
            "..", "..",
            "src", "solace_agent_mesh", "gateway", "http_sse", "alembic",
        ),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_gateway_upgrade_applies_all_revisions(db_url):
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


def _column_names(idx):
    """Return the base column names of an index, stripping sort direction.

    For a plain reflected Column the name is idx.key.
    For a TextClause like 'updated_time DESC' we take the first whitespace-delimited
    token, which is always the column name.
    """
    from sqlalchemy.schema import Column

    names = set()
    for expr in idx.expressions:
        if isinstance(expr, Column):
            names.add(expr.key)
        else:
            # TextClause or similar — strip direction qualifiers
            names.add(str(expr).split()[0])
    return names


def _reconcile_expression_index_drift(diff):
    """Reconcile spurious add/remove pairs caused by expression-index reflection limits.

    SQLite and MySQL cannot round-trip functional/descending indexes (e.g. a DESC
    column expressed via sa.text()). compare_metadata emits both:
    - 'add_index'    with a TextClause expression  (model side, functional form)
    - 'remove_index' with plain Column objects      (DB side, direction stripped)
    for the same index name.

    This function removes such a pair only when both conditions hold:
    1. The same index name appears in both an 'add_index' and a 'remove_index' entry.
    2. The base column names (ignoring sort direction) are identical on both sides.

    If condition 2 fails — meaning the column sets differ — the entries are kept so
    the assertion catches genuine schema drift.
    """
    from sqlalchemy import Index

    adds = {
        item[1].name: item[1]
        for item in diff
        if item[0] == "add_index" and isinstance(item[1], Index)
    }
    removes = {
        item[1].name: item[1]
        for item in diff
        if item[0] == "remove_index" and isinstance(item[1], Index)
    }

    # Names that appear on both sides with matching column sets — safe to drop
    forgiven = {
        name
        for name in adds.keys() & removes.keys()
        if _column_names(adds[name]) == _column_names(removes[name])
    }

    return [
        item for item in diff
        if not (
            item[0] in ("add_index", "remove_index")
            and getattr(item[1], "name", None) in forgiven
        )
    ]


def test_gateway_schema_matches_models(db_url):
    """After upgrade, the live DB schema matches the SQLAlchemy model metadata exactly."""
    import solace_agent_mesh.gateway.http_sse.repository.models  # noqa: F401 — registers all models on Base
    from solace_agent_mesh.gateway.http_sse.repository.models.base import Base

    cfg = _make_cfg(db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)

        # SQLite and MySQL cannot round-trip expression/descending indexes.
        # Reconcile pairs where the index exists with the correct columns but the
        # sort direction was lost during reflection. Pairs with mismatched columns
        # are kept so genuine drift is still caught.
        if engine.dialect.name in ("sqlite", "mysql"):
            diff = _reconcile_expression_index_drift(diff)

        assert diff == [], f"Schema drift on {engine.dialect.name}: {diff}"
    finally:
        engine.dispose()
