"""
The GenericGatewayComponent, the engine that hosts and orchestrates GatewayAdapters.
"""

import asyncio
import importlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from a2a.types import (
    DataPart as A2ADataPart,
    FilePart,
    JSONRPCError,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from ...common import a2a
from ...common.a2a.protocol import get_feedback_topic
from ...agent.utils.artifact_helpers import (
    get_artifact_info_list,
    load_artifact_content_or_metadata,
)
from ...common.a2a.types import ArtifactInfo
from ...common.utils.mime_helpers import is_text_based_mime_type
from ...common.utils.embeds import (
    LATE_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_recursively_in_string,
)
from ...common.utils.embeds.types import ResolutionMode
from ..adapter.base import GatewayAdapter
from ..adapter.types import (
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFeedback,
    SamFilePart,
    SamTextPart,
    SamUpdate,
)
from ..base.component import BaseGatewayComponent

# Try to import enterprise auth handler
try:
    from solace_agent_mesh_enterprise.gateway.auth import SAMOAuth2Handler
    ENTERPRISE_AUTH_AVAILABLE = True
except ImportError:
    ENTERPRISE_AUTH_AVAILABLE = False
    SAMOAuth2Handler = None


log = logging.getLogger(__name__)

info = {
    "class_name": "GenericGatewayComponent",
    "description": "A generic gateway component that hosts a pluggable GatewayAdapter.",
    "config_parameters": [],
}


def _load_adapter_class(adapter_path: str) -> type[GatewayAdapter]:
    """Dynamically loads the adapter class from a module path."""
    try:
        module_path, class_name = adapter_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        if not issubclass(adapter_class, GatewayAdapter):
            raise TypeError(
                f"Class {adapter_path} is not a subclass of GatewayAdapter."
            )
        return adapter_class
    except (ImportError, AttributeError, ValueError, TypeError) as e:
        log.exception(f"Failed to load gateway adapter from path: {adapter_path}")
        raise ImportError(
            f"Could not load gateway adapter '{adapter_path}': {e}"
        ) from e


class GenericGatewayComponent(BaseGatewayComponent, GatewayContext):
    """
    The engine that hosts and orchestrates a GatewayAdapter.

    This component implements the `BaseGatewayComponent` abstract methods by
    delegating platform-specific logic to a dynamically loaded adapter. It also
    serves as the concrete implementation of the `GatewayContext` provided to
    the adapter.
    """

    def __init__(self, **kwargs: Any):
        component_config = kwargs.get("component_config", {})
        app_config = component_config.get("app_config", {})
        resolve_uris = app_config.get("resolve_artifact_uris_in_gateway", True)

        # Generic gateway configuration:
        # - supports_inline_artifact_resolution=True: Artifacts are converted to FileParts
        #   during embed resolution and can be rendered inline
        # - filter_tool_data_parts=False: Gateway displays all parts including tool execution details
        super().__init__(
            resolve_artifact_uris_in_gateway=resolve_uris,
            supports_inline_artifact_resolution=True,
            filter_tool_data_parts=False,
            **kwargs,
        )
        log.info("%s Initializing Generic Gateway Component...", self.log_identifier)

        # --- Adapter Loading ---
        adapter_path = self.get_config("gateway_adapter")
        if not adapter_path:
            raise ValueError("'gateway_adapter' path is not configured.")

        log.info(
            "%s Loading gateway adapter from: %s", self.log_identifier, adapter_path
        )
        AdapterClass = _load_adapter_class(adapter_path)
        self.adapter: GatewayAdapter = AdapterClass()
        log.info(
            "%s Gateway adapter '%s' loaded successfully.",
            self.log_identifier,
            adapter_path,
        )

        # --- GatewayContext properties ---
        adapter_config_dict = self.get_config("adapter_config", {})
        if self.adapter.ConfigModel:
            log.info(
                "%s Validating adapter_config against %s...",
                self.log_identifier,
                self.adapter.ConfigModel.__name__,
            )
            self.adapter_config = self.adapter.ConfigModel(**adapter_config_dict)
        else:
            self.adapter_config = adapter_config_dict

        self.artifact_service = self.shared_artifact_service
        # `gateway_id`, `namespace`, `config` are available from base classes.

        # --- Setup Authentication ---
        self._setup_auth()

        # --- Register Agent Registry Callbacks ---
        # Wire up callbacks so the adapter is notified of agent changes
        self.agent_registry.set_on_agent_added_callback(self._on_agent_added)
        self.agent_registry.set_on_agent_removed_callback(self._on_agent_removed)
        log.info(
            "%s Agent registry callbacks registered for dynamic adapter updates.",
            self.log_identifier,
        )

    def _setup_auth(self) -> None:
        """
        Setup authentication handler if enabled in config.

        Uses enterprise SAMOAuth2Handler if available and auth is enabled.
        Falls back gracefully if enterprise module is not installed.

        Note: This method is called twice:
        1. During BaseGatewayComponent.__init__() (adapter_config not yet available)
        2. After adapter_config is set in GenericGatewayComponent.__init__()
        """
        # Early exit if adapter_config not yet set
        if not hasattr(self, 'adapter_config'):
            log.debug("%s _setup_auth() called before adapter_config set, skipping", self.log_identifier)
            return

        log.debug("%s adapter_config type: %s", self.log_identifier, type(self.adapter_config))

        # Check enable_auth from adapter_config (not app_config)
        # Handle both Pydantic models (use getattr) and plain dicts (use .get())
        if isinstance(self.adapter_config, dict):
            enable_auth = self.adapter_config.get('enable_auth', False)
            log.debug("%s adapter_config is dict, keys: %s", self.log_identifier, list(self.adapter_config.keys()))
        else:
            # Pydantic model or other object
            enable_auth = getattr(self.adapter_config, 'enable_auth', False)
            log.debug("%s adapter_config is Pydantic model, enable_auth=%s", self.log_identifier, enable_auth)

        log.info("%s Authentication check: enable_auth=%s (from adapter_config)", self.log_identifier, enable_auth)

        if not enable_auth:
            log.debug("%s Authentication disabled in config", self.log_identifier)
            return

        if not ENTERPRISE_AUTH_AVAILABLE:
            log.warning(
                "%s Authentication enabled but enterprise module not available. "
                "Install solace-agent-mesh-enterprise to enable OAuth2 authentication.",
                self.log_identifier
            )
            return

        try:
            # Build config dict for SAMOAuth2Handler from adapter_config
            # Handler expects: oauth_proxy_url, external_auth_service_url, external_auth_provider, callback_url
            auth_config = {}

            # Try to get config from adapter_config (Pydantic model or dict)
            if hasattr(self.adapter_config, '__dict__'):
                # Pydantic model
                auth_config = self.adapter_config.__dict__.copy()
            elif isinstance(self.adapter_config, dict):
                # Plain dict
                auth_config = self.adapter_config.copy()

            # Ensure callback_url is set (construct from host/port if not provided)
            if 'callback_url' not in auth_config and 'callback_uri' not in auth_config:
                # Try to construct from host and port
                host = auth_config.get('host', 'localhost')
                port = auth_config.get('port', 8080)
                auth_config['callback_url'] = f"http://{host}:{port}/oauth/callback"
                log.debug("%s Constructed callback_url: %s", self.log_identifier, auth_config['callback_url'])

            # Initialize enterprise OAuth2 handler
            self.auth_handler = SAMOAuth2Handler(auth_config)
            log.info("%s OAuth2 authentication enabled via enterprise module", self.log_identifier)
        except Exception as e:
            log.error("%s Failed to initialize OAuth2 authentication: %s", self.log_identifier, e, exc_info=True)
            self.auth_handler = None

    def _on_agent_added(self, agent_card: Any) -> None:
        """Called when a new agent is added to the registry."""
        if self.adapter:
            log.info(
                "%s Registering new agent: %s",
                self.log_identifier,
                agent_card.name,
            )
            # Schedule the async call in the component's event loop
            asyncio.run_coroutine_threadsafe(
                self.adapter.handle_agent_registered(agent_card), self.get_async_loop()
            )

    def _on_agent_removed(self, agent_name: str) -> None:
        """Called when an agent is removed from the registry."""
        log.info(
            "%s Deregistering agent: %s",
            self.log_identifier,
            agent_name,
        )

        if self.adapter:
            # Schedule the async call in the component's event loop
            asyncio.run_coroutine_threadsafe(
                self.adapter.handle_agent_deregistered(agent_name), self.get_async_loop()
            )

    async def get_user_identity(
            self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts the user identity from the external input via the adapter.

        Returns:
            A dictionary representing the user identity, or None if not available.
        """
        log_id_prefix = f"{self.log_identifier}[GetUserIdentity]"
        user_identity = None
        # 1. Authentication & Enrichment
        # Try enterprise authentication first, fallback to adapter-based auth
        try:
            from solace_agent_mesh_enterprise.gateway.auth import authenticate_request

            auth_claims = await authenticate_request(
                adapter=self.adapter,
                external_input=external_input,
                endpoint_context=endpoint_context,
            )
            log.debug("%s Using enterprise authentication", log_id_prefix)
        except ImportError:
            # Enterprise package not available, use adapter-based auth
            log.debug("%s Enterprise package not available, using adapter auth", log_id_prefix)
            auth_claims = await self.adapter.extract_auth_claims(
                external_input, endpoint_context
            )

        # The final user_identity is a dictionary, not the Pydantic model.
        # It's built from claims and potentially enriched by an identity service.
        if auth_claims:
            if self.identity_service:
                # Pass the rich claims object to the identity service
                enriched_profile = await self.identity_service.get_user_profile(
                    auth_claims
                )
                if enriched_profile:
                    # Merge claims and profile, with profile taking precedence
                    user_identity = {
                        **auth_claims.model_dump(),
                        **enriched_profile,
                    }
                else:
                    user_identity = auth_claims.model_dump()
            else:
                # No identity service, just use the claims from the adapter
                user_identity = auth_claims.model_dump()
        else:
            # Fallback to default identity if no claims are extracted
            default_identity = self.get_config("default_user_identity")
            if default_identity:
                user_identity = {"id": default_identity, "name": default_identity}
        return user_identity

    async def handle_external_input(
        self, external_input: Any, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Processes an external input event through the full gateway flow.
        Orchestrates auth, task preparation, and A2A submission.
        """
        log_id_prefix = f"{self.log_identifier}[HandleInput]"
        user_identity = None
        try:
            user_identity = await self.get_user_identity(external_input, endpoint_context)
            if not user_identity or not user_identity.get("id"):
                raise PermissionError(
                    "Authentication failed: No identity could be determined."
                )

            log.info(
                "%s Authenticated user: %s", log_id_prefix, user_identity.get("id")
            )
            # Add user_id to external_input so adapter can use it for permission checks.
            external_input["user_id"] = user_identity.get("id")

            # 2. Task Preparation
            sam_task = await self.adapter.prepare_task(external_input, endpoint_context)
            log.info(
                "%s Adapter prepared task for agent '%s' with %d parts.",
                log_id_prefix,
                sam_task.target_agent,
                len(sam_task.parts),
            )

            # 3. A2A Submission
            a2a_parts = self._sam_parts_to_a2a_parts(sam_task.parts)

            external_request_context = {
                "a2a_session_id": sam_task.session_id,
                "user_id_for_artifacts": user_identity.get("id"),
                **sam_task.platform_context,
            }

            # Pass session_behavior if provided by adapter
            if sam_task.session_behavior:
                external_request_context["session_behavior"] = sam_task.session_behavior

            task_id = await self.submit_a2a_task(
                target_agent_name=sam_task.target_agent,
                a2a_parts=a2a_parts,
                external_request_context=external_request_context,
                user_identity=user_identity,
                is_streaming=sam_task.is_streaming,
            )
            return task_id

        except Exception as e:
            log.exception(
                "%s Error during external input processing: %s", log_id_prefix, e
            )
            # Try to report error back to the platform if possible
            if (
                user_identity
                and user_identity.get("id")
                and isinstance(e, (ValueError, PermissionError))
            ):
                try:
                    # Create a dummy context to report the error
                    error_context = ResponseContext(
                        task_id="pre-task-error",
                        session_id=None,
                        conversation_id=None,
                        user_id=user_identity.get("id"),
                        platform_context={},
                    )
                    error = SamError(
                        message=str(e), code=-32001, category="GATEWAY_ERROR"
                    )
                    await self.adapter.handle_error(error, error_context)
                except Exception as report_err:
                    log.error(
                        "%s Failed to report initial processing error to adapter: %s",
                        log_id_prefix,
                        report_err,
                    )
            raise

    async def cancel_task(self, task_id: str) -> None:
        """Cancels an in-flight A2A task."""
        log_id_prefix = f"{self.log_identifier}[CancelTask]"
        context = self.task_context_manager.get_context(task_id)
        if not context:
            log.warning(
                "%s Cannot cancel task %s: context not found.", log_id_prefix, task_id
            )
            return

        target_agent_name = context.get("target_agent_name")
        user_id = context.get("user_id_for_a2a")

        if not target_agent_name:
            log.error(
                "%s Cannot cancel task %s: target_agent_name missing from context.",
                log_id_prefix,
                task_id,
            )
            return

        log.info(
            "%s Requesting cancellation for task %s on agent %s",
            log_id_prefix,
            task_id,
            target_agent_name,
        )
        topic, payload, user_properties = self.core_a2a_service.cancel_task(
            agent_name=target_agent_name,
            task_id=task_id,
            client_id=self.gateway_id,
            user_id=user_id,
        )
        self.publish_a2a_message(
            topic=topic, payload=payload, user_properties=user_properties
        )

    async def load_artifact_content(
        self,
        context: "ResponseContext",
        filename: str,
        version: Union[int, str] = "latest",
    ) -> Optional[bytes]:
        """Loads the raw byte content of an artifact using the shared service."""
        log_id_prefix = f"{self.log_identifier}[LoadArtifact]"
        if not self.artifact_service:
            log.error("%s Artifact service is not configured.", log_id_prefix)
            return None
        try:
            artifact_data = await load_artifact_content_or_metadata(
                artifact_service=self.artifact_service,
                app_name=self.gateway_id,
                user_id=context.user_id,
                session_id=context.session_id,
                filename=filename,
                version=version,
                return_raw_bytes=True,
                log_identifier_prefix=log_id_prefix,
            )
            if artifact_data.get("status") == "success":
                content_bytes = artifact_data.get("raw_bytes")
                mime_type = artifact_data.get("mime_type")

                if content_bytes:
                    # For text-based artifacts, resolve templates and late embeds
                    if mime_type and is_text_based_mime_type(mime_type):
                        try:

                            content_str = content_bytes.decode("utf-8")

                            # Build context for resolution
                            context_for_resolver = {
                                "artifact_service": self.artifact_service,
                                "session_context": {
                                    "app_name": self.gateway_id,
                                    "user_id": context.user_id,
                                    "session_id": context.session_id,
                                },
                            }

                            config_for_resolver = {
                                "gateway_max_artifact_resolve_size_bytes": (
                                    self.gateway_max_artifact_resolve_size_bytes
                                    if hasattr(
                                        self, "gateway_max_artifact_resolve_size_bytes"
                                    )
                                    else -1
                                ),
                                "gateway_recursive_embed_depth": (
                                    self.gateway_recursive_embed_depth
                                    if hasattr(self, "gateway_recursive_embed_depth")
                                    else 12
                                ),
                            }

                            log.debug(
                                "%s Text-based artifact. Resolving late embeds and templates.",
                                log_id_prefix,
                            )

                            # Resolve late embeds
                            resolved_content_str = await resolve_embeds_recursively_in_string(
                                text=content_str,
                                context=context_for_resolver,
                                resolver_func=evaluate_embed,
                                types_to_resolve=LATE_EMBED_TYPES,
                                resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT,
                                log_identifier=f"{log_id_prefix}[RecursiveResolve]",
                                config=config_for_resolver,
                                max_depth=config_for_resolver[
                                    "gateway_recursive_embed_depth"
                                ],
                                max_total_size=config_for_resolver[
                                    "gateway_max_artifact_resolve_size_bytes"
                                ],
                            )

                            # Template blocks are automatically resolved by resolve_embeds_recursively_in_string
                            # when resolving late embeds. No need to call template resolution separately.

                            content_bytes = resolved_content_str.encode("utf-8")
                            log.info(
                                "%s Resolved embeds (including templates). Final size: %d bytes.",
                                log_id_prefix,
                                len(content_bytes),
                            )
                        except Exception as resolve_err:
                            log.warning(
                                "%s Failed to resolve embeds/templates: %s. Returning original content.",
                                log_id_prefix,
                                resolve_err,
                            )
                            # Fall through to return original content_bytes

                    log.info(
                        "%s Successfully loaded %d bytes for artifact '%s'.",
                        log_id_prefix,
                        len(content_bytes),
                        filename,
                    )
                    return content_bytes
                else:
                    log.warning(
                        "%s Artifact '%s' (version: %s) loaded but has no content.",
                        log_id_prefix,
                        filename,
                        version,
                    )
                    return None
            else:
                log.warning(
                    "%s Failed to load artifact '%s' (version: %s). Status: %s",
                    log_id_prefix,
                    filename,
                    version,
                    artifact_data.get("status"),
                )
                return None
        except Exception as e:
            log.exception(
                "%s Failed to load artifact '%s': %s", log_id_prefix, filename, e
            )
            return None

    async def list_artifacts(
        self, context: "ResponseContext"
    ) -> List[ArtifactInfo]:
        """Lists all artifacts available in the user's context."""
        log_id_prefix = f"{self.log_identifier}[ListArtifacts]"
        if not self.artifact_service:
            log.error("%s Artifact service is not configured.", log_id_prefix)
            return []
        try:
            artifact_infos = await get_artifact_info_list(
                artifact_service=self.artifact_service,
                app_name=self.gateway_id,
                user_id=context.user_id,
                session_id=context.session_id,
            )
            log.info(
                "%s Found %d artifacts for user %s in session %s.",
                log_id_prefix,
                len(artifact_infos),
                context.user_id,
                context.session_id,
            )
            return artifact_infos
        except Exception as e:
            log.exception(
                "%s Failed to list artifacts for user %s: %s",
                log_id_prefix,
                context.user_id,
                e,
            )
            return []

    def list_agents(self) -> List[Any]:
        """Lists all agents currently registered in the agent registry."""
        log_id_prefix = f"{self.log_identifier}[ListAgents]"
        try:
            agent_names = self.agent_registry.get_agent_names()
            agents = []
            for agent_name in agent_names:
                agent_card = self.agent_registry.get_agent(agent_name)
                if agent_card:
                    agents.append(agent_card)
            log.info("%s Found %d registered agents.", log_id_prefix, len(agents))
            return agents
        except Exception as e:
            log.exception("%s Failed to list agents: %s", log_id_prefix, e)
            return []

    async def submit_feedback(self, feedback: "SamFeedback") -> None:
        """Handles feedback submission from an adapter."""
        log_id_prefix = f"{self.log_identifier}[SubmitFeedback]"
        feedback_config = self.get_config("feedback_publishing", {})

        if not feedback_config.get("enabled", False):
            log.debug("%s Feedback received but publishing is disabled.", log_id_prefix)
            return

        log.info(
            "%s Received feedback for task %s: %s",
            log_id_prefix,
            feedback.task_id,
            feedback.rating,
        )

        feedback_payload = {
            "id": f"feedback-{uuid.uuid4().hex}",
            "session_id": feedback.session_id,
            "task_id": feedback.task_id,
            "user_id": feedback.user_id,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "created_time": datetime.now(timezone.utc).isoformat(),
            "gateway_id": self.gateway_id,
        }

        topic = get_feedback_topic(self.namespace)
        self.publish_a2a_message(topic=topic, payload=feedback_payload)
        log.info(
            "%s Published feedback event for task %s to topic '%s'.",
            log_id_prefix,
            feedback.task_id,
            topic,
        )

    def add_timer(
        self, delay_ms: int, callback: Callable, interval_ms: Optional[int] = None
    ) -> str:
        timer_id = f"adapter-timer-{len(self.timer_manager.timers)}"
        super().add_timer(delay_ms, timer_id, interval_ms, {"callback": callback})
        return timer_id

    def handle_timer_event(self, timer_data: Dict[str, Any]):
        """Handles timer events and calls the adapter's callback."""
        callback = timer_data.get("payload", {}).get("callback")
        if callable(callback):
            # Run async callback in the component's event loop
            asyncio.run_coroutine_threadsafe(callback(), self.get_async_loop())
        else:
            log.warning("Timer fired but no valid callback found in payload.")

    def get_task_state(self, task_id: str, key: str, default: Any = None) -> Any:
        cache_key = f"task_state:{task_id}:{key}"
        value = self.cache_service.get_data(cache_key)
        return value if value is not None else default

    def set_task_state(self, task_id: str, key: str, value: Any) -> None:
        cache_key = f"task_state:{task_id}:{key}"
        # Use a reasonable expiry to prevent orphaned state
        self.cache_service.add_data(cache_key, value, expiry=3600)  # 1 hour

    def get_session_state(self, session_id: str, key: str, default: Any = None) -> Any:
        cache_key = f"session_state:{session_id}:{key}"
        value = self.cache_service.get_data(cache_key)
        return value if value is not None else default

    def set_session_state(self, session_id: str, key: str, value: Any) -> None:
        cache_key = f"session_state:{session_id}:{key}"
        # Use a longer expiry for session state
        self.cache_service.add_data(cache_key, value, expiry=86400)  # 24 hours

    def process_sac_template(
        self,
        template: str,
        payload: Any = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        # This is a complex feature of SAC that requires careful implementation.
        # For now, we raise an error.
        raise NotImplementedError(
            "process_sac_template is not yet implemented in GenericGatewayComponent."
        )

    # --- BaseGatewayComponent Abstract Method Implementations ---

    async def _async_setup_and_run(self) -> None:
        """Main async logic for the generic gateway component.

        Initializes the adapter before calling base class setup to ensure
        the adapter context is available before any message processing begins.
        This guarantees that adapter methods like extract_auth_claims() have
        access to self.context when called.
        """
        log.info("%s Initializing adapter...", self.log_identifier)
        try:
            await self.adapter.init(self)
            log.info("%s Adapter initialized successfully", self.log_identifier)
        except Exception as e:
            log.error("%s Failed to initialize adapter: %s", self.log_identifier, e)
            raise

        await super()._async_setup_and_run()

    def _start_listener(self) -> None:
        """Listener start hook from BaseGatewayComponent.

        For GenericGatewayComponent, adapter initialization is handled in
        _async_setup_and_run() before this method is called. This ensures
        proper async initialization and guarantees the adapter context is
        available before message processing starts.

        Subclasses that need additional listener setup (e.g., starting an
        HTTP server) can override this method.
        """
        # Adapter already initialized in _async_setup_and_run
        log.debug(
            "%s _start_listener called - adapter already initialized",
            self.log_identifier,
        )

    def _stop_listener(self) -> None:
        """Stops the adapter's listener."""
        log.info("%s Calling adapter.cleanup()...", self.log_identifier)
        # The adapter's cleanup method should handle graceful shutdown.
        if self.adapter:
            future = asyncio.run_coroutine_threadsafe(
                self.adapter.cleanup(), self.get_async_loop()
            )
            try:
                future.result(timeout=10)  # Wait for cleanup to finish
            except Exception as e:
                log.error("%s Error during adapter cleanup: %s", self.log_identifier, e)

    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        """Translates an A2A update event to SAM types and calls the adapter."""
        response_context = self._create_response_context(external_request_context)
        sam_update = SamUpdate(is_final=False)

        parts: List[a2a.ContentPart] = []
        if isinstance(event_data, TaskStatusUpdateEvent):
            if event_data.status and event_data.status.message:
                parts = a2a.get_parts_from_message(event_data.status.message)
        elif isinstance(event_data, TaskArtifactUpdateEvent):
            if event_data.artifact:
                parts = a2a.get_parts_from_artifact(event_data.artifact)

        sam_update.parts = self._a2a_parts_to_sam_parts(parts)
        await self.adapter.handle_update(sam_update, response_context)

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        """Translates a final A2A Task object to SAM types and calls the adapter."""
        response_context = self._create_response_context(external_request_context)
        sam_update = SamUpdate(is_final=True)

        all_final_parts: List[a2a.ContentPart] = []
        if task_data.status and task_data.status.message:
            all_final_parts.extend(a2a.get_parts_from_message(task_data.status.message))
        if task_data.artifacts:
            for artifact in task_data.artifacts:
                all_final_parts.extend(a2a.get_parts_from_artifact(artifact))

        # If the original request was streaming, filter out text and file parts
        # from the final response to avoid duplication, as they were already streamed.
        was_streaming = external_request_context.get("is_streaming", False)
        if was_streaming:
            log.debug(
                "%s Filtering final response parts for streaming task %s.",
                self.log_identifier,
                response_context.task_id,
            )
            filtered_parts = [
                part
                for part in all_final_parts
                if not isinstance(part, (TextPart, FilePart))
            ]
            sam_update.parts = self._a2a_parts_to_sam_parts(filtered_parts)
        else:
            sam_update.parts = self._a2a_parts_to_sam_parts(all_final_parts)

        # Send the final content update (which might be empty for streaming tasks)
        await self.adapter.handle_update(sam_update, response_context)

        # Then, signal completion
        await self.adapter.handle_task_complete(response_context)

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        """Translates an A2A error to a SamError and calls the adapter."""
        response_context = self._create_response_context(external_request_context)
        sam_error = self._a2a_error_to_sam_error(error_data)

        await self.adapter.handle_error(sam_error, response_context)

        # Also signal task completion, as an error is a final state
        await self.adapter.handle_task_complete(response_context)

    # --- Unused BaseGatewayComponent Abstract Methods ---
    # These are part of the old gateway pattern and are replaced by the adapter flow.

    async def _extract_initial_claims(
        self, external_event_data: Any
    ) -> Optional[Dict[str, Any]]:
        # This is now handled by `handle_external_input` calling the adapter directly.
        # This method should not be called in the generic gateway flow.
        log.warning(
            "%s _extract_initial_claims called on GenericGatewayComponent. This should not happen.",
            self.log_identifier,
        )
        return None

    async def _translate_external_input(
        self, external_event: Any
    ) -> Tuple[str, List[a2a.ContentPart], Dict[str, Any]]:
        # This is now handled by `handle_external_input` calling `adapter.prepare_task`.
        # This method should not be called in the generic gateway flow.
        log.warning(
            "%s _translate_external_input called on GenericGatewayComponent. This should not happen.",
            self.log_identifier,
        )
        raise NotImplementedError(
            "_translate_external_input is not used in GenericGatewayComponent"
        )

    # --- Private Helper Methods ---

    def _create_response_context(
        self, external_request_context: Dict[str, Any]
    ) -> ResponseContext:
        """Builds a ResponseContext from the stored external request context."""
        user_identity = external_request_context.get("user_identity", {})
        return ResponseContext(
            task_id=external_request_context.get("a2a_task_id_for_event"),
            session_id=external_request_context.get("a2a_session_id"),
            user_id=user_identity.get("id"),
            platform_context=external_request_context,
        )

    def _sam_parts_to_a2a_parts(
        self, sam_parts: List[Union[SamTextPart, SamFilePart, SamDataPart]]
    ) -> List[a2a.ContentPart]:
        """Converts a list of SAM parts to A2A parts."""
        a2a_parts = []
        for part in sam_parts:
            if isinstance(part, SamTextPart):
                a2a_parts.append(a2a.create_text_part(part.text))
            elif isinstance(part, SamFilePart):
                if part.content_bytes:
                    a2a_parts.append(
                        a2a.create_file_part_from_bytes(
                            content_bytes=part.content_bytes,
                            name=part.name,
                            mime_type=part.mime_type,
                        )
                    )
                elif part.uri:
                    a2a_parts.append(
                        a2a.create_file_part_from_uri(
                            uri=part.uri,
                            name=part.name,
                            mime_type=part.mime_type,
                        )
                    )
            elif isinstance(part, SamDataPart):
                a2a_parts.append(a2a.create_data_part(part.data))
        return a2a_parts

    def _a2a_parts_to_sam_parts(
        self, a2a_parts: List[a2a.ContentPart]
    ) -> List[Union[SamTextPart, SamFilePart, SamDataPart]]:
        """Converts a list of A2A parts to SAM parts."""
        sam_parts = []
        for part in a2a_parts:
            if isinstance(part, TextPart):
                sam_parts.append(SamTextPart(text=part.text))
            elif isinstance(part, FilePart):
                sam_parts.append(
                    SamFilePart(
                        name=a2a.get_filename_from_file_part(part),
                        content_bytes=a2a.get_bytes_from_file_part(part),
                        uri=a2a.get_uri_from_file_part(part),
                        mime_type=a2a.get_mimetype_from_file_part(part),
                    )
                )
            elif isinstance(part, A2ADataPart):
                sam_parts.append(
                    SamDataPart(
                        data=a2a.get_data_from_data_part(part),
                        metadata=a2a.get_metadata_from_part(part),
                    )
                )
        return sam_parts

    def _a2a_error_to_sam_error(self, error: JSONRPCError) -> SamError:
        """Converts an A2A JSONRPCError to a SamError."""
        category = "PROTOCOL_ERROR"
        if isinstance(error.data, dict):
            task_status = error.data.get("taskStatus")
            if task_status == TaskState.failed:
                category = "FAILED"
            elif task_status == TaskState.canceled:
                category = "CANCELED"

        return SamError(
            message=error.message,
            code=error.code,
            category=category,
        )
