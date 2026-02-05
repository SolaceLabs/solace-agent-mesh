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

from solace_agent_mesh.services.platform.component import PlatformServiceComponent

log = logging.getLogger(__name__)


class PlatformServiceFactory:
    """
    Creates and configures a FastAPI application instance for testing the Platform Service.

    This factory class encapsulates the logic for setting up a test-ready
    version of the Platform Service FastAPI application, including mock dependencies
    and a test database. It ensures all routers (community and enterprise) are
    correctly registered when available.
    """

    def __init__(
        self, db_url: str = None, service_id: str = "test-platform", user: dict = None
    ):
        self._temp_dir = None
        if db_url is None:
            self._temp_dir = tempfile.TemporaryDirectory()
            db_path = (
                Path(self._temp_dir.name) / f"test_platform_{uuid.uuid4().hex}.db"
            )
            db_url = f"sqlite:///{db_path}"

        if db_url.startswith("sqlite"):
            db_file_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
            if db_file_path:
                db_path_obj = Path(db_file_path)
                parent_dir = db_path_obj.parent
                if parent_dir and str(parent_dir) != ".":
                    parent_dir.mkdir(parents=True, exist_ok=True)
                    log.info(f"[PlatformServiceFactory] Ensured parent directory exists: {parent_dir}")

        mock_component = Mock(spec=PlatformServiceComponent)

        def mock_get_config(key, default=None):
            config_values = {
                "frontend_use_authorization": False,
            }
            return config_values.get(key, default)

        mock_component.get_config.side_effect = mock_get_config
        mock_component.get_cors_origins.return_value = ["*"]
        mock_component.service_id = service_id
        mock_component.log_identifier = f"[{service_id}]"
        mock_component.namespace = "test_namespace"
        mock_component.external_auth_service_url = ""
        mock_component.external_auth_provider = "generic"

        mock_session_manager = Mock()
        mock_component.get_session_manager.return_value = mock_session_manager

        mock_config_resolver = Mock()
        mock_config_resolver.resolve_user_config = AsyncMock(return_value={})
        mock_component.get_config_resolver.return_value = mock_config_resolver

        mock_heartbeat_tracker = Mock()
        mock_heartbeat_tracker.is_deployer_alive.return_value = True
        mock_heartbeat_tracker.get_last_heartbeat.return_value = None
        mock_component.get_heartbeat_tracker.return_value = mock_heartbeat_tracker
        mock_component.heartbeat_tracker = mock_heartbeat_tracker

        mock_agent_registry = Mock()
        mock_agent_registry.get_all_agents.return_value = []
        mock_agent_registry.get_agent.return_value = None
        mock_component.get_agent_registry.return_value = mock_agent_registry
        mock_component.agent_registry = mock_agent_registry

        async def mock_publish_a2a(*args, **kwargs):
            pass

        mock_component.publish_a2a = AsyncMock(side_effect=mock_publish_a2a)

        if user is None:
            user = {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }
        mock_component._factory_user = user

        if db_url.startswith("sqlite"):
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
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
            )

        Session = sessionmaker(bind=engine)

        mock_component.database_url = db_url

        self.app = FastAPI(
            title=f"Platform Service API (Test - {service_id})",
            version="1.0.0-test",
            description="Independent test instance for the Platform Service API",
        )

        self.mock_component = mock_component
        self.db_url = db_url
        self.engine = engine
        self.Session = Session

        self._setup_independent_app(mock_component, db_url)

    def _setup_independent_app(self, component, database_url: str):
        """Set up the FastAPI app by reusing patterns from Platform Service main.py."""
        from solace_agent_mesh.services.platform.api import dependencies

        original_session_local = getattr(dependencies, "PlatformSessionLocal", None)
        original_component = getattr(dependencies, "platform_component_instance", None)

        dependencies.PlatformSessionLocal = self.Session
        dependencies.platform_component_instance = component
        log.info("[PlatformServiceFactory] Platform database initialized with shared engine")

        self._run_migrations(database_url)

        try:
            self._setup_middleware(component)
            self._setup_routers()
        finally:
            if original_session_local is not None:
                dependencies.PlatformSessionLocal = original_session_local
            if original_component is not None:
                dependencies.platform_component_instance = original_component

        self._setup_dependency_overrides(component)
        self._setup_exception_handlers()

    def _run_migrations(self, database_url: str):
        """Run database migrations for Platform Service."""
        try:
            from solace_agent_mesh.services.platform.api.main import (
                _run_enterprise_migrations,
            )

            log.info("[PlatformServiceFactory] Running enterprise platform migrations...")
            _run_enterprise_migrations(database_url)
            log.info("[PlatformServiceFactory] Enterprise platform migrations completed")
        except ImportError:
            log.info("[PlatformServiceFactory] Enterprise package not available - skipping enterprise migrations")
        except Exception as e:
            log.warning(f"[PlatformServiceFactory] Migration error (non-fatal): {e}")

    def _setup_middleware(self, component):
        """Add middleware to the FastAPI application."""
        from fastapi.middleware.cors import CORSMiddleware

        allowed_origins = component.get_cors_origins()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        log.info(f"[PlatformServiceFactory] CORS middleware added with origins: {allowed_origins}")

    def _setup_routers(self):
        """Mount community and enterprise routers to the FastAPI application."""
        PLATFORM_SERVICE_PREFIX = "/api/v1/platform"

        from solace_agent_mesh.services.platform.api.routers import get_community_platform_routers

        community_routers = get_community_platform_routers()
        for router_config in community_routers:
            self.app.include_router(
                router_config["router"],
                prefix=PLATFORM_SERVICE_PREFIX,
                tags=router_config["tags"],
            )
        log.info(f"[PlatformServiceFactory] Mounted {len(community_routers)} community platform routers")

        try:
            from solace_agent_mesh_enterprise.platform_service.routers import get_enterprise_routers

            enterprise_routers = get_enterprise_routers()
            for router_config in enterprise_routers:
                self.app.include_router(
                    router_config["router"],
                    prefix=PLATFORM_SERVICE_PREFIX,
                    tags=router_config["tags"],
                )
            log.info(f"[PlatformServiceFactory] Mounted {len(enterprise_routers)} enterprise platform routers")
        except ImportError:
            log.info("[PlatformServiceFactory] No enterprise package detected - running in community mode")
        except Exception as e:
            log.warning(f"[PlatformServiceFactory] Failed to load enterprise routers: {e}")

    def _setup_dependency_overrides(self, component):
        """Set up FastAPI dependency overrides for testing."""
        from solace_agent_mesh.services.platform.api.dependencies import (
            get_platform_db,
            get_heartbeat_tracker,
            get_agent_registry,
        )
        from solace_agent_mesh.shared.auth.dependencies import get_current_user

        def override_get_current_user():
            if hasattr(component, "_factory_user"):
                return component._factory_user
            return {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }

        def override_get_platform_db():
            db = self.Session()
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        def override_get_heartbeat_tracker():
            return component.get_heartbeat_tracker()

        def override_get_agent_registry():
            return component.get_agent_registry()

        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.app.dependency_overrides[get_platform_db] = override_get_platform_db
        self.app.dependency_overrides[get_heartbeat_tracker] = override_get_heartbeat_tracker
        self.app.dependency_overrides[get_agent_registry] = override_get_agent_registry

        log.info("[PlatformServiceFactory] Dependency overrides configured")

    def _setup_exception_handlers(self):
        """Set up exception handlers for the FastAPI application."""
        from fastapi.responses import JSONResponse

        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail}
            )

        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request, exc):
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc)}
            )

        @self.app.exception_handler(Exception)
        async def generic_exception_handler(request, exc):
            log.error(f"Unhandled exception: {exc}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

    def setup_multi_user_testing(self, provider=None, test_user_header: str = "X-Test-User-Id"):
        """
        Set up additional dependency overrides for multi-user testing.

        Args:
            provider: Database provider instance (optional, for advanced session validation)
            test_user_header: Header name used to identify test user
        """
        from fastapi import Request
        from solace_agent_mesh.shared.auth.dependencies import get_current_user

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
            return {
                "id": "sam_dev_user",
                "name": "Sam Dev User",
                "email": "sam@dev.local",
                "authenticated": True,
                "auth_method": "development",
            }

        self.app.dependency_overrides[get_current_user] = override_get_current_user
        log.info("[PlatformServiceFactory] Multi-user testing overrides configured")

    def teardown(self):
        """Clean up resources."""
        self.app.dependency_overrides = {}
        if self._temp_dir:
            self._temp_dir.cleanup()
