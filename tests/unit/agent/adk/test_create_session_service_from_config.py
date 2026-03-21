"""Tests for create_session_service_from_config factory."""

import os

import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.agent.adk.services import create_session_service_from_config


class TestCreateSessionServiceFromConfig:
    """Tests for the create_session_service_from_config factory covering all branches."""

    def test_memory_type_returns_in_memory_service(self):
        from google.adk.sessions import InMemorySessionService

        result = create_session_service_from_config({"type": "memory"})
        assert isinstance(result, InMemorySessionService)

    def test_memory_type_is_default_when_type_missing(self):
        from google.adk.sessions import InMemorySessionService

        result = create_session_service_from_config({})
        assert isinstance(result, InMemorySessionService)

    def test_sql_type_returns_database_session_service(self):
        from google.adk.sessions import DatabaseSessionService

        result = create_session_service_from_config(
            {"type": "sql", "database_url": "sqlite:///:memory:"}
        )
        assert isinstance(result, DatabaseSessionService)

    def test_sql_type_raises_when_database_url_missing(self):
        with pytest.raises(ValueError, match="database_url"):
            create_session_service_from_config({"type": "sql"})

    def test_vertex_type_returns_vertex_service(self):
        with patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "test-project", "GOOGLE_CLOUD_LOCATION": "us-central1"},
        ), patch(
            "solace_agent_mesh.agent.adk.services.VertexAiSessionService"
        ) as mock_vertex:
            mock_vertex.return_value = MagicMock()
            result = create_session_service_from_config({"type": "vertex"})
            mock_vertex.assert_called_once_with(
                project="test-project", location="us-central1"
            )
            assert result is mock_vertex.return_value

    def test_vertex_type_raises_when_env_vars_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env vars if they exist
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
            os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
            with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
                create_session_service_from_config({"type": "vertex"})

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            create_session_service_from_config({"type": "redis"})

    def test_accepts_config_object_with_type_attribute(self):
        from google.adk.sessions import InMemorySessionService

        config = MagicMock()
        config.type = "memory"
        result = create_session_service_from_config(config)
        assert isinstance(result, InMemorySessionService)

    def test_sql_with_migrations(self):
        mock_component = MagicMock()
        with patch(
            "solace_agent_mesh.agent.adk.services.DatabaseSessionService"
        ) as mock_db_svc, patch(
            "solace_agent_mesh.agent.adk.services.run_migrations"
        ) as mock_migrate:
            mock_db_svc.return_value = MagicMock()
            result = create_session_service_from_config(
                {"type": "sql", "database_url": "sqlite:///:memory:"},
                run_db_migrations=True,
                migration_component=mock_component,
            )
            mock_migrate.assert_called_once_with(mock_db_svc.return_value, mock_component)
            assert result is mock_db_svc.return_value
