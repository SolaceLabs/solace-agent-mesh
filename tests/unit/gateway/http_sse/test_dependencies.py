#!/usr/bin/env python3
"""
Comprehensive unit tests for dependencies.py to achieve 85%+ coverage.

Tests cover:
1. Global state management (component, database, config initialization)
2. All dependency getter functions
3. Optional dependencies
4. ValidatedUserConfig class
5. Session validation
6. Error handling and edge cases
"""

import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from solace_agent_mesh.gateway.http_sse import dependencies
from solace_agent_mesh.gateway.http_sse.dependencies import (
    ValidatedUserConfig,
    ensure_session_id,
    ensure_session_id_callable,
    get_agent_card_service,
    get_agent_registry,
    get_api_config,
    get_app_config,
    get_config_resolver,
    get_core_a2a_service,
    get_data_retention_service,
    get_db,
    get_db_optional,
    get_embed_config,
    get_feedback_service,
    get_gateway_id,
    get_identity_service,
    get_namespace,
    get_people_service,
    get_project_service,
    get_project_service_optional,
    get_publish_a2a_func,
    get_sac_component,
    get_session_business_service,
    get_session_business_service_optional,
    get_session_manager,
    get_session_validator,
    get_shared_artifact_service,
    get_sse_manager,
    get_task_context_manager_from_component,
    get_task_logger_service,
    get_task_repository,
    get_task_service,
    get_user_config,
    get_user_id,
    get_user_id_callable,
    init_database,
    set_api_config,
    set_component_instance,
)

# Fixtures

@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test to ensure test isolation."""
    # Store original values
    original_component = dependencies.sac_component_instance
    original_session_local = dependencies.SessionLocal
    original_api_config = dependencies.api_config

    # Reset to None
    dependencies.sac_component_instance = None
    dependencies.SessionLocal = None
    dependencies.api_config = None

    yield

    # Restore original values
    dependencies.sac_component_instance = original_component
    dependencies.SessionLocal = original_session_local
    dependencies.api_config = original_api_config


@pytest.fixture
def mock_component():
    """Mock WebUIBackendComponent for testing."""
    component = Mock()
    component.gateway_id = "test-gateway"
    component.database_url = "sqlite:///test.db"
    component.identity_service = Mock()
    component.task_context_manager = Mock()
    component.component_config = {"app_config": {"key": "value"}}
    component.data_retention_service = Mock()

    # Mock methods
    component.get_agent_registry.return_value = Mock()
    component.get_sse_manager.return_value = Mock()
    component.get_session_manager.return_value = Mock()
    component.get_namespace.return_value = "test-namespace"
    component.get_gateway_id.return_value = "test-gateway"
    component.get_config_resolver.return_value = Mock()
    component.get_shared_artifact_service.return_value = Mock()
    component.get_embed_config.return_value = {"key": "value"}
    component.get_core_a2a_service.return_value = Mock()
    component.get_task_logger_service.return_value = Mock()
    component.get_config.return_value = "WebUIBackendApp"
    component.publish_a2a = Mock()

    return component


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object."""
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.user = {"id": "test-user", "name": "Test User"}
    return request


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for testing."""
    manager = Mock()
    manager.use_authorization = False
    manager.ensure_a2a_session.return_value = "test-session-123"
    manager.dep_get_client_id.return_value = Mock()
    manager.dep_ensure_session_id.return_value = Mock()
    return manager


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy database session."""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


# Test Classes

