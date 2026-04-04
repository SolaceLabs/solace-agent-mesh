"""
Integration test fixtures and configuration.

This conftest imports and re-exports all fixtures from the fixtures/ subdirectory
for backward compatibility, while keeping integration-specific fixtures here.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from sqlalchemy import create_engine, event, text

from solace_agent_mesh.agent.adk.services import ScopedArtifactServiceWrapper

# Import all fixtures from subdirectories for pytest auto-discovery
from .fixtures import *  # noqa: F403

if TYPE_CHECKING:
    pass


def pytest_configure(config):
    """Configure pytest and set environment variables before test session starts."""
    # TEST_TOKEN_TRIGGER_THRESHOLD should only be set in specific compaction tests


@pytest.fixture(scope="function")
def enable_test_compaction_trigger():
    """
    Fixture to enable TEST_TOKEN_TRIGGER_THRESHOLD for specific compaction tests.

    Use this fixture in tests that need to trigger proactive compaction.
    Automatically cleans up the env var after the test.
    """
    original_value = os.environ.get("TEST_TOKEN_TRIGGER_THRESHOLD")
    os.environ["TEST_TOKEN_TRIGGER_THRESHOLD"] = "300"
    yield
    if original_value is not None:
        os.environ["TEST_TOKEN_TRIGGER_THRESHOLD"] = original_value
    else:
        os.environ.pop("TEST_TOKEN_TRIGGER_THRESHOLD", None)


@pytest.fixture(scope="session")
def test_db_engine():
    """
    Creates a temporary SQLite database for the test session, runs migrations,
    and yields the SQLAlchemy engine.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_integration.db"
        database_url = f"sqlite:///{db_path}"
        print(f"\n[SessionFixture] Creating test database at: {database_url}")

        engine = create_engine(database_url)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            if database_url.startswith("sqlite"):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        # Run Alembic migrations
        alembic_cfg = AlembicConfig()
        script_location = "src/solace_agent_mesh/gateway/http_sse/alembic"
        alembic_cfg.set_main_option("script_location", script_location)
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        alembic_command.upgrade(alembic_cfg, "head")
        print("[SessionFixture] Database migrations applied.")

        # Ensure write permissions
        if db_path.exists():
            os.chmod(db_path, 0o666)
            print(f"[SessionFixture] Set write permissions on database file: {db_path}")

        yield engine

        engine.dispose()
        print("[SessionFixture] Test database engine disposed.")


@pytest.fixture(autouse=True)
def clean_db_fixture(test_db_engine):
    """Cleans all data from the test database before each test run."""
    with test_db_engine.connect() as connection, connection.begin():
        inspector = sa.inspect(test_db_engine)
        existing_tables = inspector.get_table_names()

        # Delete in correct order to handle foreign key constraints
        tables_to_clean = [
            "feedback",
            "task_events",
            "chat_messages",
            "tasks",
            "sessions",
            "prompt_group_users",
            "prompts",
            "prompt_groups",
            "project_users",
            "projects",
            "users",
        ]
        for table_name in tables_to_clean:
            if table_name in existing_tables:
                connection.execute(text(f"DELETE FROM {table_name}"))
    yield


