"""
Platform Service Component for Solace Agent Mesh.
Hosts the FastAPI REST API server for platform configuration management.
"""

import logging
import threading
import json
from typing import Any, Dict

import uvicorn
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.common.middleware.config_resolver import ConfigResolver
from solace_agent_mesh.core_a2a.service import CoreA2AService
from solace_agent_mesh.common import a2a
from a2a.types import AgentCard

log = logging.getLogger(__name__)


class _StubSessionManager:
    """
    Minimal stub for SessionManager to satisfy legacy router dependencies.

    Platform service doesn't have chat sessions, but webui_backend routers
    (originally designed for WebUI gateway) expect a SessionManager.
    This stub provides minimal compatibility.
    """
    pass


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
    - Uses direct messaging (publishes commands to deployer, receives heartbeats)
    - Has agent registry (for deployment monitoring, not chat orchestration)
    - Independent from WebUI gateway
    - NOT A2A communication (deployer is a service, not an agent)
    """

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Override get_config to look inside nested 'app_config' dictionary.

        PlatformServiceApp places configuration in component_config['app_config'],
        following the same pattern as BaseGatewayApp.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if "app_config" in self.component_config:
            value = self.component_config["app_config"].get(key)
            if value is not None:
                return value

        return super().get_config(key, default)

    def __init__(self, **kwargs):
        """
        Initialize the PlatformServiceComponent.

        Retrieves configuration, initializes FastAPI server state,
        and starts the FastAPI/Uvicorn server.
        """
        # Initialize SamComponentBase (provides namespace, max_message_size, async loop)
        super().__init__(info, **kwargs)
        log.info("%s Initializing Platform Service Component...", self.log_identifier)

        # Note: self.namespace is already set by SamComponentBase
        # Note: self.max_message_size_bytes is already set by SamComponentBase

        try:
            # Retrieve Platform Service specific configuration
            self.database_url = self.get_config("database_url")
            self.fastapi_host = self.get_config("fastapi_host", "127.0.0.1")
            self.fastapi_port = int(self.get_config("fastapi_port", 8001))
            self.fastapi_https_port = int(self.get_config("fastapi_https_port", 8444))
            self.ssl_keyfile = self.get_config("ssl_keyfile", "")
            self.ssl_certfile = self.get_config("ssl_certfile", "")
            self.ssl_keyfile_password = self.get_config("ssl_keyfile_password", "")
            self.cors_allowed_origins = self.get_config("cors_allowed_origins", ["*"])

            # OAuth2 configuration (enterprise feature - defaults to community mode)
            self.external_auth_service_url = self.get_config("external_auth_service_url", "")
            self.external_auth_provider = self.get_config("external_auth_provider", "generic")

            # Background task configuration
            self.deployment_timeout_minutes = self.get_config("deployment_timeout_minutes", 5)
            self.heartbeat_timeout_seconds = self.get_config("heartbeat_timeout_seconds", 90)
            self.deployment_check_interval_seconds = self.get_config("deployment_check_interval_seconds", 60)

            log.info(
                "%s Platform service configuration retrieved (Host: %s, Port: %d, Auth: %s).",
                self.log_identifier,
                self.fastapi_host,
                self.fastapi_port,
                "enabled" if self.get_config("frontend_use_authorization", False) else "disabled",
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
        self.session_manager = _StubSessionManager()

        # Agent discovery (like BaseGatewayComponent)
        # Initialize here so CoreA2AService can use it
        from solace_agent_mesh.common.agent_registry import AgentRegistry
        self.agent_registry = AgentRegistry()
        self.core_a2a_service = CoreA2AService(
            agent_registry=self.agent_registry,
            namespace=self.namespace,
            component_id="Platform"
        )
        log.info("%s Agent discovery service initialized", self.log_identifier)

        # Background task state (for heartbeat monitoring and deployment status checking)
        # Note: agent_registry already initialized above
        self.heartbeat_tracker = None
        self.heartbeat_listener = None
        self.background_scheduler = None
        self.background_tasks_thread = None

        # Direct message publisher for deployer commands
        self.direct_publisher = None

        log.info("%s Platform Service Component initialized.", self.log_identifier)

        # Start FastAPI server immediately (doesn't depend on broker)
        self._start_fastapi_server()

        # Note: Direct publisher and background tasks are started in _late_init()
        # after SamComponentBase.run() is called and broker is guaranteed ready

    def _late_init(self):
        """
        Late initialization called by SamComponentBase.run() after broker is ready.

        This is the proper place to initialize services that require broker connectivity:
        - Direct message publisher (for deployer commands)
        - Background tasks (heartbeat listener, deployment checker)
        """
        log.info("%s Starting late initialization (broker-dependent services)...", self.log_identifier)

        # Initialize direct message publisher for deployer commands
        self._init_direct_publisher()

        # Start background tasks (heartbeat listener + deployment checker)
        self._start_background_tasks()

        log.info("%s Late initialization complete", self.log_identifier)

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

            # Determine port based on SSL configuration
            port = (
                self.fastapi_https_port
                if self.ssl_keyfile and self.ssl_certfile
                else self.fastapi_port
            )

            # Create uvicorn configuration with SSL support
            config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.fastapi_host,
                port=port,
                log_level="warning",
                lifespan="on",
                ssl_keyfile=self.ssl_keyfile if self.ssl_keyfile else None,
                ssl_certfile=self.ssl_certfile if self.ssl_certfile else None,
                ssl_keyfile_password=self.ssl_keyfile_password if self.ssl_keyfile_password else None,
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

            # Log with correct protocol
            protocol = "https" if self.ssl_keyfile and self.ssl_certfile else "http"
            log.info(
                "%s FastAPI/Uvicorn server starting in background thread on %s://%s:%d",
                self.log_identifier,
                protocol,
                self.fastapi_host,
                port,
            )

        except Exception as e:
            log.error(
                "%s Failed to start FastAPI/Uvicorn server: %s",
                self.log_identifier,
                e,
            )
            raise

    def _init_direct_publisher(self):
        """
        Initialize direct message publisher for deployer communication.

        Platform Service sends deployment commands directly to deployer:
        - {namespace}/deployer/agent/{id}/deploy
        - {namespace}/deployer/agent/{id}/update
        - {namespace}/deployer/agent/{id}/undeploy

        Uses direct publishing (not A2A protocol) since deployer is a
        standalone service, not an A2A agent.

        Called from _late_init() after broker is guaranteed to be connected.
        """
        try:
            # Get messaging service from broker_output
            # Note: broker_output might not be ready yet in _late_init (timing varies)
            if not hasattr(self, 'broker_output') or not self.broker_output:
                log.info(
                    "%s Broker output not yet available - direct publisher will be initialized later if needed",
                    self.log_identifier
                )
                return

            if not hasattr(self.broker_output, 'messaging_service'):
                log.warning(
                    "%s Broker output missing messaging_service - deployment commands unavailable",
                    self.log_identifier
                )
                return

            messaging_service = self.broker_output.messaging_service

            from solace.messaging.publisher.direct_message_publisher import DirectMessagePublisher

            self.direct_publisher = messaging_service.create_direct_message_publisher_builder().build()
            self.direct_publisher.start()

            log.info("%s Direct message publisher initialized for deployer commands", self.log_identifier)

        except Exception as e:
            log.warning(
                "%s Could not initialize direct publisher: %s (deployment commands will not work)",
                self.log_identifier,
                e
            )

    def _start_background_tasks(self):
        """
        Start background tasks for Platform Service.

        This method calls the enterprise function to start background tasks
        if the enterprise package is available. Follows the same pattern as
        WebUI Gateway for graceful degradation.

        Background tasks (enterprise-only):
        - Heartbeat listener (monitors deployer heartbeats)
        - Deployment status checker (checks deployment timeouts)
        - Agent registry (tracks agent availability)
        """
        try:
            from solace_agent_mesh_enterprise.init_enterprise import start_platform_background_tasks

            log.info("%s Starting enterprise platform background tasks...", self.log_identifier)
            start_platform_background_tasks(self)
            log.info("%s Enterprise platform background tasks started", self.log_identifier)

        except ImportError:
            log.info(
                "%s Enterprise package not available - no background tasks to start",
                self.log_identifier
            )
        except Exception as e:
            log.error(
                "%s Failed to start enterprise background tasks: %s",
                self.log_identifier,
                e,
                exc_info=True
            )

    async def _handle_message_async(self, message, topic: str) -> None:
        """
        Handle incoming broker messages asynchronously (required by SamComponentBase).

        Processes agent discovery messages and updates AgentRegistry.

        Args:
            message: The broker message
            topic: The topic the message was received on
        """
        log.debug(
            "%s Received async message on topic: %s",
            self.log_identifier,
            topic,
        )

        processed_successfully = False

        try:
            if a2a.topic_matches_subscription(
                topic, a2a.get_discovery_topic(self.namespace)
            ):
                payload = message.get_payload()

                # Parse JSON if payload is string/bytes (defensive coding)
                if isinstance(payload, bytes):
                    payload = json.loads(payload.decode('utf-8'))
                elif isinstance(payload, str):
                    payload = json.loads(payload)
                # else: payload is already a dict (SAC framework auto-parses)

                processed_successfully = self._handle_discovery_message(payload)
            else:
                log.debug(
                    "%s Ignoring message on non-discovery topic: %s",
                    self.log_identifier,
                    topic,
                )
                processed_successfully = True

        except Exception as e:
            log.error(
                "%s Error handling async message on topic %s: %s",
                self.log_identifier,
                topic,
                e,
                exc_info=True
            )
            processed_successfully = False
        finally:
            # Acknowledge message (like BaseGatewayComponent pattern)
            if hasattr(message, 'call_acknowledgements'):
                try:
                    if processed_successfully:
                        message.call_acknowledgements()
                    else:
                        message.call_negative_acknowledgements()
                except Exception as ack_error:
                    log.warning(
                        "%s Error acknowledging message: %s",
                        self.log_identifier,
                        ack_error
                    )

    def _handle_discovery_message(self, payload: Dict) -> bool:
        """
        Handle incoming agent discovery messages.

        Follows the same pattern as BaseGatewayComponent for consistency.

        Args:
            payload: The message payload dictionary

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            agent_card = AgentCard(**payload)
            self.core_a2a_service.process_discovery_message(agent_card)
            log.debug(
                "%s Processed agent discovery: %s",
                self.log_identifier,
                agent_card.name
            )
            return True
        except Exception as e:
            log.error(
                "%s Failed to process discovery message: %s. Payload: %s",
                self.log_identifier,
                e,
                payload,
                exc_info=True
            )
            return False

    def _get_component_id(self) -> str:
        """
        Return unique identifier for this component (required by SamComponentBase).

        Returns:
            Component identifier string
        """
        return "platform_service"

    def _get_component_type(self) -> str:
        """
        Return component type (required by SamComponentBase).

        Returns:
            Component type string
        """
        return "service"

    def _pre_async_cleanup(self) -> None:
        """
        Cleanup before async operations stop (required by SamComponentBase).

        Platform Service doesn't have async-specific resources to clean up here.
        Main cleanup happens in cleanup() method.
        """
        pass

    def cleanup(self):
        """
        Gracefully shut down the Platform Service Component.

        This method:
        1. Stops direct message publisher
        2. Stops background tasks (heartbeat listener, deployment checker)
        3. Stops agent registry
        4. Signals the uvicorn server to exit
        5. Waits for the FastAPI thread to finish
        6. Calls parent cleanup
        """
        log.info("%s Cleaning up Platform Service Component...", self.log_identifier)

        # Stop direct publisher
        if self.direct_publisher:
            try:
                self.direct_publisher.terminate()
                log.info("%s Direct message publisher stopped", self.log_identifier)
            except Exception as e:
                log.warning("%s Error stopping direct publisher: %s", self.log_identifier, e)

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

        # Call SamComponentBase cleanup (stops async loop and threads)
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
        Publish direct message to deployer (not A2A protocol).

        Platform Service sends deployment commands directly to deployer service.
        This is service-to-service communication, not agent-to-agent protocol.

        Commands sent to:
        - {namespace}/deployer/agent/{agent_id}/deploy
        - {namespace}/deployer/agent/{agent_id}/update
        - {namespace}/deployer/agent/{agent_id}/undeploy

        Args:
            topic: Message topic
            payload: Message payload dictionary (will be JSON-serialized)
            user_properties: Optional user properties (not used by deployer)

        Raises:
            Exception: If publishing fails
        """
        import json
        from solace.messaging.resources.topic import Topic

        log.debug("%s Publishing deployer command to topic: %s", self.log_identifier, topic)

        try:
            if not self.direct_publisher:
                raise RuntimeError("Direct publisher not initialized")

            # Serialize payload to JSON
            message_body = json.dumps(payload)

            # Build message
            main_app = self.get_app()
            messaging_service = main_app.connector.get_messaging_service()
            message = messaging_service.message_builder().build(message_body)

            # Publish directly to topic
            self.direct_publisher.publish(message, Topic.of(topic))

            log.debug(
                "%s Successfully published deployer command to topic: %s (payload size: %d bytes)",
                self.log_identifier,
                topic,
                len(message_body)
            )

        except Exception as e:
            log.error(
                "%s Failed to publish deployer command: %s",
                self.log_identifier,
                e,
                exc_info=True
            )
            raise
