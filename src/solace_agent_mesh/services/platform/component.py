"""
Platform Service Component for Solace Agent Mesh.
Hosts the FastAPI REST API server for platform configuration management.
"""

import logging
import threading

import uvicorn
from solace_ai_connector.components.component_base import ComponentBase
from solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

log = logging.getLogger(__name__)


class _StubSessionManager:
    """
    Minimal stub for SessionManager to satisfy gateway dependencies.

    Platform service doesn't have sessions, but webui_backend routers
    expect a SessionManager for user_id resolution. This stub provides
    just enough to make get_user_id work when OAuth middleware sets
    request.state.user.
    """
    def __init__(self, use_authorization: bool):
        self.use_authorization = use_authorization


info = {
    "class_name": "PlatformServiceComponent",
    "description": (
        "Platform Service Component - REST API for platform configuration management. "
        "NOT a gateway - no session management, no A2A communication, no artifacts."
    ),
}


class PlatformServiceComponent(ComponentBase):
    """
    Platform Service Component

    Key characteristics:
    - Pure REST API with CRUD operations on platform database
    """

    def __init__(self, **kwargs):
        """
        Initialize the PlatformServiceComponent.

        Retrieves configuration, initializes FastAPI server state,
        and starts the FastAPI/Uvicorn server.
        """
        super().__init__(info, **kwargs)
        log.info("%s Initializing Platform Service Component...", self.log_identifier)

        try:
            # Retrieve configuration
            self.namespace = self.get_config("namespace")
            self.database_url = self.get_config("database_url")
            self.fastapi_host = self.get_config("fastapi_host", "127.0.0.1")
            self.fastapi_port = int(self.get_config("fastapi_port", 8001))
            self.cors_allowed_origins = self.get_config("cors_allowed_origins", ["*"])

            # OAuth2 configuration
            self.external_auth_service_url = self.get_config("external_auth_service_url")
            self.external_auth_provider = self.get_config("external_auth_provider", "azure")
            self.use_authorization = self.get_config("use_authorization", True)

            log.info(
                "%s Platform service configuration retrieved (Host: %s, Port: %d, Auth: %s).",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
                "enabled" if self.use_authorization else "disabled",
            )
        except Exception as e:
            log.error("%s Failed to retrieve configuration: %s", self.log_identifier, e)
            raise ValueError(f"Configuration retrieval error: {e}") from e

        # FastAPI server state (initialized later)
        self.fastapi_app = None
        self.uvicorn_server = None
        self.fastapi_thread = None

        # Config resolver (permissive default - allows all features/scopes)
        self.config_resolver = ConfigResolver()

        # Gateway compatibility attributes
        # These allow webui_backend routers (designed for gateway) to work with platform service
        # self.component_config = {"app_config": {}}
        self.session_manager = _StubSessionManager(use_authorization=self.use_authorization)

        log.info("%s Platform Service Component initialized.", self.log_identifier)

        # Start FastAPI server
        self._start_fastapi_server()

    def _start_fastapi_server(self):
        """
        Start the FastAPI/Uvicorn server in a separate background thread.

        This method:
        1. Runs enterprise platform migrations if available
        2. Imports the FastAPI app and setup function
        3. Calls setup_dependencies to initialize DB, middleware, and routers
        4. Creates uvicorn.Config and uvicorn.Server
        5. Starts the server in a daemon thread
        """
        log.info(
            "%s Attempting to start FastAPI/Uvicorn server...",
            self.log_identifier,
        )

        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.warning(
                "%s FastAPI server thread already started.", self.log_identifier
            )
            return

        try:
            # Import FastAPI app and setup function
            from .api.main import app as fastapi_app_instance
            from .api.main import setup_dependencies

            self.fastapi_app = fastapi_app_instance

            # Setup dependencies (idempotent - safe to call multiple times)
            setup_dependencies(self, self.database_url)

            # Create uvicorn configuration
            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.fastapi_host,
                port=self.fastapi_port,
                log_level="warning",
                lifespan="on",
                log_config=None,
            )
            self.uvicorn_server = uvicorn.Server(config)

            # Start server in background thread
            self.fastapi_thread = threading.Thread(
                target=self.uvicorn_server.run,
                daemon=True,
                name="PlatformService_FastAPI_Thread",
            )
            self.fastapi_thread.start()
            log.info(
                "%s FastAPI/Uvicorn server starting in background thread on http://%s:%d",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
            )

        except Exception as e:
            log.error(
                "%s Failed to start FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            raise

    def cleanup(self):
        """
        Gracefully shut down the Platform Service Component.

        This method:
        1. Signals the uvicorn server to exit
        2. Waits for the FastAPI thread to finish
        3. Calls parent cleanup
        """
        log.info("%s Cleaning up Platform Service Component...", self.log_identifier)

        # Signal uvicorn to shutdown
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True

        # Wait for FastAPI thread to exit
        if self.fastapi_thread and self.fastapi_thread.is_alive():
            log.info(
                "%s Waiting for FastAPI server thread to exit...", self.log_identifier
            )
            self.fastapi_thread.join(timeout=10)
            if self.fastapi_thread.is_alive():
                log.warning(
                    "%s FastAPI server thread did not exit gracefully.",
                    self.log_identifier,
                )

        # Call parent cleanup
        super().cleanup()
        log.info("%s Platform Service Component cleanup finished.", self.log_identifier)

    def get_cors_origins(self) -> list[str]:
        """
        Return the configured CORS allowed origins.

        Returns:
            List of allowed origin strings.
        """
        return self.cors_allowed_origins

    def get_namespace(self) -> str:
        """
        Return the component's namespace.

        Returns:
            Namespace string.
        """
        return self.namespace

    def get_config_resolver(self) -> ConfigResolver:
        """
        Return the ConfigResolver instance.

        The default ConfigResolver is permissive and allows all features/scopes.
        This enables webui_backend routers (which use ValidatedUserConfig) to work
        in platform mode without custom authorization logic.

        Returns:
            ConfigResolver instance.
        """
        return self.config_resolver

    def get_session_manager(self) -> _StubSessionManager:
        """
        Return the stub SessionManager.

        Platform service doesn't have real session management, but returns a
        minimal stub to satisfy gateway dependencies that expect SessionManager.

        Returns:
            Stub SessionManager instance.
        """
        return self.session_manager