class TestGlobalStateManagement:
    """Tests for global state initialization functions."""

    def test_set_component_instance_first_time(self, mock_component):
        """Test setting component instance for the first time."""
        set_component_instance(mock_component)

        assert dependencies.sac_component_instance == mock_component

    def test_set_component_instance_already_set(self, mock_component, caplog):
        """Test warning when component instance is already set."""
        # Set it once
        set_component_instance(mock_component)

        # Try to set it again
        another_component = Mock()
        set_component_instance(another_component)

        # Should log warning and not change
        assert "already set" in caplog.text.lower()
        assert dependencies.sac_component_instance == mock_component

    def test_set_api_config_first_time(self):
        """Test setting API config for the first time."""
        config = {"key": "value", "persistence_enabled": True}
        set_api_config(config)

        assert dependencies.api_config == config

    def test_set_api_config_already_set(self, caplog):
        """Test warning when API config is already set."""
        # Set it once
        config1 = {"key": "value1"}
        set_api_config(config1)

        # Try to set it again
        config2 = {"key": "value2"}
        set_api_config(config2)

        # Should log warning and not change
        assert "already set" in caplog.text.lower()
        assert dependencies.api_config == config1

    @patch('sqlalchemy.event.listens_for')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.create_engine')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.sessionmaker')
    def test_init_database_sqlite(self, mock_sessionmaker, mock_create_engine, mock_listens_for):
        """Test database initialization for SQLite."""
        db_url = "sqlite:///test.db"

        init_database(db_url)

        # Should create engine with SQLite-specific settings
        mock_create_engine.assert_called_once()
        call_kwargs = mock_create_engine.call_args[1]
        assert 'poolclass' in call_kwargs
        assert 'connect_args' in call_kwargs
        assert call_kwargs['connect_args']['check_same_thread'] is False

        # Should create session maker
        mock_sessionmaker.assert_called_once()

        # Should set up event listener for SQLite
        mock_listens_for.assert_called_once()

    @patch('sqlalchemy.event.listens_for')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.create_engine')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.sessionmaker')
    def test_init_database_postgresql(self, mock_sessionmaker, mock_create_engine, mock_listens_for):
        """Test database initialization for PostgreSQL."""
        db_url = "postgresql://user:pass@localhost/db"

        init_database(db_url)

        # Should create engine with PostgreSQL connection pooling
        mock_create_engine.assert_called_once()
        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs['pool_size'] == 10
        assert call_kwargs['max_overflow'] == 20
        assert call_kwargs['pool_pre_ping'] is True

    @patch('sqlalchemy.event.listens_for')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.create_engine')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.sessionmaker')
    def test_init_database_mysql(self, mock_sessionmaker, mock_create_engine, mock_listens_for):
        """Test database initialization for MySQL."""
        db_url = "mysql://user:pass@localhost/db"

        init_database(db_url)

        # Should create engine with MySQL connection pooling
        mock_create_engine.assert_called_once()
        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs['pool_size'] == 10
        assert call_kwargs['pool_pre_ping'] is True

    @patch('sqlalchemy.event.listens_for')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.create_engine')
    @patch('solace_agent_mesh.gateway.http_sse.dependencies.sessionmaker')
    def test_init_database_already_initialized(self, mock_sessionmaker, mock_create_engine, mock_listens_for, caplog):
        """Test warning when database is already initialized."""
        db_url = "sqlite:///test.db"

        # Initialize once
        init_database(db_url)
        mock_create_engine.reset_mock()

        # Try to initialize again
        init_database(db_url)

        # Should log warning and not create engine again
        assert "already initialized" in caplog.text.lower()
        mock_create_engine.assert_not_called()


class TestBasicDependencyGetters:
    """Tests for basic dependency getter functions."""

    def test_get_sac_component_success(self, mock_component):
        """Test getting component when it's set."""
        dependencies.sac_component_instance = mock_component

        result = get_sac_component()

        assert result == mock_component

    def test_get_sac_component_not_initialized(self):
        """Test error when component is not initialized."""
        dependencies.sac_component_instance = None

        with pytest.raises(HTTPException) as exc_info:
            get_sac_component()

        assert exc_info.value.status_code == 503
        assert "not yet initialized" in exc_info.value.detail.lower()

    def test_get_api_config_success(self):
        """Test getting API config when it's set."""
        config = {"key": "value"}
        dependencies.api_config = config

        result = get_api_config()

        assert result == config

    def test_get_api_config_not_initialized(self):
        """Test error when API config is not initialized."""
        dependencies.api_config = None

        with pytest.raises(HTTPException) as exc_info:
            get_api_config()

        assert exc_info.value.status_code == 503
        assert "not yet initialized" in exc_info.value.detail.lower()

    def test_get_agent_registry(self, mock_component):
        """Test getting agent registry from component."""
        expected_registry = Mock()
        mock_component.get_agent_registry.return_value = expected_registry
        dependencies.sac_component_instance = mock_component

        result = get_agent_registry(mock_component)

        assert result == expected_registry
        mock_component.get_agent_registry.assert_called_once()

    def test_get_sse_manager(self, mock_component):
        """Test getting SSE manager from component."""
        expected_manager = Mock()
        mock_component.get_sse_manager.return_value = expected_manager

        result = get_sse_manager(mock_component)

        assert result == expected_manager

    def test_get_session_manager(self, mock_component):
        """Test getting session manager from component."""
        expected_manager = Mock()
        mock_component.get_session_manager.return_value = expected_manager

        result = get_session_manager(mock_component)

        assert result == expected_manager

    def test_get_namespace(self, mock_component):
        """Test getting namespace from component."""
        expected_namespace = "test-namespace"
        mock_component.get_namespace.return_value = expected_namespace

        result = get_namespace(mock_component)

        assert result == expected_namespace

    def test_get_gateway_id(self, mock_component):
        """Test getting gateway ID from component."""
        expected_id = "test-gateway-id"
        mock_component.get_gateway_id.return_value = expected_id

        result = get_gateway_id(mock_component)

        assert result == expected_id

    def test_get_config_resolver(self, mock_component):
        """Test getting config resolver from component."""
        expected_resolver = Mock()
        mock_component.get_config_resolver.return_value = expected_resolver

        result = get_config_resolver(mock_component)

        assert result == expected_resolver

    def test_get_app_config(self, mock_component):
        """Test getting app config from component."""
        mock_component.component_config = {"app_config": {"test": "value"}}

        result = get_app_config(mock_component)

        assert result == {"test": "value"}

    def test_get_app_config_missing(self, mock_component):
        """Test getting app config when it's missing returns empty dict."""
        mock_component.component_config = {}

        result = get_app_config(mock_component)

        assert result == {}

    def test_get_identity_service(self, mock_component):
        """Test getting identity service from component."""
        expected_service = Mock()
        mock_component.identity_service = expected_service

        result = get_identity_service(mock_component)

        assert result == expected_service

    def test_get_identity_service_none(self, mock_component):
        """Test getting identity service when None."""
        mock_component.identity_service = None

        result = get_identity_service(mock_component)

        assert result is None


