"""
Pytest fixtures for Platform Service integration testing.

Provides FastAPI TestClient and HTTP-based testing infrastructure for Platform Service.
Uses separate database from WebUI Gateway tests.
"""

import logging

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sam_test_infrastructure.fastapi_service.platform_service_factory import (
    PlatformServiceFactory,
)
from sqlalchemy import text

from tests.integration.apis.infrastructure.database_manager import (
    DatabaseProviderFactory,
)

log = logging.getLogger(__name__)

TEST_USER_HEADER = "X-Test-User-Id"


def _patch_mock_component_config(factory):
    """Patches the mock component's get_config method for Platform Service."""
    if not hasattr(factory, "mock_component"):
        return

    original_side_effect = factory.mock_component.get_config.side_effect

    def get_config_side_effect(key, default=None):
        if key == "name":
            return "Platform_Service"
        if callable(original_side_effect):
            return original_side_effect(key, default)
        return default

    factory.mock_component.get_config.side_effect = get_config_side_effect
    log.info("Patched mock_component.get_config for Platform Service.")


@pytest.fixture(scope="session")
def platform_db_provider_type():
    """Database provider type for Platform Service tests.

    Returns SQLite by default - can be parameterized for multi-db testing.
    """
    return "sqlite"


@pytest.fixture(scope="session")
def platform_db_provider(platform_db_provider_type):
    """Database provider fixture for Platform Service.

    Creates a SEPARATE database from WebUI Gateway tests.
    """
    provider = DatabaseProviderFactory.create_provider(platform_db_provider_type)
    provider.setup(agent_names=[])

    if hasattr(provider, "get_gateway_url_with_credentials"):
        db_url = provider.get_gateway_url_with_credentials()
    else:
        db_url = str(provider.get_sync_gateway_engine().url)

    factory = PlatformServiceFactory(db_url=db_url)
    _patch_mock_component_config(factory)
    factory.setup_multi_user_testing(provider, TEST_USER_HEADER)
    provider.factory = factory

    log.info(f"[Platform Tests] Created PlatformServiceFactory with {provider.provider_type} database")

    yield provider

    factory.teardown()
    provider.teardown()


@pytest.fixture(scope="session")
def platform_api_client_factory(platform_db_provider):
    """Returns the PlatformServiceFactory created by platform_db_provider."""
    return platform_db_provider.factory


@pytest.fixture(scope="session")
def platform_api_client(platform_db_provider, platform_api_client_factory):
    """Creates a TestClient for Platform Service API testing."""
    app = platform_api_client_factory.app

    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)

    client = HeaderBasedTestClient(app, "sam_dev_user")
    log.info(f"[Platform Tests] FastAPI TestClient created from {platform_db_provider.provider_type} db_provider")

    yield client


@pytest.fixture(scope="session")
def secondary_platform_api_client(platform_api_client_factory):
    """Creates a secondary TestClient for Platform Service (different user)."""
    class HeaderBasedTestClient(TestClient):
        def __init__(self, app, user_id: str):
            super().__init__(app)
            self.test_user_id = user_id

        def request(self, method, url, **kwargs):
            if "headers" not in kwargs or kwargs["headers"] is None:
                kwargs["headers"] = {}
            kwargs["headers"][TEST_USER_HEADER] = self.test_user_id
            return super().request(method, url, **kwargs)

    client = HeaderBasedTestClient(platform_api_client_factory.app, "secondary_user")
    log.info("[Platform Tests] Secondary FastAPI TestClient created (same database, different user)")

    yield client


@pytest.fixture(autouse=True)
def clean_database_between_tests():
    """Override parent apis/conftest's clean_database_between_tests."""
    yield


@pytest.fixture(autouse=True)
def clean_db_fixture():
    """Override grandparent integration/conftest's clean_db_fixture."""
    yield


@pytest.fixture(autouse=True)
def clear_llm_server_configs():
    """Override grandparent integration/conftest's clear_llm_server_configs."""
    yield


@pytest.fixture(autouse=True)
def clear_static_file_server_state():
    """Override grandparent integration/conftest's clear_static_file_server_state."""
    yield


@pytest.fixture(autouse=True, scope="function")
async def clear_test_artifact_service_between_tests():
    """Override grandparent integration/conftest's clear_test_artifact_service_between_tests."""
    yield


@pytest.fixture(autouse=True, scope="function")
def clear_test_gateway_state_between_tests():
    """Override grandparent integration/conftest's clear_test_gateway_state_between_tests."""
    yield


@pytest.fixture(autouse=True, scope="function")
def clear_all_agent_states_between_tests():
    """Override grandparent integration/conftest's clear_all_agent_states_between_tests."""
    yield


@pytest.fixture(autouse=True)
def clean_platform_database_between_tests(platform_db_provider):
    """Cleans Platform Service database state between tests."""
    _clean_platform_database(platform_db_provider.get_sync_gateway_engine())
    yield
    _clean_platform_database(platform_db_provider.get_sync_gateway_engine())
    log.debug("[Platform Tests] Database cleaned between tests")


def _clean_platform_database(engine):
    """Clean the Platform Service test database."""
    with engine.connect() as connection, connection.begin():
        metadata = sa.MetaData()
        metadata.reflect(bind=connection)

        db_url = str(connection.engine.url)
        if db_url.startswith("sqlite"):
            connection.execute(text("PRAGMA foreign_keys=OFF"))

        for table in reversed(metadata.sorted_tables):
            if table.name == "alembic_version":
                continue
            connection.execute(table.delete())

        if db_url.startswith("sqlite"):
            connection.execute(text("PRAGMA foreign_keys=ON"))


@pytest.fixture
def platform_db_session_factory(platform_api_client_factory):
    """Provides SQLAlchemy session factory for Platform Service database."""
    return platform_api_client_factory.Session


@pytest.fixture
def platform_db_engine(platform_api_client_factory):
    """Provides SQLAlchemy engine for Platform Service database."""
    return platform_api_client_factory.engine


__all__ = [
    "platform_api_client",
    "platform_api_client_factory",
    "secondary_platform_api_client",
    "clean_database_between_tests",
    "clean_platform_database_between_tests",
    "platform_db_provider_type",
    "platform_db_provider",
    "platform_db_session_factory",
    "platform_db_engine",
]
