"""
Shared pytest configuration for ALL SAM component migration tests.

Uses testcontainers for automatic PostgreSQL and MySQL management.
No manual docker commands needed - everything is automatic.

This provides:
- Automatic Docker container lifecycle
- Database connection fixtures for all dialects
- Database cleanup utilities
- Parametrized dialect fixture
"""
import pytest
from sqlalchemy import create_engine, text, inspect
from typing import Generator


# =============================================================================
# Testcontainer Fixtures - Automatic Container Management
# =============================================================================

@pytest.fixture(scope="session")
def postgres_container():
    """
    PostgreSQL container - automatically starts and stops.

    Scope: session (shared across all tests for performance)
    Cleanup: Automatic when test session ends
    """
    from testcontainers.postgres import PostgresContainer

    postgres = PostgresContainer("postgres:15-alpine")
    postgres.start()

    yield postgres

    postgres.stop()


@pytest.fixture(scope="session")
def mysql_container():
    """
    MySQL container - automatically starts and stops.

    Scope: session (shared across all tests for performance)
    Cleanup: Automatic when test session ends

    Optimized for test speed:
    - Disables binary logging
    - Disables sync to disk (durability not needed for tests)
    - Reduces InnoDB overhead
    """
    from testcontainers.mysql import MySqlContainer

    mysql = MySqlContainer("mysql:8.0")

    # Speed optimizations for tests (2-3x faster)
    mysql.with_command(
        "--skip-log-bin "                      # Disable binary logs
        "--innodb-flush-log-at-trx-commit=2 "  # Only flush log to disk once per second
        "--innodb-doublewrite=0 "              # Disable doublewrite buffer
        "--sync-binlog=0 "                     # Disable binlog sync
        "--performance-schema=OFF "            # Disable performance schema overhead
        "--innodb-buffer-pool-size=64M"        # Small buffer pool for tests
    )

    mysql.start()

    yield mysql

    mysql.stop()


# =============================================================================
# Database URL Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def postgres_url(postgres_container) -> str:
    """Get PostgreSQL connection URL from container."""
    # Manually construct URL to ensure correct driver (following existing pattern)
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user = postgres_container.username
    password = postgres_container.password
    database = postgres_container.dbname

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture(scope="session")
def mysql_url(mysql_container) -> str:
    """Get MySQL connection URL from container."""
    # Manually construct URL to ensure pymysql driver (following existing pattern)
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    user = mysql_container.username
    password = mysql_container.password
    database = mysql_container.dbname

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


# =============================================================================
# Database Cleanup Utilities
# =============================================================================

def clean_postgres_schema(url: str) -> None:
    """Drop all tables in PostgreSQL database."""
    engine = create_engine(url)
    with engine.connect() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if tables:
            for table in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            conn.commit()

    engine.dispose()


def clean_mysql_schema(url: str) -> None:
    """Drop all tables in MySQL database."""
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    engine.dispose()


# =============================================================================
# Database Fixtures - One per dialect
# =============================================================================

@pytest.fixture
def clean_sqlite_db() -> Generator[str, None, None]:
    """
    Provide a clean SQLite database (file-based for tests).

    Using file-based instead of :memory: because in-memory creates
    a separate database per connection, breaking alembic + inspector isolation.

    Performance optimizations:
    - WAL mode set once (persists in DB file, speeds up all writes)
    """
    import tempfile
    import os
    from sqlalchemy import create_engine

    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Set WAL mode (persists in DB file across all connections)
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode = WAL")
        conn.commit()
    engine.dispose()

    yield url

    # Cleanup
    try:
        os.unlink(path)
        # Clean up WAL files
        for suffix in ['-shm', '-wal']:
            try:
                os.unlink(f"{path}{suffix}")
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass


@pytest.fixture
def clean_postgres_db(postgres_url) -> Generator[str, None, None]:
    """
    Provide a clean PostgreSQL database.

    Cleans schema before and after test.
    Container managed automatically by postgres_container fixture.
    """
    # Clean before test
    clean_postgres_schema(postgres_url)

    yield postgres_url

    # Clean after test
    clean_postgres_schema(postgres_url)


@pytest.fixture
def clean_mysql_db(mysql_url) -> Generator[str, None, None]:
    """
    Provide a clean MySQL database.

    Cleans schema before and after test.
    Container managed automatically by mysql_container fixture.
    """
    # Clean before test
    clean_mysql_schema(mysql_url)

    yield mysql_url

    # Clean after test
    clean_mysql_schema(mysql_url)


# =============================================================================
# Parametrized Dialect Fixture
# =============================================================================

@pytest.fixture(
    params=[
        pytest.param("sqlite", id="SQLite", marks=pytest.mark.xdist_group("sqlite")),
        pytest.param("postgres", id="PostgreSQL", marks=pytest.mark.xdist_group("postgres")),
        pytest.param("mysql", id="MySQL", marks=pytest.mark.xdist_group("mysql")),
    ]
)
def dialect_db(request, clean_sqlite_db, clean_postgres_db, clean_mysql_db) -> str:
    """
    Parametrized fixture providing clean database for each dialect.

    Tests using this fixture will run 3 times (once per dialect).
    Containers start automatically on first use.

    Each database type is assigned to its own xdist group for parallel execution:
    - All SQLite tests run on one worker
    - All PostgreSQL tests run on another worker
    - All MySQL tests run on another worker

    Returns:
        Database connection URL for the current dialect
    """
    dialect_map = {
        "sqlite": clean_sqlite_db,
        "postgres": clean_postgres_db,
        "mysql": clean_mysql_db,
    }
    return dialect_map[request.param]


# =============================================================================
# SQLAlchemy Utilities
# =============================================================================

@pytest.fixture
def db_engine(dialect_db):
    """
    Create SQLAlchemy engine for the test database.

    Automatically disposed after test.
    """
    engine = create_engine(dialect_db)
    yield engine
    engine.dispose()


@pytest.fixture
def db_inspector(db_engine):
    """
    Create SQLAlchemy inspector for examining database schema.

    Useful for validating table structure, indexes, foreign keys, etc.
    """
    return inspect(db_engine)
