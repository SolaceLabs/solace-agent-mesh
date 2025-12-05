"""
Platform Service Component for Solace Agent Mesh.
Hosts the FastAPI REST API server for platform configuration management.
"""

import logging
import threading

import uvicorn
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

log = logging.getLogger(__name__)


class _StubSessionManager:
    """
    Minimal stub for SessionManager to satisfy legacy router dependencies.

    Platform service doesn't have chat sessions, but webui_backend routers
    (originally designed for WebUI gateway) expect a SessionManager.
    This stub provides minimal compatibility for user_id resolution.
    """
    def __init__(self, use_authorization: bool):
        self.use_authorization = use_authorization


info = {
    "class_name": "PlatformServiceComponent",
    "description": (
        "Platform Service Component - REST API for platform management (agents, connectors, deployments). "
        "This is a SERVICE, not a gateway - services provide internal platform functionality, "
        "while gateways handle external communication channels."
    ),
}


class PlatformServiceComponent(SamComponentBase):
    """
    Platform Service Component - Management plane for SAM platform.

    Architecture distinction:
    - SERVICE: Provides internal platform functionality (this component)
    - GATEWAY: Handles external communication channels (http_sse, slack, webhook, etc.)

    Responsibilities:
    - REST API for platform configuration management
    - Agent Builder CRUD operations
    - Connector management
    - Deployment orchestration
    - Deployer heartbeat monitoring
    - Background deployment status checking

    Key characteristics:
    - No user chat sessions (services don't interact with end users)
    - Has A2A messaging (publishes to deployer, receives heartbeats/agent-cards)
    - Has agent registry (for deployment monitoring, not chat orchestration)
    - Independent from WebUI gateway
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

            # Background task configuration
            self.deployment_timeout_minutes = self.get_config("deployment_timeout_minutes", 5)
            self.heartbeat_timeout_seconds = self.get_config("heartbeat_timeout_seconds", 90)
            self.deployment_check_interval_seconds = self.get_config("deployment_check_interval_seconds", 60)

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

        # Legacy router compatibility
        # webui_backend routers were originally designed for WebUI gateway context
        # but now work with Platform Service via dependency abstraction
        self.session_manager = _StubSessionManager(use_authorization=self.use_authorization)

        # Background task state (for heartbeat monitoring and deployment status checking)
        self.agent_registry = None
        self.heartbeat_tracker = None
        self.heartbeat_listener = None
        self.background_scheduler = None
        self.background_tasks_thread = None

        log.info("%s Platform Service Component initialized.", self.log_identifier)

        # Start FastAPI server
        self._start_fastapi_server()

        # Start background tasks (heartbeat listener + deployment checker)
        self._start_background_tasks()

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

    def _start_background_tasks(self):
        """
        Start background tasks for platform service:
        1. Agent registry (monitors agent presence via agent-cards topic)
        2. Heartbeat listener (monitors deployer heartbeats)
        3. Deployment status checker (monitors in-progress deployments)
        """
        log.info("%s Starting background tasks...", self.log_identifier)

        try:
            from solace_agent_mesh.agent.registry import AgentRegistry

            self.agent_registry = AgentRegistry(namespace=self.namespace, component=self)
            log.info("%s Agent registry initialized for deployment monitoring", self.log_identifier)
        except Exception as e:
            log.error("%s Failed to initialize agent registry: %s", self.log_identifier, e)
            raise

        import asyncio
        loop = asyncio.new_event_loop()

        async def start_tasks():
            await self._start_heartbeat_listener()
            await self._start_deployment_checker()

        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_tasks())
            loop.run_forever()

        self.background_tasks_thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name="PlatformService_BackgroundTasks"
        )
        self.background_tasks_thread.start()

        log.info("%s Background tasks started successfully", self.log_identifier)

    async def _start_heartbeat_listener(self):
        """
        Start deployer heartbeat listener.
        Monitors deployer heartbeats to determine if deployer service is online.
        """
        try:
            from solace_agent_mesh_enterprise.platform_service.services.heartbeat_tracker import HeartbeatTracker
            from solace_agent_mesh_enterprise.platform_service.services.heartbeat_message_handler import HeartbeatMessageHandler
            from solace_agent_mesh_enterprise.platform_service.services.heartbeat_listener import HeartbeatListener

            log.info("%s Starting heartbeat listener...", self.log_identifier)

            self.heartbeat_tracker = HeartbeatTracker(timeout_seconds=self.heartbeat_timeout_seconds)

            heartbeat_topic = f"{self.namespace}/deployer/heartbeat"

            main_app = self.get_app()
            if not main_app or not main_app.connector:
                raise RuntimeError("Cannot access main app or connector for heartbeat listener")

            broker_config = main_app.app_info.get("broker", {})
            if not broker_config:
                raise ValueError("Broker configuration is required for heartbeat monitoring")

            handler = HeartbeatMessageHandler(self.heartbeat_tracker)
            self.heartbeat_listener = HeartbeatListener(
                heartbeat_topic=heartbeat_topic,
                broker_config=broker_config,
                handler=handler
            )

            self.heartbeat_listener.start()

            log.info(
                "%s Heartbeat listener started on topic: %s (timeout: %ds)",
                self.log_identifier,
                heartbeat_topic,
                self.heartbeat_timeout_seconds
            )

        except (ImportError, ModuleNotFoundError):
            log.warning(
                "%s Enterprise package not found - heartbeat monitoring unavailable",
                self.log_identifier
            )
        except Exception as e:
            log.error("%s Failed to start heartbeat listener: %s", self.log_identifier, e)
            raise

    async def _start_deployment_checker(self):
        """
        Start deployment status checker.
        Periodically checks in-progress deployments and updates their status.
        """
        try:
            from solace_agent_mesh_enterprise.platform_service.services.deployment_status_checker import DeploymentStatusChecker
            from solace_agent_mesh_enterprise.platform_service.services.background_scheduler import BackgroundScheduler
            from solace_agent_mesh_enterprise.platform_service.repositories.deployment_repository import DeploymentRepository
            from solace_agent_mesh_enterprise.platform_service.repositories.agent_repository import AgentRepository
            from solace_agent_mesh_enterprise.platform_service.dependencies import PlatformSessionLocal

            if PlatformSessionLocal is None:
                log.warning(
                    "%s Platform database not initialized - deployment monitoring unavailable",
                    self.log_identifier
                )
                return

            log.info("%s Starting deployment status checker...", self.log_identifier)

            deployment_repo = DeploymentRepository()
            agent_repo = AgentRepository()

            status_checker = DeploymentStatusChecker(
                agent_registry=self.agent_registry,
                deployment_repository=deployment_repo,
                agent_repository=agent_repo,
                timeout_minutes=self.deployment_timeout_minutes
            )

            self.background_scheduler = BackgroundScheduler(
                status_checker=status_checker,
                db_session_factory=PlatformSessionLocal,
                interval_seconds=self.deployment_check_interval_seconds
            )

            await self.background_scheduler.start()

            log.info(
                "%s Deployment status checker started (interval: %ds, timeout: %dm)",
                self.log_identifier,
                self.deployment_check_interval_seconds,
                self.deployment_timeout_minutes
            )

        except (ImportError, ModuleNotFoundError):
            log.warning(
                "%s Enterprise package not found - deployment monitoring unavailable",
                self.log_identifier
            )
        except Exception as e:
            log.error("%s Failed to start deployment status checker: %s", self.log_identifier, e)
            raise

    def cleanup(self):
        """
        Gracefully shut down the Platform Service Component.

        This method:
        1. Stops background tasks (heartbeat listener, deployment checker)
        2. Stops agent registry
        3. Signals the uvicorn server to exit
        4. Waits for the FastAPI thread to finish
        5. Calls parent cleanup
        """
        log.info("%s Cleaning up Platform Service Component...", self.log_identifier)

        # Stop background scheduler
        if self.background_scheduler:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.background_scheduler.stop())
                log.info("%s Background scheduler stopped", self.log_identifier)
            except Exception as e:
                log.warning("%s Error stopping background scheduler: %s", self.log_identifier, e)

        # Stop heartbeat listener
        if self.heartbeat_listener:
            try:
                self.heartbeat_listener.stop()
                log.info("%s Heartbeat listener stopped", self.log_identifier)
            except Exception as e:
                log.warning("%s Error stopping heartbeat listener: %s", self.log_identifier, e)

        # Stop agent registry
        if self.agent_registry:
            try:
                self.agent_registry.cleanup()
                log.info("%s Agent registry stopped", self.log_identifier)
            except Exception as e:
                log.warning("%s Error stopping agent registry: %s", self.log_identifier, e)

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

    def get_heartbeat_tracker(self):
        """
        Return the heartbeat tracker instance.

        Used by deployer status endpoint to check if deployer is online.

        Returns:
            HeartbeatTracker instance if initialized, None otherwise.
        """
        return self.heartbeat_tracker

    def get_agent_registry(self):
        """
        Return the agent registry instance.

        Used for deployment status monitoring.

        Returns:
            AgentRegistry instance if initialized, None otherwise.
        """
        return self.agent_registry

    def publish_a2a(
        self, topic: str, payload: dict, user_properties: dict | None = None
    ):
        """
        Publish an A2A message to the broker.

        Used by deployment service to send commands to deployer:
        - {namespace}/deployer/agent/{agent_id}/deploy
        - {namespace}/deployer/agent/{agent_id}/update
        - {namespace}/deployer/agent/{agent_id}/undeploy

        Args:
            topic: Message topic
            payload: Message payload dictionary
            user_properties: Optional user properties for message metadata

        Raises:
            Exception: If publishing fails
        """
        log.debug("%s Publishing A2A message to topic: %s", self.log_identifier, topic)

        try:
            super().publish_a2a_message(payload, topic, user_properties)
            log.debug("%s Successfully published to topic: %s", self.log_identifier, topic)
        except Exception as e:
            log.error("%s Failed to publish A2A message: %s", self.log_identifier, e, exc_info=True)
            raise
