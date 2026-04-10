"""Shared cleanup fixtures and utilities."""

import pytest
from sqlalchemy import MetaData, text


def clean_all_tables(engine, exclude_tables=None):
    """
    Clean all tables in a database except specified ones.

    Args:
        engine: SQLAlchemy engine
        exclude_tables: List of table names to exclude (e.g., ["alembic_version"])
    """
    exclude_tables = exclude_tables or ["alembic_version"]

    with engine.connect() as conn, conn.begin():
        metadata = MetaData()
        metadata.reflect(bind=conn)

        # Delete in reverse order (respects FK constraints)
        for table in reversed(metadata.sorted_tables):
            if table.name not in exclude_tables:
                conn.execute(table.delete())


@pytest.fixture
def auto_cleanup_database(db_engine):
    """Automatically clean database before and after test."""
    clean_all_tables(db_engine)
    yield
    clean_all_tables(db_engine)
