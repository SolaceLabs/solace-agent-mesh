"""
Shared fixtures for migration tests.

One PostgreSQL container + one MySQL container per session.
Each container hosts 3 named databases (gateway, adk, platform) so the
three migration trees never share an alembic_version table.

SQLite uses tmp_path for a fresh per-test file named after each tree.
"""

import pytest
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Container fixtures — one PG and one MySQL container for the whole session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _pg_base_url():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:18") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def _mysql_container():
    from testcontainers.mysql import MySqlContainer

    with MySqlContainer("mysql:8") as mysql:
        yield mysql


@pytest.fixture(scope="session")
def _mysql_base_url(_mysql_container):
    raw = _mysql_container.get_connection_url()
    for prefix in ("mysql+mysqldb://", "mysql+mysqlconnector://", "mysql://"):
        raw = raw.replace(prefix, "mysql+pymysql://")
    return raw


@pytest.fixture(scope="session")
def _mysql_root_url(_mysql_container):
    # get_connection_url() has no username/password parameters in this version of
    # testcontainers — build the root URL from the container's attributes directly.
    host = _mysql_container.get_container_host_ip()
    port = _mysql_container.get_exposed_port(_mysql_container.port)
    root_password = _mysql_container.root_password
    dbname = _mysql_container.dbname
    return f"mysql+pymysql://root:{root_password}@{host}:{port}/{dbname}"


# ---------------------------------------------------------------------------
# Helpers — create a named database on each container
# ---------------------------------------------------------------------------

def _make_pg_db(base_url: str, name: str) -> str:
    """Create a named PostgreSQL database and return its connection URL."""
    engine = sa.create_engine(base_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    engine.dispose()
    return base_url.rsplit("/", 1)[0] + f"/{name}"


def _make_mysql_db(root_url: str, test_url: str, name: str) -> str:
    """Create a named MySQL database as root, grant access to the test user."""
    test_user = test_url.split("://")[1].split(":")[0]
    engine = sa.create_engine(root_url)
    with engine.connect() as conn:
        conn.execute(sa.text(f"CREATE DATABASE IF NOT EXISTS `{name}`"))
        conn.execute(sa.text(f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{test_user}'@'%'"))
        conn.commit()
    engine.dispose()
    return test_url.rsplit("/", 1)[0] + f"/{name}"


# ---------------------------------------------------------------------------
# Per-tree PostgreSQL URLs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_gateway_url(_pg_base_url):
    yield _make_pg_db(_pg_base_url, "gateway")


@pytest.fixture(scope="session")
def pg_adk_url(_pg_base_url):
    yield _make_pg_db(_pg_base_url, "adk")


@pytest.fixture(scope="session")
def pg_platform_url(_pg_base_url):
    yield _make_pg_db(_pg_base_url, "platform")


# ---------------------------------------------------------------------------
# Per-tree MySQL URLs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mysql_gateway_url(_mysql_root_url, _mysql_base_url):
    yield _make_mysql_db(_mysql_root_url, _mysql_base_url, "gateway")


@pytest.fixture(scope="session")
def mysql_adk_url(_mysql_root_url, _mysql_base_url):
    yield _make_mysql_db(_mysql_root_url, _mysql_base_url, "adk")


@pytest.fixture(scope="session")
def mysql_platform_url(_mysql_root_url, _mysql_base_url):
    yield _make_mysql_db(_mysql_root_url, _mysql_base_url, "platform")