class TestUserIdExtraction:
    """Tests for user ID extraction logic."""

    def test_get_user_id_from_auth_middleware(self, mock_request, mock_session_manager):
        """Test getting user ID from request.state.user set by AuthMiddleware."""
        mock_request.state.user = {"id": "user-123", "name": "Test User"}

        result = get_user_id(mock_request, mock_session_manager)

        assert result == "user-123"

    def test_get_user_id_missing_id_field(self, mock_request, mock_session_manager, caplog):
        """Test error when user object exists but has no ID field."""
        mock_request.state.user = {"name": "Test User"}  # No 'id' field
        mock_session_manager.use_authorization = False

        result = get_user_id(mock_request, mock_session_manager)

        # Should fall back to development user
        assert result == "sam_dev_user"
        assert "no 'id' field" in caplog.text.lower()

    def test_get_user_id_oauth_enabled_no_user(self, mock_request, mock_session_manager):
        """Test 401 error when OAuth enabled but no authenticated user."""
        mock_request.state.user = None
        mock_session_manager.use_authorization = True

        with pytest.raises(HTTPException) as exc_info:
            get_user_id(mock_request, mock_session_manager)

        assert exc_info.value.status_code == 401
        assert "authentication required" in exc_info.value.detail.lower()

    def test_get_user_id_fallback_dev_user(self, mock_request, mock_session_manager):
        """Test fallback to development user when auth disabled and no user."""
        mock_request.state.user = None
        mock_session_manager.use_authorization = False

        result = get_user_id(mock_request, mock_session_manager)

        assert result == "sam_dev_user"

    def test_ensure_session_id(self, mock_request, mock_session_manager):
        """Test ensuring session ID."""
        expected_session_id = "session-abc-123"
        mock_session_manager.ensure_a2a_session.return_value = expected_session_id

        result = ensure_session_id(mock_request, mock_session_manager)

        assert result == expected_session_id
        mock_session_manager.ensure_a2a_session.assert_called_once_with(mock_request)


