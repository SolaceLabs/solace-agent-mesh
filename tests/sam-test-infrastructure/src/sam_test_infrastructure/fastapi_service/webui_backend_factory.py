import logging
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from solace_agent_mesh.core_a2a.service import CoreA2AService
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from solace_agent_mesh.gateway.http_sse.dependencies import get_session_business_service
from solace_agent_mesh.gateway.http_sse.services.data_retention_service import (
    DataRetentionService,
)
from solace_agent_mesh.gateway.http_sse.services.session_service import SessionService
from solace_agent_mesh.gateway.http_sse.services.task_logger_service import (
    TaskLoggerService,
)
from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager

log = logging.getLogger(__name__)


class WebUIBackendFactory:
    """
    Creates and configures a FastAPI application instance for testing the WebUI backend.
    This factory class encapsulates the logic for setting up a test-ready
    version of the main FastAPI application, including mock dependencies and
    a test database. It ensures all routers are correctly registered.
    """

    def __init__(
        self, db_url: str = None, gateway_id: str = "test-gateway", user: dict = None
    ):
        self._temp_dir = None
        if db_url is None:
            # If no database URL is provided, create a temporary SQLite DB for isolation.
            self._temp_dir = tempfile.TemporaryDirectory()
            db_path = (
                Path(self._temp_dir.name) / f"test_webui_gateway_{uuid.uuid4().hex}.db"
            )
            db_url = f"sqlite:///{db_path}"

        # Ensure parent directory exists for SQLite databases
        if db_url.startswith("sqlite"):
            # Extract file path from SQLite URL
            db_file_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
            if db_file_path:  # Only process non-empty paths
                db_path_obj = Path(db_file_path)
                parent_dir = db_path_obj.parent
                if parent_dir and str(parent_dir) != ".":
                    parent_dir.mkdir(parents=True, exist_ok=True)
                    log.info(f"[WebUIBackendFactory] Ensured parent directory exists: {parent_dir}")

        # Create a mock WebUIBackendComponent
        mock_component = Mock(spec=WebUIBackendComponent)
        mock_component.get_app.return_value = Mock(
            app_config={
                "frontend_use_authorization": False,
                "external_auth_service_url": "http://localhost:8080",
                "external_auth_callback_uri": "http://localhost:8000/api/v1/auth/callback",
                "external_auth_provider": "azure",
                "frontend_redirect_url": "http://localhost:3000",
            }
        )
        mock_component.get_cors_origins.return_value = ["*"]
        mock_session_manager = Mock(secret_key="test-secret-key")
        mock_session_manager.create_new_session_id.side_effect = (
            lambda *args: f"test-session-{uuid.uuid4().hex[:8]}"
        )
        mock_component.get_session_manager.return_value = mock_session_manager
        mock_component.identity_service = None
        mock_component.gateway_id = gateway_id
        mock_component.log_identifier = f"[{gateway_id}]"

        # Mock authentication method - use same user ID as default auth middleware
        if user is None:
            user = {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }
        mock_component.authenticate_and_enrich_user = AsyncMock(return_value=user)
        mock_component.task_context_manager = Mock()
        mock_component.component_config = {"app_config": {}}
        # Store the user info on the component for dependency overrides
        mock_component._factory_user = user

        # Mock the config resolver to handle async user config resolution
        mock_config_resolver = Mock()
        mock_config_resolver.resolve_user_config = AsyncMock(return_value={})
        mock_component.get_config_resolver.return_value = mock_config_resolver

        # Mock the A2A task submission to return just the task ID string
        async def mock_submit_task(*args, **kwargs):
            return f"task-{uuid.uuid4().hex[:8]}"

        mock_component.submit_a2a_task = AsyncMock(side_effect=mock_submit_task)

        # Create a mock CoreA2AService instance for task cancellation tests
        mock_core_a2a_service = Mock(spec=CoreA2AService)

        def mock_cancel_task_service(agent_name, task_id, client_id, user_id):
            target_topic = f"test_namespace/a2a/v1/agent/cancel/{agent_name}"
            payload = {
                "jsonrpc": "2.0",
                "id": f"cancel-{task_id}",
                "method": "tasks/cancel",
                "params": {"id": task_id},
            }
            user_properties = {"userId": user_id}
            return target_topic, payload, user_properties

        mock_core_a2a_service.cancel_task = mock_cancel_task_service
        mock_component.get_core_a2a_service.return_value = mock_core_a2a_service

        # Create a mock SSEManager instance
        mock_sse_manager = Mock(spec=SSEManager)
        mock_component.get_sse_manager.return_value = mock_sse_manager

        # Create a test database engine and session factory with database-specific settings
        if db_url.startswith("sqlite"):
            # SQLite-specific configuration
            engine = create_engine(
                db_url,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        else:
            # PostgreSQL/MySQL configuration - no SQLite-specific arguments
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
            )

        Session = sessionmaker(bind=engine)

        # Create real instances of services required for persistence tests
        task_logger_config = {"enabled": True}
        real_task_logger_service = TaskLoggerService(
            session_factory=Session, config=task_logger_config
        )
        mock_component.get_task_logger_service.return_value = real_task_logger_service

        data_retention_config = {
            "enabled": True,
            "task_retention_days": 90,
            "feedback_retention_days": 90,
            "cleanup_interval_hours": 24,
            "batch_size": 1000,
        }
        real_data_retention_service = DataRetentionService(
            session_factory=Session, config=data_retention_config
        )
        mock_component.data_retention_service = real_data_retention_service

        # Add the database_url attribute that the tests expect
        mock_component.database_url = db_url

        # Create a real SessionService and attach it to the mock component
        mock_component.session_service = SessionService(component=mock_component)

        # Create a completely independent FastAPI app instance instead of using the global singleton
        self.app = FastAPI(
            title=f"A2A Web UI Backend (Test - {gateway_id})",
            version="1.0.0-test",
            description="Independent test instance for the A2A Web UI Backend",
        )

        # Store references before setting up the app
        self.mock_component = mock_component
        self.db_url = db_url
        self.engine = engine
        self.Session = Session

        # Set up the independent app with all necessary components
        self._setup_independent_app(mock_component, db_url)

    def _setup_independent_app(self, component, database_url: str):
        """Set up the FastAPI app by importing and reusing functions from main.py."""

        # Import the setup functions from main.py
        from solace_agent_mesh.gateway.http_sse import dependencies
        from solace_agent_mesh.gateway.http_sse.main import (
            _create_api_config,
            _get_app_config,
            _run_community_migrations,
            _run_enterprise_migrations,
            _setup_middleware,
            _setup_routers,
            generic_exception_handler,
            http_exception_handler,
            validation_exception_handler,
        )

        # Set up database - use the engine and Session we already created
        # instead of having _setup_database create a new one
        dependencies.SessionLocal = self.Session
        dependencies.sac_component_instance = component
        log.info("[WebUIBackendFactory] Database initialized with shared engine")
        log.info("Running database migrations...")
        _run_community_migrations(database_url)
        _run_enterprise_migrations(component, database_url)

        # Set up API config
        app_config = _get_app_config(component)
        api_config_dict = _create_api_config(app_config, database_url)

        # Store original dependencies state
        original_component = getattr(dependencies, "_component_instance", None)
        original_api_config = getattr(dependencies, "api_config", None)

        try:
            # Temporarily set dependencies for setup
            dependencies.set_component_instance(component)
            dependencies.set_api_config(api_config_dict)

            # Temporarily replace the global app in main.py with our app
            # so the setup functions work on our independent app
            import solace_agent_mesh.gateway.http_sse.main as main_module

            original_app = main_module.app
            main_module.app = self.app

            try:
                # Set up middleware and routers using the existing functions
                _setup_middleware(component)
                _setup_routers()
            finally:
                # Restore the original global app
                main_module.app = original_app
        finally:
            # Restore original dependencies state to avoid polluting global state
            if original_component is not None:
                dependencies.set_component_instance(original_component)
            if original_api_config is not None:
                dependencies.set_api_config(original_api_config)

        # Set up independent dependency overrides on our app that don't rely on global state
        def override_get_current_user():
            # Return the user configured for this specific factory
            if hasattr(component, "_factory_user"):
                return component._factory_user
            return {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }

        def override_get_user_id():
            user = override_get_current_user()
            return user.get("id", "sam_dev_user")

        def override_get_sac_component():
            return component

        def override_get_session_service() -> SessionService:
            return component.session_service

        def override_get_db():
            # Return a database session from THIS factory's Session, not the global one
            db = self.Session()
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        # Import the dependency functions and override them on our specific app
        from solace_agent_mesh.gateway.http_sse.dependencies import (
            get_db,
            get_sac_component,
            get_user_id,
        )
        from solace_agent_mesh.gateway.http_sse.shared.auth_utils import (
            get_current_user,
        )

        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.app.dependency_overrides[get_user_id] = override_get_user_id
        self.app.dependency_overrides[get_sac_component] = override_get_sac_component
        self.app.dependency_overrides[get_session_business_service] = (
            override_get_session_service
        )
        self.app.dependency_overrides[get_db] = override_get_db

        # Set up exception handlers using the imported handlers
        self.app.add_exception_handler(HTTPException, http_exception_handler)
        self.app.add_exception_handler(
            RequestValidationError, validation_exception_handler
        )
        self.app.add_exception_handler(Exception, generic_exception_handler)

    def setup_multi_user_testing(self, provider, test_user_header: str = "X-Test-User-Id"):
        """
        Set up additional dependency overrides for multi-user testing.

        This method should be called after factory creation to enable:
        - Header-based user identification for multi-user tests
        - Test database overrides for optional dependencies
        - Session validation using test database

        Args:
            provider: Database provider instance (needed for session validation)
            test_user_header: Header name used to identify test user
        """
        from fastapi import Request
        from sqlalchemy.orm import sessionmaker
        from solace_agent_mesh.gateway.http_sse.dependencies import (
            get_user_id,
            get_db_optional,
            get_feedback_service,
            get_task_repository,
            get_sac_component,
            get_task_logger_service,
            get_session_validator,
        )
        from solace_agent_mesh.gateway.http_sse.shared.auth_utils import get_current_user
        from solace_agent_mesh.gateway.http_sse.services.feedback_service import FeedbackService
        from solace_agent_mesh.gateway.http_sse.services.task_logger_service import TaskLoggerService
        from solace_agent_mesh.gateway.http_sse.repository import SessionRepository

        # Multi-user auth overrides that read from test header
        async def override_get_current_user(request: Request) -> dict:
            user_id = request.headers.get(test_user_header, "sam_dev_user")
            if user_id == "secondary_user":
                return {
                    "id": "secondary_user",
                    "name": "Secondary User",
                    "email": "secondary@dev.local",
                    "authenticated": True,
                    "auth_method": "development",
                }
            else:
                return {
                    "id": "sam_dev_user",
                    "name": "Sam Dev User",
                    "email": "sam@dev.local",
                    "authenticated": True,
                    "auth_method": "development",
                }

        def override_get_user_id(request: Request) -> str:
            return request.headers.get(test_user_header, "sam_dev_user")

        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.app.dependency_overrides[get_user_id] = override_get_user_id

        # Override for get_db_optional to use the test database
        def override_get_db_optional():
            """Override to use factory's Session for optional DB dependency."""
            db = self.Session()
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        self.app.dependency_overrides[get_db_optional] = override_get_db_optional

        # Override for get_feedback_service to use the test database
        def override_get_feedback_service():
            """Override to use factory's Session for FeedbackService."""
            # Call get_sac_component() directly so test patches are picked up
            component = get_sac_component()
            task_repo = get_task_repository()

            return FeedbackService(
                session_factory=self.Session,  # Use test database
                component=component,  # Will have test patches applied
                task_repo=task_repo
            )

        self.app.dependency_overrides[get_feedback_service] = override_get_feedback_service

        # Override for get_task_logger_service to use the test database
        def override_get_task_logger_service():
            """Override to use factory's Session for TaskLoggerService."""
            # Get component via dependency to pick up test patches
            component = get_sac_component()

            # Get task logging config from component
            task_logging_config = component.get_config("task_logging", {})

            return TaskLoggerService(
                session_factory=self.Session,  # Use test database
                config=task_logging_config
            )

        self.app.dependency_overrides[get_task_logger_service] = override_get_task_logger_service

        # Override for session validator to use the test database
        def override_get_session_validator():
            """Override to use test database's Session factory for validation."""
            def validate_with_test_database(session_id: str, user_id: str) -> bool:
                try:
                    # Use the provider's engine to get a session from the same database
                    db = provider.get_sync_gateway_engine().connect()
                    try:
                        from sqlalchemy.orm import Session as SQLASession
                        # Create an ORM session from the connection
                        session_maker = sessionmaker(bind=db)
                        orm_session = session_maker()
                        try:
                            session_repository = SessionRepository()
                            session_domain = session_repository.find_user_session(
                                orm_session, session_id, user_id
                            )
                            return session_domain is not None
                        finally:
                            orm_session.close()
                    finally:
                        db.close()
                except Exception as e:
                    log.error(f"Session validation error: {e}")
                    return False
            return validate_with_test_database

        self.app.dependency_overrides[get_session_validator] = override_get_session_validator

        log.info("[WebUIBackendFactory] Multi-user testing overrides configured")

    def teardown(self):
        # Clean up dependency overrides from our independent app
        self.app.dependency_overrides = {}
        if self._temp_dir:
            self._temp_dir.cleanup()