@pytest.fixture(scope="session")
def shared_solace_connector(
    test_llm_server,
    test_artifact_service_instance,
    session_monkeypatch,
    request,
    mcp_server_harness,
    test_db_engine,
    test_a2a_agent_server_harness,
    # Agent config fixtures
    sam_agent_app_config,
    peer_a_config,
    peer_b_config,
    peer_c_config,
    peer_d_config,
    compaction_agent_config,
    combined_dynamic_agent_config,
    empty_provider_agent_config,
    docstringless_agent_config,
    mixed_discovery_agent_config,
    complex_signatures_agent_config,
    config_context_agent_config,
    artifact_content_agent_config,
    # Gateway config fixtures
    minimal_gateway_config,
    auth_gateway_config,
    file_gateway_config,
    dispatching_gateway_config,
    webui_gateway_config,
    test_harness_gateway_config,
) -> SolaceAiConnector:
    """
    Creates and manages a single SolaceAiConnector instance with multiple agents
    for integration testing. Imports configurations from fixtures/ subdirectory.
    """
    # Reset MetricRegistry singleton before creating the connector to avoid
    # 'MetricRegistry already initialized' errors from SAC 3.3.6+.
    from solace_ai_connector.common.observability.registry import MetricRegistry

    MetricRegistry.reset()

    from .fixtures.workflow_configs import (
        get_a2a_proxy_config,
        get_conditional_workflow_config,
        get_instruction_workflow_config,
        get_loop_workflow_config,
        get_map_workflow_config,
        get_recursive_workflow_config,
        get_simple_workflow_config,
        get_structured_workflow_config,
        get_subworkflow_invoke_config,
        get_switch_workflow_config,
    )

    app_infos = [
        {
            "name": "WebUIBackendApp",
            "app_module": "solace_agent_mesh.gateway.http_sse.app",
            "broker": {"dev_mode": True},
            "app_config": webui_gateway_config,
        },
        {
            "name": "MinimalGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": minimal_gateway_config,
        },
        {
            "name": "AuthGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": auth_gateway_config,
        },
        {
            "name": "FileGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": file_gateway_config,
        },
        {
            "name": "DispatchingGatewayApp",
            "app_module": "solace_agent_mesh.gateway.generic.app",
            "broker": {"dev_mode": True},
            "app_config": dispatching_gateway_config,
        },
        {
            "name": "TestSamAgentApp",
            "app_config": sam_agent_app_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentA_App",
            "app_config": peer_a_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentB_App",
            "app_config": peer_b_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentC_App",
            "app_config": peer_c_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestPeerAgentD_App",
            "app_config": peer_d_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestAgentCompaction_App",
            "app_config": compaction_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "TestHarnessGatewayApp",
            "app_config": test_harness_gateway_config,
            "broker": {"dev_mode": True},
            "app_module": "sam_test_infrastructure.gateway_interface.app",
        },
        {
            "name": "CombinedDynamicAgent_App",
            "app_config": combined_dynamic_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "EmptyProviderAgent_App",
            "app_config": empty_provider_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "DocstringlessAgent_App",
            "app_config": docstringless_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "MixedDiscoveryAgent_App",
            "app_config": mixed_discovery_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "ComplexSignaturesAgent_App",
            "app_config": complex_signatures_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "ConfigContextAgent_App",
            "app_config": config_context_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        {
            "name": "ArtifactContentAgent_App",
            "app_config": artifact_content_agent_config,
            "broker": {"dev_mode": True},
            "app_module": "solace_agent_mesh.agent.sac.app",
        },
        get_simple_workflow_config(),
        get_structured_workflow_config(),
        get_conditional_workflow_config(),
        get_map_workflow_config(),
        get_switch_workflow_config(),
        get_loop_workflow_config(),
        get_instruction_workflow_config(),
        get_subworkflow_invoke_config(),
        get_recursive_workflow_config(),
        get_a2a_proxy_config(test_a2a_agent_server_harness),
    ]

    session_monkeypatch.setattr(
        "solace_agent_mesh.agent.adk.services.TestInMemoryArtifactService",
        lambda: test_artifact_service_instance,
    )
    session_monkeypatch.setattr(
        "solace_agent_mesh.agent.proxies.base.component.initialize_artifact_service",
        lambda component: ScopedArtifactServiceWrapper(
            wrapped_service=test_artifact_service_instance, component=component
        ),
    )
    session_monkeypatch.setattr(
        "solace_agent_mesh.agent.adk.services.initialize_artifact_service",
        lambda component: ScopedArtifactServiceWrapper(
            wrapped_service=test_artifact_service_instance, component=component
        ),
    )

    log_level_str = request.config.getoption("--log-cli-level") or "INFO"

    connector_config = {
        "apps": app_infos,
        "log": {
            "stdout_log_level": log_level_str.upper(),
            "log_file_level": "INFO",
            "enable_trace": False,
        },
    }
    print(
        f"\n[Conftest] Configuring SolaceAiConnector with stdout log level: {log_level_str.upper()}"
    )
    connector = SolaceAiConnector(config=connector_config)
    connector.run()
    print(
        f"shared_solace_connector fixture: Started SolaceAiConnector with apps: {[app['name'] for app in connector_config['apps']]}"
    )

    # Allow time for agent card discovery
    print("shared_solace_connector fixture: Waiting for agent discovery...")
    time.sleep(5)
    print("shared_solace_connector fixture: Agent discovery wait complete.")

    yield connector

    print("shared_solace_connector fixture: Cleaning up SolaceAiConnector...")
    connector.stop()
    connector.cleanup()
    print("shared_solace_connector fixture: SolaceAiConnector cleaned up.")


def test_a2a_sdk_import():
    """Verifies that the a2a-sdk can be imported."""
    try:
        from a2a.types import Task

        assert Task is not None
    except ImportError as e:
        pytest.fail(f"Failed to import from a2a-sdk: {e}")