class TestDatabaseDependencies:
    """Tests for database-related dependencies."""

    def test_get_db_success(self, mock_db_session):
        """Test getting database session when configured."""
        mock_session_maker = Mock(return_value=mock_db_session)
        dependencies.SessionLocal = mock_session_maker

        # Use generator
        gen = get_db()
        _ = next(gen)

        assert mock_db_session is not None
        # Complete the generator to trigger cleanup
        with contextlib.suppress(StopIteration):
            next(gen)
            pass

        mock_db_session.commit.assert_called_once()
        mock_db_session.close.assert_called_once()

    def test_get_db_not_configured(self):
        """Test error when database is not configured."""
        dependencies.SessionLocal = None

        with pytest.raises(HTTPException) as exc_info:
            gen = get_db()
            next(gen)

        assert exc_info.value.status_code == 501
        assert "database configuration" in exc_info.value.detail.lower()

    def test_get_db_rollback_on_error(self, mock_db_session):
        """Test database rollback on exception."""
        mock_session_maker = Mock(return_value=mock_db_session)
        dependencies.SessionLocal = mock_session_maker

        gen = get_db()
        _ = next(gen)

        # Simulate an error
        try:
            raise ValueError("Test error")
        except ValueError:
            with contextlib.suppress(ValueError):
                gen.throw(ValueError, ValueError("Test error"), None)

        mock_db_session.rollback.assert_called_once()
        mock_db_session.close.assert_called_once()

    def test_get_db_optional_with_database(self, mock_db_session):
        """Test optional database dependency when configured."""
        mock_session_maker = Mock(return_value=mock_db_session)
        dependencies.SessionLocal = mock_session_maker

        gen = get_db_optional()
        result = next(gen)

        assert result == mock_db_session

    def test_get_db_optional_without_database(self):
        """Test optional database dependency when not configured."""
        dependencies.SessionLocal = None

        gen = get_db_optional()
        result = next(gen)

        assert result is None


class TestServiceDependencies:
    """Tests for service dependency getters."""

    def test_get_people_service(self, mock_component):
        """Test getting people service."""
        identity_service = Mock()

        result = get_people_service(identity_service)

        assert result is not None
        # PeopleService is created with the identity service
        assert result._identity_service == identity_service

    def test_get_task_repository(self):
        """Test getting task repository."""
        result = get_task_repository()

        assert result is not None
        # Should return a TaskRepository instance

    def test_get_feedback_service_with_database(self, mock_component):
        """Test getting feedback service when database is configured."""
        dependencies.SessionLocal = Mock()
        mock_component.database_url = "sqlite:///test.db"
        task_repo = Mock()

        result = get_feedback_service(mock_component, task_repo)

        assert result is not None

    def test_get_feedback_service_without_database(self, mock_component):
        """Test getting feedback service when database is not configured."""
        dependencies.SessionLocal = None
        mock_component.database_url = None
        task_repo = Mock()

        result = get_feedback_service(mock_component, task_repo)

        assert result is not None

    def test_get_data_retention_service_success(self, mock_component):
        """Test getting data retention service when configured."""
        mock_service = Mock()
        mock_component.database_url = "sqlite:///test.db"
        mock_component.data_retention_service = mock_service

        result = get_data_retention_service(mock_component)

        assert result == mock_service

    def test_get_data_retention_service_no_database(self, mock_component):
        """Test getting data retention service when no database."""
        mock_component.database_url = None

        result = get_data_retention_service(mock_component)

        assert result is None

    def test_get_data_retention_service_not_initialized(self, mock_component):
        """Test getting data retention service when not initialized."""
        mock_component.database_url = "sqlite:///test.db"
        mock_component.data_retention_service = None

        result = get_data_retention_service(mock_component)

        assert result is None

    def test_get_task_logger_service_success(self, mock_component):
        """Test getting task logger service when available."""
        expected_service = Mock()
        mock_component.get_task_logger_service.return_value = expected_service

        result = get_task_logger_service(mock_component)

        assert result == expected_service

    def test_get_task_logger_service_not_available(self, mock_component):
        """Test error when task logger service is not available."""
        mock_component.get_task_logger_service.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_logger_service(mock_component)

        assert exc_info.value.status_code == 503
        assert "not configured" in exc_info.value.detail.lower()

    def test_get_publish_a2a_func(self, mock_component):
        """Test getting publish A2A function."""
        expected_func = Mock()
        mock_component.publish_a2a = expected_func

        result = get_publish_a2a_func(mock_component)

        assert result == expected_func

    def test_get_shared_artifact_service(self, mock_component):
        """Test getting shared artifact service."""
        expected_service = Mock()
        mock_component.get_shared_artifact_service.return_value = expected_service

        result = get_shared_artifact_service(mock_component)

        assert result == expected_service

    def test_get_embed_config(self, mock_component):
        """Test getting embed config."""
        expected_config = {"embed_key": "value"}
        mock_component.get_embed_config.return_value = expected_config

        result = get_embed_config(mock_component)

        assert result == expected_config

    def test_get_core_a2a_service_success(self, mock_component):
        """Test getting core A2A service when available."""
        expected_service = Mock()
        mock_component.get_core_a2a_service.return_value = expected_service

        result = get_core_a2a_service(mock_component)

        assert result == expected_service

    def test_get_core_a2a_service_not_ready(self, mock_component):
        """Test error when core A2A service is not ready."""
        mock_component.get_core_a2a_service.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_core_a2a_service(mock_component)

        assert exc_info.value.status_code == 503
        assert "not ready" in exc_info.value.detail.lower()

    def test_get_task_context_manager_success(self, mock_component):
        """Test getting task context manager when available."""
        expected_manager = Mock()
        mock_component.task_context_manager = expected_manager

        result = get_task_context_manager_from_component(mock_component)

        assert result == expected_manager

    def test_get_task_context_manager_not_ready(self, mock_component):
        """Test error when task context manager is not ready."""
        mock_component.task_context_manager = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_context_manager_from_component(mock_component)

        assert exc_info.value.status_code == 503
        assert "not ready" in exc_info.value.detail.lower()

    def test_get_agent_card_service(self, mock_component):
        """Test getting agent card service."""
        from solace_agent_mesh.common.agent_registry import AgentRegistry

        # Create a proper mock with the correct spec to pass isinstance check
        registry = Mock(spec=AgentRegistry)

        result = get_agent_card_service(registry)

        assert result is not None
        # AgentCardService is created with the registry

    def test_get_task_service(self, mock_component):
        """Test getting task service with all dependencies."""
        from solace_agent_mesh.core_a2a.service import CoreA2AService
        from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager

        # Create proper mocks with the correct specs to pass isinstance checks
        core_service = Mock(spec=CoreA2AService)
        publish_func = Mock()
        namespace = "test-namespace"
        gateway_id = "test-gateway"
        sse_manager = Mock(spec=SSEManager)
        task_context_manager = Mock()
        task_context_manager._contexts = {}
        task_context_manager._lock = Mock()
        mock_component.get_config.return_value = "TestApp"

        result = get_task_service(
            core_service,
            publish_func,
            namespace,
            gateway_id,
            sse_manager,
            task_context_manager,
            mock_component,
        )

        assert result is not None

    def test_get_session_business_service(self, mock_component):
        """Test getting session business service."""
        result = get_session_business_service(mock_component)

        assert result is not None

    def test_get_project_service(self, mock_component):
        """Test getting project service."""
        result = get_project_service(mock_component)

        assert result is not None

    def test_get_project_service_optional_with_db(self, mock_component):
        """Test getting optional project service when database configured."""
        dependencies.SessionLocal = Mock()

        result = get_project_service_optional(mock_component)

        assert result is not None

    def test_get_project_service_optional_without_db(self, mock_component):
        """Test getting optional project service when no database."""
        dependencies.SessionLocal = None

        result = get_project_service_optional(mock_component)

        assert result is None

    def test_get_session_business_service_optional_with_db(self, mock_component):
        """Test getting optional session service when database configured."""
        dependencies.SessionLocal = Mock()

        result = get_session_business_service_optional(mock_component)

        assert result is not None

    def test_get_session_business_service_optional_without_db(self, mock_component):
        """Test getting optional session service when no database."""
        dependencies.SessionLocal = None

        result = get_session_business_service_optional(mock_component)

        assert result is None


