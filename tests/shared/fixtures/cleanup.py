"""Shared cleanup fixtures and utilities."""
import pytest
from sqlalchemy import text, MetaData


def clean_all_tables(engine, exclude_tables=None):
    """
    Clean all tables in a database except specified ones.

    Args:
        engine: SQLAlchemy engine
        exclude_tables: List of table names to exclude (e.g., ["alembic_version"])
    """
    exclude_tables = exclude_tables or ["alembic_version"]

    with engine.connect() as conn:
        with conn.begin():
            metadata = MetaData()
            metadata.reflect(bind=engine)

            # Handle database-specific FK constraints
            db_url = str(engine.url)
            if db_url.startswith("sqlite"):
                conn.execute(text("PRAGMA foreign_keys=OFF"))

            # Delete in reverse order (respects FK constraints)
            for table in reversed(metadata.sorted_tables):
                if table.name not in exclude_tables:
                    conn.execute(table.delete())

            # Re-enable FK constraints
            if db_url.startswith("sqlite"):
                conn.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture
def auto_cleanup_database(db_engine):
    """Automatically clean database before and after test."""
    clean_all_tables(db_engine)
    yield
    clean_all_tables(db_engine)

