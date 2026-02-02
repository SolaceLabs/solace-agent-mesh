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
from solace_agent_mesh.common.constants import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_TTL_SECONDS,
)
from solace_agent_mesh.common.a2a.utils import is_gateway_card
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

    HEALTH_CHECK_TIMER_ID = "platform_agent_health_check"
    GATEWAY_HEALTH_CHECK_TIMER_ID = "platform_gateway_health_check"

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
            self.cors_allowed_origin_regex = self.get_config("cors_allowed_origin_regex", "")

            # OAuth2 configuration (enterprise feature - defaults to community mode)
            self.external_auth_service_url = self.get_config("external_auth_service_url", "")
            self.external_auth_provider = self.get_config("external_auth_provider", "generic")

            # Background task configuration
            self.deployment_timeout_minutes = self.get_config("deployment_timeout_minutes", 5)
            self.heartbeat_timeout_seconds = self.get_config("heartbeat_timeout_seconds", 90)
            self.deployment_check_interval_seconds = self.get_config("deployment_check_interval_seconds", 60)

            # Agent health check configuration (for removing expired agents from registry)
            self.health_check_interval_seconds = self.get_config(
                "health_check_interval_seconds", HEALTH_CHECK_INTERVAL_SECONDS
            )
            self.health_check_ttl_seconds = self.get_config(
                "health_check_ttl_seconds", HEALTH_CHECK_TTL_SECONDS
            )

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

        # Agent and gateway discovery (like BaseGatewayComponent)
        # Initialize here so CoreA2AService can use it
        from solace_agent_mesh.common.agent_registry import AgentRegistry
        from solace_agent_mesh.common.gateway_registry import GatewayRegistry
        self.agent_registry = AgentRegistry()
        self.gateway_registry = GatewayRegistry()
        self.core_a2a_service = CoreA2AService(
            agent_registry=self.agent_registry,
            namespace=self.namespace,
            component_id="Platform"
        )
        log.info("%s Agent and gateway discovery services initialized", self.log_identifier)

        # Background task state (for heartbeat monitoring and deployment status checking)
        # Note: agent_registry already initialized above
        self.heartbeat_tracker = None
        self.heartbeat_listener = None
        self.background_scheduler = None
        self.background_tasks_thread = None

        self.direct_publisher = None

        log.info("%s Running database migrations...", self.log_identifier)
        self._run_database_migrations()
        log.info("%s Database migrations completed", self.log_identifier)

        log.info("%s Platform Service Component initialized.", self.log_identifier)

    def _run_database_migrations(self):
        """Run database migrations synchronously during __init__."""
        try:
            from .api.main import _setup_database
            _setup_database(self.database_url)
        except Exception as e:
            log.error(
                "%s Failed to run database migrations: %s",
                self.log_identifier,
                e,
                exc_info=True
            )
            raise RuntimeError(f"Database migration failed during component initialization: {e}") from e

    def _late_init(self):
        """
        Late initialization called by SamComponentBase.run() after broker is ready.

        This is the proper place to initialize services that require broker connectivity:
        - FastAPI server (with startup event for background tasks)
        - Direct message publisher (for deployer commands)
        - Agent health check timer (for removing expired agents from registry)
        """
        log.info("%s Starting late initialization (broker-dependent services)...", self.log_identifier)

        # Initialize direct message publisher for deployer commands
        self._init_direct_publisher()

        # Start FastAPI server (background tasks started via FastAPI startup event)
        self._start_fastapi_server()

        # Schedule agent health checks to remove expired agents from registry
        self._schedule_agent_health_check()

        # Schedule gateway health checks to remove expired gateways from registry
        self._schedule_gateway_health_check()

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

            setup_dependencies(self)

            # Register startup event for background tasks
            @self.fastapi_app.on_event("startup")
            async def start_background_tasks():
                try:
                    from solace_agent_mesh_enterprise.init_enterprise import start_platform_background_tasks

                    log.info("%s Starting enterprise platform background tasks...", self.log_identifier)
                    await start_platform_background_tasks(self)
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

        Called from _late_init() and lazily from publish_a2a() if needed.
        Uses SAC's existing broker connection via the BrokerOutput component.
        """
        try:
            main_app = self.get_app()
            if not main_app or not main_app.flows:
                log.info(
                    "%s App flows not yet available - direct publisher will be initialized later",
                    self.log_identifier
                )
                return

            # Find BrokerOutput component in the flow (same pattern as App.send_message)
            broker_output = None
            flow = main_app.flows[0]
            if flow.component_groups:
                for group in reversed(flow.component_groups):
                    if group:
                        comp = group[0]
                        if comp.module_info.get("class_name") == "BrokerOutput":
                            broker_output = comp
                            break

            if not broker_output or not hasattr(broker_output, 'messaging_service'):
                log.info(
                    "%s BrokerOutput component not ready - direct publisher will be initialized later",
                    self.log_identifier
                )
                return

            self._messaging_service = broker_output.messaging_service.messaging_service
            self.direct_publisher = self._messaging_service.create_direct_message_publisher_builder().build()
            self.direct_publisher.start()

            log.info("%s Direct message publisher initialized for deployer commands", self.log_identifier)

        except Exception as e:
            log.warning(
                "%s Could not initialize direct publisher: %s (deployment commands will not work)",
                self.log_identifier,
                e
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
                topic, a2a.get_discovery_subscription_topic(self.namespace)
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
        Handle incoming agent and gateway discovery messages.

        Routes discovery cards to appropriate registries:
        - Gateway cards (with gateway-role extension) -> GatewayRegistry
        - Agent cards -> AgentRegistry

        Args:
            payload: The message payload dictionary

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            agent_card = AgentCard(**payload)

            # Route to appropriate registry based on card type
            if is_gateway_card(agent_card):
                # This is a gateway card - track in gateway registry
                is_new = self.gateway_registry.add_or_update_gateway(agent_card)
                if is_new:
                    gateway_type = self.gateway_registry.get_gateway_type(agent_card.name)
                    log.info(
                        "%s New gateway discovered: %s (type: %s)",
                        self.log_identifier,
                        agent_card.name,
                        gateway_type or "unknown"
                    )
                else:
                    log.debug(
                        "%s Gateway heartbeat received: %s",
                        self.log_identifier,
                        agent_card.name
                    )
            else:
                # This is an agent card - use existing logic
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

        # Cancel health check timers before clearing registries
        self.cancel_timer(self.HEALTH_CHECK_TIMER_ID)
        self.cancel_timer(self.GATEWAY_HEALTH_CHECK_TIMER_ID)
        log.info("%s Health check timers cancelled", self.log_identifier)

        # Stop agent registry
        if self.agent_registry:
            try:
                self.agent_registry.clear()
                log.info("%s Agent registry cleared", self.log_identifier)
            except Exception as e:
                log.warning("%s Error clearing agent registry: %s", self.log_identifier, e)

        # Stop gateway registry
        if self.gateway_registry:
            try:
                self.gateway_registry.clear()
                log.info("%s Gateway registry cleared", self.log_identifier)
            except Exception as e:
                log.warning("%s Error clearing gateway registry: %s", self.log_identifier, e)

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

    def get_cors_origin_regex(self) -> str:
        """
        Return the configured CORS allowed origin regex pattern.

        Returns:
            Regex pattern string, or empty string if not configured.
        """
        return self.cors_allowed_origin_regex

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

    def get_gateway_registry(self):
        """
        Return the gateway registry instance.

        Used for gateway fleet health monitoring.

        Returns:
            GatewayRegistry instance if initialized, None otherwise.
        """
        return self.gateway_registry

    def get_db_engine(self):
        """
        Get the SQLAlchemy database engine for health checks.

        Returns the engine bound to PlatformSessionLocal if database is configured,
        otherwise returns None.

        Returns:
            Engine or None: The SQLAlchemy engine if available.
        """
        from .api import dependencies

        if dependencies.PlatformSessionLocal is not None:
            return dependencies.PlatformSessionLocal.kw.get("bind")
        return None

    def _schedule_agent_health_check(self):
        """
        Schedule periodic agent health checks to remove expired agents from registry.

        This is essential for deployment status checking - when an agent is undeployed,
        the deployment status checker needs to see the agent removed from the registry
        to mark the undeploy as successful.
        """
        if self.health_check_interval_seconds > 0:
            log.info(
                "%s Scheduling agent health check every %d seconds (TTL: %d seconds)",
                self.log_identifier,
                self.health_check_interval_seconds,
                self.health_check_ttl_seconds,
            )
            self.add_timer(
                delay_ms=self.health_check_interval_seconds * 1000,
                timer_id=self.HEALTH_CHECK_TIMER_ID,
                interval_ms=self.health_check_interval_seconds * 1000,
                callback=lambda timer_data: self._check_agent_health(),
            )
        else:
            log.warning(
                "%s Agent health check disabled (interval=%d). "
                "Agents will not be automatically removed from registry when they stop sending heartbeats.",
                self.log_identifier,
                self.health_check_interval_seconds,
            )

    def _check_agent_health(self):
        """
        Check agent health and remove expired agents from registry.

        Called periodically by the health check timer. Iterates through all
        registered agents and removes any whose TTL has expired (i.e., they
        haven't sent a heartbeat recently).
        """
        log.debug("%s Performing agent health check...", self.log_identifier)

        agent_names = self.agent_registry.get_agent_names()
        total_agents = len(agent_names)
        agents_removed = 0

        for agent_name in agent_names:
            is_expired, time_since_last_seen = self.agent_registry.check_ttl_expired(
                agent_name, self.health_check_ttl_seconds
            )

            if is_expired:
                log.warning(
                    "%s Agent '%s' TTL expired (last seen: %d seconds ago, TTL: %d seconds). Removing from registry.",
                    self.log_identifier,
                    agent_name,
                    time_since_last_seen,
                    self.health_check_ttl_seconds,
                )
                self.agent_registry.remove_agent(agent_name)
                agents_removed += 1

        if agents_removed > 0:
            log.info(
                "%s Agent health check complete: %d/%d agents removed",
                self.log_identifier,
                agents_removed,
                total_agents,
            )
        else:
            log.debug(
                "%s Agent health check complete: %d agents, all healthy",
                self.log_identifier,
                total_agents,
            )

    def _schedule_gateway_health_check(self):
        """
        Schedule periodic gateway health checks to remove expired gateways from registry.

        This mirrors _schedule_agent_health_check() for consistency. When a gateway
        stops sending heartbeats (discovery cards), it will be automatically removed
        from the registry after the TTL expires.
        """
        if self.health_check_interval_seconds > 0:
            log.info(
                "%s Scheduling gateway health check every %d seconds (TTL: %d seconds)",
                self.log_identifier,
                self.health_check_interval_seconds,
                self.health_check_ttl_seconds,
            )
            self.add_timer(
                delay_ms=self.health_check_interval_seconds * 1000,
                timer_id=self.GATEWAY_HEALTH_CHECK_TIMER_ID,
                interval_ms=self.health_check_interval_seconds * 1000,
                callback=lambda timer_data: self._check_gateway_health(),
            )
        else:
            log.warning(
                "%s Gateway health check disabled (interval=%d). "
                "Gateways will not be automatically removed from registry when they stop sending heartbeats.",
                self.log_identifier,
                self.health_check_interval_seconds,
            )

    def _check_gateway_health(self):
        """
        Check gateway health and remove expired gateways from registry.

        Called periodically by the health check timer. Iterates through all
        registered gateways and removes any whose TTL has expired (i.e., they
        haven't sent a heartbeat recently).
        """
        log.debug("%s Performing gateway health check...", self.log_identifier)

        gateway_ids = self.gateway_registry.get_gateway_ids()
        total_gateways = len(gateway_ids)
        gateways_removed = 0

        for gateway_id in gateway_ids:
            is_expired, time_since_last_seen = self.gateway_registry.check_ttl_expired(
                gateway_id, self.health_check_ttl_seconds
            )

            if is_expired:
                log.warning(
                    "%s Gateway '%s' TTL expired (last seen: %d seconds ago, TTL: %d seconds). Removing from registry.",
                    self.log_identifier,
                    gateway_id,
                    time_since_last_seen,
                    self.health_check_ttl_seconds,
                )
                self.gateway_registry.remove_gateway(gateway_id)
                gateways_removed += 1

        if gateways_removed > 0:
            log.info(
                "%s Gateway health check complete: %d/%d gateways removed",
                self.log_identifier,
                gateways_removed,
                total_gateways,
            )
        else:
            log.debug(
                "%s Gateway health check complete: %d gateways, all healthy",
                self.log_identifier,
                total_gateways,
            )

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
                self._init_direct_publisher()
                if not self.direct_publisher:
                    raise RuntimeError("Direct publisher not initialized")

            # Serialize payload to JSON and convert to bytearray
            message_body = json.dumps(payload)
            message_bytes = bytearray(message_body.encode("utf-8"))

            # Publish directly to topic
            self.direct_publisher.publish(
                message=message_bytes,
                destination=Topic.of(topic)
            )

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