class TestUserConfig:
    """Tests for user config functionality."""

    @pytest.mark.asyncio
    async def test_get_user_config(self, mock_request, mock_component):
        """Test getting user config asynchronously."""
        user_id = "test-user"
        config_resolver = Mock()
        config_resolver.resolve_user_config = AsyncMock(return_value={"user": "config"})
        app_config = {"app": "config"}

        result = await get_user_config(
            mock_request,
            user_id,
            config_resolver,
            mock_component,
            app_config,
        )

        assert result == {"user": "config"}
        config_resolver.resolve_user_config.assert_called_once()


class TestValidatedUserConfig:
    """Tests for ValidatedUserConfig class."""

    def test_validated_user_config_init(self):
        """Test initializing ValidatedUserConfig with scopes."""
        required_scopes = ["scope1", "scope2"]

        validator = ValidatedUserConfig(required_scopes)

        assert validator.required_scopes == required_scopes

    @pytest.mark.asyncio
    async def test_validated_user_config_authorized(self, mock_request):
        """Test ValidatedUserConfig allows access when scopes match."""
        config_resolver = Mock()
        config_resolver.is_feature_enabled.return_value = True
        user_config = {"user_profile": {"id": "test-user"}}

        validator = ValidatedUserConfig(["scope1"])
        result = await validator(mock_request, config_resolver, user_config)

        assert result == user_config

    @pytest.mark.asyncio
    async def test_validated_user_config_unauthorized(self, mock_request):
        """Test ValidatedUserConfig raises 403 when scopes don't match."""
        config_resolver = Mock()
        config_resolver.is_feature_enabled.return_value = False
        user_config = {"user_profile": {"id": "test-user"}}

        validator = ValidatedUserConfig(["scope1", "scope2"])

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request, config_resolver, user_config)

        assert exc_info.value.status_code == 403
        assert "not authorized" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validated_user_config_no_user_id(self, mock_request):
        """Test ValidatedUserConfig handles missing user ID."""
        config_resolver = Mock()
        config_resolver.is_feature_enabled.return_value = False
        user_config = {"user_profile": {}}  # No 'id' field

        validator = ValidatedUserConfig(["scope1"])

        with pytest.raises(HTTPException) as exc_info:
            await validator(mock_request, config_resolver, user_config)

        assert exc_info.value.status_code == 403


class TestSessionValidator:
    """Tests for session validation functionality."""

    def test_get_session_validator_with_database(self, mock_component):
        """Test getting session validator when database is configured."""
        dependencies.SessionLocal = Mock()

        result = get_session_validator(mock_component)

        assert callable(result)

    def test_get_session_validator_without_database(self, mock_component):
        """Test getting session validator when no database."""
        dependencies.SessionLocal = None

        result = get_session_validator(mock_component)

        assert callable(result)

    def test_session_validator_with_db_valid_session(self, mock_component):
        """Test database-backed session validation for valid session."""
        mock_session = Mock()
        mock_session_maker = Mock(return_value=mock_session)
        dependencies.SessionLocal = mock_session_maker

        with patch('solace_agent_mesh.gateway.http_sse.dependencies.SessionRepository') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.find_user_session.return_value = Mock()  # Session exists
            mock_repo_class.return_value = mock_repo

            validator = get_session_validator(mock_component)
            result = validator("session-123", "user-456")

            assert result is True
            mock_session.close.assert_called_once()

    def test_session_validator_with_db_invalid_session(self, mock_component):
        """Test database-backed session validation for invalid session."""
        mock_session = Mock()
        mock_session_maker = Mock(return_value=mock_session)
        dependencies.SessionLocal = mock_session_maker

        with patch('solace_agent_mesh.gateway.http_sse.dependencies.SessionRepository') as mock_repo_class:
            mock_repo = Mock()
            mock_repo.find_user_session.return_value = None  # Session doesn't exist
            mock_repo_class.return_value = mock_repo

            validator = get_session_validator(mock_component)
            result = validator("session-123", "user-456")

            assert result is False

    def test_session_validator_with_db_exception(self, mock_component):
        """Test database-backed session validation handles exceptions."""
        mock_session_maker = Mock(side_effect=Exception("DB error"))
        dependencies.SessionLocal = mock_session_maker

        validator = get_session_validator(mock_component)
        result = validator("session-123", "user-456")

        assert result is False

    def test_session_validator_without_db_valid_format(self, mock_component):
        """Test basic session validation for valid format."""
        dependencies.SessionLocal = None

        validator = get_session_validator(mock_component)
        result = validator("web-session-abc123", "user-456")

        assert result is True

    def test_session_validator_without_db_invalid_format(self, mock_component):
        """Test basic session validation for invalid format."""
        dependencies.SessionLocal = None

        validator = get_session_validator(mock_component)

        # Test invalid session ID format
        assert validator("invalid-session", "user-456") is False
        # Test empty session ID
        assert validator("", "user-456") is False
        # Test None session ID
        assert validator(None, "user-456") is False
        # Test missing user ID
        assert validator("web-session-abc123", "") is False


class TestCallableDependencies:
    """Tests for callable-returning dependencies."""

    def test_get_user_id_callable(self, mock_session_manager):
        """Test getting user ID callable."""
        expected_callable = Mock()
        mock_session_manager.dep_get_client_id.return_value = expected_callable

        result = get_user_id_callable(mock_session_manager)

        assert result == expected_callable

    def test_ensure_session_id_callable(self, mock_session_manager):
        """Test getting ensure session ID callable."""
        expected_callable = Mock()
        mock_session_manager.dep_ensure_session_id.return_value = expected_callable

        result = ensure_session_id_callable(mock_session_manager)

        assert result == expected_callable
