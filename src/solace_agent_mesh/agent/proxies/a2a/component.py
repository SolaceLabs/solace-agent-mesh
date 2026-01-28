"""
Concrete implementation of a proxy for standard A2A-over-HTTPS agents.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union
from urllib.parse import urlparse

import httpx

from a2a.client import (
    A2ACardResolver,
    Client,
    ClientConfig,
    ClientFactory,
    A2AClientHTTPError,
    AuthInterceptor,
    InMemoryContextCredentialStore,
)
from a2a.client.errors import A2AClientJSONRPCError
from .oauth_token_cache import OAuth2TokenCache
from a2a.types import (
    A2ARequest,
    AgentCard,
    Artifact,
    CancelTaskRequest,
    DataPart,
    InternalError,
    Message,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
    TransportProtocol,
)

from solace_ai_connector.common.log import log

from datetime import datetime, timezone

from ....common import a2a
from ....common.auth_headers import build_full_auth_headers
from ....common.oauth import OAuth2Client, validate_https_url
from ....common.data_parts import AgentProgressUpdateData
from ....agent.utils.artifact_helpers import format_artifact_uri
from ..base.component import BaseProxyComponent

if TYPE_CHECKING:
    from ..base.proxy_task_context import ProxyTaskContext

info = {
    "class_name": "A2AProxyComponent",
    "description": "A proxy for standard A2A-over-HTTPS agents.",
    "config_parameters": [],
    "input_schema": {},
    "output_schema": {},
}


class A2AProxyComponent(BaseProxyComponent):
    """
    Concrete proxy component for standard A2A-over-HTTPS agents.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Cache Client instances per (agent_name, session_id, is_streaming) to ensure
        # each session gets its own client with session-specific credentials and streaming mode
        self._a2a_clients: Dict[Tuple[str, str, bool], Client] = {}
        self._credential_store: InMemoryContextCredentialStore = (
            InMemoryContextCredentialStore()
        )
        self._auth_interceptor: AuthInterceptor = AuthInterceptor(
            self._credential_store
        )
        # OAuth 2.0 token cache for client credentials flow
        # Why use asyncio.Lock: Ensures thread-safe access to the token cache
        # when multiple concurrent requests target the same agent
        self._oauth_token_cache: OAuth2TokenCache = OAuth2TokenCache()

        # OAuth 2.0 client for protocol operations (no retry for A2A)
        self._oauth_client = OAuth2Client()

        # Index agent configs by name for O(1) lookup (performance optimization)
        self._agent_config_by_name: Dict[str, Dict[str, Any]] = {
            agent["name"]: agent for agent in self.proxied_agents_config
        }

        # NEW: OAuth 2.0 authorization code support (enterprise feature)
        # Stores paused tasks waiting for user authorization
        self._paused_a2a_oauth2_tasks: Dict[str, Dict[str, Any]] = {}
        # Caches CredentialManagerWithDiscovery instances per agent
        self._a2a_oauth2_credential_managers: Dict[str, Any] = {}

        # NEW: Initialize enterprise features for OAuth2 support
        try:
            from solace_agent_mesh_enterprise.init_enterprise_component import (
                init_enterprise_proxy_features
            )
            init_enterprise_proxy_features(self)
        except ImportError:
            pass  # Enterprise not installed

        # OAuth 2.0 configuration is now validated by Pydantic models at app initialization
        # No need for separate _validate_oauth_config() method

    def _get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        O(1) lookup of agent configuration by name.

        Args:
            agent_name: The name of the agent to look up.

        Returns:
            The agent configuration dictionary, or None if not found.
        """
        return self._agent_config_by_name.get(agent_name)

    def _extract_security_scheme_name(
        self, agent_card: Optional[AgentCard], auth_type: str, agent_name: str
    ) -> str:
        """
        Extracts the security scheme name from the agent card based on authentication type.

        The A2A SDK's AuthInterceptor uses the security scheme name from the agent card
        to look up credentials in the credential store. This method ensures we use the
        correct scheme name that matches what the agent card expects.

        Args:
            agent_card: The agent card containing security scheme definitions.
            auth_type: The authentication type from config (static_bearer, static_apikey,
                      oauth2_client_credentials, oauth2_authorization_code).
            agent_name: The name of the agent (for logging).

        Returns:
            The security scheme name to use when storing credentials. Falls back to
            default names for backward compatibility if no matching scheme is found
            in the agent card.

        Default fallbacks:
            - static_bearer -> "bearer"
            - static_apikey -> "apikey"
            - oauth2_client_credentials -> "bearer"
            - oauth2_authorization_code -> "oauth2_authorization_code"
        """
        log_identifier = f"{self.log_identifier}[ExtractScheme:{agent_name}]"

        # If no agent card or no security schemes, use default
        if not agent_card or not agent_card.security_schemes:
            default_scheme = self._get_default_scheme_name(auth_type)
            log.debug(
                "%s No security schemes in agent card, using default '%s'",
                log_identifier,
                default_scheme,
            )
            return default_scheme

        scheme_name = None

        # Search for matching security scheme based on auth type
        for name, scheme_wrapper in agent_card.security_schemes.items():
            scheme = scheme_wrapper.root

            if not hasattr(scheme, "type"):
                continue

            scheme_type = scheme.type.lower()

            if auth_type == "static_bearer":
                # Look for HTTP bearer token scheme
                if scheme_type == "http" and hasattr(scheme, "scheme"):
                    if scheme.scheme.lower() == "bearer":
                        scheme_name = name
                        break
                # Also accept oauth2 schemes for bearer tokens (common pattern)
                elif scheme_type == "oauth2":
                    scheme_name = name
                    break

            elif auth_type == "static_apikey":
                # Look for API key scheme
                if scheme_type == "apikey":
                    scheme_name = name
                    break

            elif auth_type == "oauth2_client_credentials":
                # Look for OAuth2 scheme with client credentials flow
                if scheme_type == "oauth2":
                    if hasattr(scheme, "flows") and scheme.flows:
                        if hasattr(scheme.flows, "client_credentials") and scheme.flows.client_credentials:
                            scheme_name = name
                            break
                    # Fallback: accept any oauth2 scheme
                    if not scheme_name:
                        scheme_name = name
                        # Don't break - keep looking for client_credentials flow

            elif auth_type == "oauth2_authorization_code":
                # Look for OAuth2 scheme with authorization code flow
                if scheme_type == "oauth2":
                    if hasattr(scheme, "flows") and scheme.flows:
                        if hasattr(scheme.flows, "authorization_code") and scheme.flows.authorization_code:
                            scheme_name = name
                            break

        # Use extracted scheme name or fall back to default
        if scheme_name:
            log.info(
                "%s Extracted security scheme '%s' from agent card for auth type '%s'",
                log_identifier,
                scheme_name,
                auth_type,
            )
            return scheme_name
        else:
            default_scheme = self._get_default_scheme_name(auth_type)
            log.warning(
                "%s No matching security scheme found in agent card for auth type '%s'. "
                "Using default scheme name '%s'. This may cause authentication failures "
                "if the agent card uses a custom scheme name.",
                log_identifier,
                auth_type,
                default_scheme,
            )
            return default_scheme

    def _get_default_scheme_name(self, auth_type: str) -> str:
        """
        Returns the default security scheme name for backward compatibility.

        Args:
            auth_type: The authentication type from config.

        Returns:
            Default scheme name to use as fallback.
        """
        defaults = {
            "static_bearer": "bearer",
            "static_apikey": "apikey",
            "oauth2_client_credentials": "bearer",
            "oauth2_authorization_code": "oauth2_authorization_code",
        }
        return defaults.get(auth_type, "bearer")

    async def _ensure_credentials(
        self,
        agent_card: Optional[AgentCard],
        auth_type: str,
        agent_name: str,
        session_id: str,
        token: str,
    ) -> None:
        """
        Extracts the security scheme name from the agent card and stores credentials.

        This helper method combines scheme name extraction and credential storage
        to reduce code duplication across authentication types.

        Args:
            agent_card: The agent card (may be None or have no security_schemes).
            auth_type: The authentication type (e.g., "static_bearer").
            agent_name: The agent name (for logging).
            session_id: The session ID for credential isolation.
            token: The authentication token/access_token to store.
        """
        scheme_name = self._extract_security_scheme_name(
            agent_card, auth_type, agent_name
        )
        await self._credential_store.set_credentials(
            session_id, scheme_name, token
        )

    async def _build_headers(
        self,
        agent_name: str,
        agent_config: Dict[str, Any],
        custom_headers_key: str,
        use_auth: bool = True,
    ) -> Dict[str, str]:
        """
        Builds HTTP headers for requests, applying authentication and custom headers.

        Delegates to the common header-building utility and provides the OAuth2
        token fetcher for dynamic token acquisition.

        This method is used for agent card fetching and custom task headers. For
        task invocations, authentication is primarily handled by the A2A SDK's
        AuthInterceptor (see _get_or_create_a2a_client), which uses credentials
        stored in the credential store with scheme names extracted from the agent card.

        Args:
            agent_name: The name of the agent.
            agent_config: The agent configuration dictionary.
            custom_headers_key: Key to look up custom headers in config ('agent_card_headers' or 'task_headers').
            use_auth: Whether to apply authentication headers.

        Returns:
            Dictionary of HTTP headers. Custom headers are applied after auth headers
            and can override them for agent card fetching. For task invocations,
            custom headers are supplementary (applied at httpx client level) and do
            not override AuthInterceptor headers (applied at middleware level).
        """
        return await build_full_auth_headers(
            agent_name=agent_name,
            agent_config=agent_config,
            custom_headers_key=custom_headers_key,
            use_auth=use_auth,
            log_identifier=self.log_identifier,
            oauth_token_fetcher=self._fetch_oauth2_token,
        )

    async def _fetch_agent_card(
        self, agent_config: Dict[str, Any]
    ) -> Optional[AgentCard]:
        """
        Fetches the AgentCard from a downstream A2A agent via HTTPS.

        Applies authentication and custom headers based on configuration:
        - If use_auth_for_agent_card=true, applies the configured authentication
        - Custom agent_card_headers override authentication headers
        """
        agent_name = agent_config.get("name")
        agent_url = agent_config.get("url")
        agent_card_path = agent_config.get("agent_card_path", "/agent/card.json")
        log_identifier = f"{self.log_identifier}[FetchCard:{agent_name}]"

        if not agent_url:
            log.error("%s No URL configured for agent.", log_identifier)
            return None

        try:
            # Build headers based on configuration
            use_auth = agent_config.get("use_auth_for_agent_card", False)
            headers = await self._build_headers(
                agent_name=agent_name,
                agent_config=agent_config,
                custom_headers_key="agent_card_headers",
                use_auth=use_auth,
            )

            if headers:
                log.debug(
                    "%s Fetching agent card with %d custom header(s) (auth=%s)",
                    log_identifier,
                    len(headers),
                    use_auth,
                )
            else:
                log.debug("%s Fetching agent card without authentication", log_identifier)

            log.info("%s Fetching agent card from %s", log_identifier, agent_url)
            async with httpx.AsyncClient(headers=headers) as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=agent_url, agent_card_path=agent_card_path)
                agent_card = await resolver.get_agent_card()
                return agent_card
        except A2AClientHTTPError as e:
            log.error(
                "%s HTTP error fetching agent card from %s: %s",
                log_identifier,
                agent_url,
                e,
            )
        except Exception as e:
            log.exception(
                "%s Unexpected error fetching agent card from %s: %s",
                log_identifier,
                agent_url,
                e,
            )
        return None

    async def _forward_request(
        self, task_context: ProxyTaskContext, request: A2ARequest, agent_name: str
    ) -> None:
        """
        Forwards an A2A request to a downstream A2A-over-HTTPS agent.

        Implements automatic retry logic for OAuth 2.0 authentication failures.
        If a 401 Unauthorized response is received and the agent uses OAuth 2.0,
        the cached token is invalidated and the request is retried once with a
        fresh token.
        """
        log_identifier = (
            f"{self.log_identifier}[ForwardRequest:{task_context.task_id}:{agent_name}]"
        )

        # Store original request for potential resumption (OAuth2 authorization code flow)
        task_context.original_request = request

        # Step 1: Initialize retry counter
        # Why only retry once: Prevents infinite loops on persistent auth failures.
        # First 401 may be due to token expiration between cache check and request;
        # second 401 indicates a configuration or authorization issue (not transient).
        max_auth_retries: int = 1
        auth_retry_count: int = 0

        # Step 2: Check for OAuth2 authorization code flow
        # This auth type requires user interaction and can pause the task,
        # so we check it before attempting normal request flow
        agent_config = self._get_agent_config(agent_name)
        auth_config = agent_config.get("authentication") if agent_config else None
        auth_type = auth_config.get("type") if auth_config else None

        if auth_type == "oauth2_authorization_code":
            try:
                from solace_agent_mesh_enterprise.auth.a2a import (
                    check_authorization_required,
                    request_authorization,
                )

                # Check if user authorization is needed
                needs_auth = await check_authorization_required(
                    component=self,
                    agent_name=agent_name,
                    task_context=task_context,
                )

                if needs_auth:
                    # Pause task and request authorization
                    log.info(
                        "%s User authorization required for agent '%s'. Pausing task.",
                        log_identifier,
                        agent_name,
                    )
                    await request_authorization(
                        component=self,
                        agent_name=agent_name,
                        task_context=task_context,
                    )
                    return  # Exit - task paused, will resume after OAuth callback

            except ImportError:
                log.error(
                    "%s Agent '%s' requires OAuth2 authorization code flow, "
                    "but solace-agent-mesh-enterprise is not installed.",
                    log_identifier,
                    agent_name,
                )
                raise ValueError(
                    f"Agent '{agent_name}' requires OAuth2 authorization code flow, "
                    "but solace-agent-mesh-enterprise is not installed."
                )

        # Step 3: Normal request flow for all other auth types
        # (static_bearer, static_apikey, oauth2_client_credentials, or authorized oauth2_authorization_code)
        received_final_task = False

        while auth_retry_count <= max_auth_retries:
            try:
                # Get or create A2AClient
                client = await self._get_or_create_a2a_client(agent_name, task_context)
                if not client:
                    raise ValueError(
                        f"Could not create A2A client for agent '{agent_name}'"
                    )

                # Create context with sessionId (camelCase!) so AuthInterceptor can look up credentials
                from a2a.client.middleware import ClientCallContext

                session_id = task_context.a2a_context.get(
                    "session_id", "default_session"
                )
                call_context = ClientCallContext(state={"sessionId": session_id})

                # Forward the request with context
                if isinstance(
                    request, (SendStreamingMessageRequest, SendMessageRequest)
                ):
                    # Extract the Message from the request params
                    message_to_send = request.params.message

                    # Check if this is a RUN_BASED request by inspecting message metadata
                    # For RUN_BASED requests, omit context_id to indicate independent tasks
                    if message_to_send.metadata:
                        session_behavior = message_to_send.metadata.get("sessionBehavior")
                        if session_behavior:
                            session_behavior = str(session_behavior).upper()
                            if session_behavior == "RUN_BASED" and message_to_send.context_id:
                                # For RUN_BASED requests, omit context_id entirely
                                # Each request is independent with no logical grouping
                                log.debug(
                                    "%s RUN_BASED request detected. Omitting context_id "
                                    "(independent task)",
                                    log_identifier,
                                )
                                message_to_send = message_to_send.model_copy(
                                    update={"context_id": None}
                                )

                    # WORKAROUND: The A2A SDK has a bug in ClientTaskManager that breaks streaming.
                    # For streaming requests, we bypass the Client.send_message() method and call
                    # the transport directly to avoid the buggy ClientTaskManager.
                    # Non-streaming requests work fine with the normal client method.
                    # TODO: Remove this workaround once SDK bug is fixed upstream.
                    if task_context.a2a_context.get("is_streaming", True):
                        # Access transport directly (private API) to bypass ClientTaskManager
                        log.debug(
                            "%s Using transport directly for streaming request (SDK bug workaround)",
                            log_identifier,
                        )
                        async for raw_event in client._transport.send_message_streaming(
                            request.params, context=call_context
                        ):
                            # Process raw events directly without ClientTaskManager
                            await self._process_downstream_response(
                                raw_event, task_context, client, agent_name
                            )
                            # Check if this is a final task
                            if isinstance(raw_event, Task) and raw_event.status:
                                if raw_event.status.state in [TaskState.completed, TaskState.failed, TaskState.canceled]:
                                    received_final_task = True
                    else:
                        # Non-streaming: use normal client method (works fine)
                        log.debug(
                            "%s Using normal client method for non-streaming request",
                            log_identifier,
                        )
                        async for event in client.send_message(
                            message_to_send, context=call_context
                        ):
                            await self._process_downstream_response(
                                event, task_context, client, agent_name
                            )
                            # Check if this is a final task (event is tuple of (Task, Optional[UpdateEvent]))
                            if isinstance(event, tuple) and len(event) > 0:
                                task = event[0]
                                if isinstance(task, Task) and task.status:
                                    if task.status.state in [TaskState.completed, TaskState.failed, TaskState.canceled]:
                                        received_final_task = True
                elif isinstance(request, CancelTaskRequest):
                    # Forward cancel request to downstream agent using the downstream task ID
                    # The request.params.id contains SAM's task ID, but we need to send
                    # the downstream agent's task ID for the cancel to work

                    if not task_context.downstream_task_id:
                        log.error(
                            "%s Cannot forward cancel request: downstream task ID not yet captured for SAM task %s",
                            log_identifier,
                            task_context.task_id,
                        )
                        # Create an error response
                        from a2a.types import InvalidRequestError
                        error = InvalidRequestError(
                            message=f"Cannot cancel task {task_context.task_id}: downstream task ID not available",
                            data={"taskId": task_context.task_id}
                        )
                        # Publish error response
                        await self._publish_error_response(error, task_context.a2a_context)
                        break

                    log.info(
                        "%s Forwarding cancel request for task %s (SAM ID: %s, downstream ID: %s) to downstream agent.",
                        log_identifier,
                        task_context.downstream_task_id,
                        task_context.task_id,
                        task_context.downstream_task_id,
                    )

                    # Create new params with the downstream task ID
                    from a2a.types import TaskIdParams
                    downstream_params = TaskIdParams(id=task_context.downstream_task_id)

                    # Use the modern client's cancel_task method with the downstream task ID
                    result = await client.cancel_task(
                        downstream_params, context=call_context
                    )
                    # Publish the canceled task response
                    await self._publish_task_response(result, task_context.a2a_context)
                else:
                    log.warning(
                        "%s Unhandled request type for forwarding: %s",
                        log_identifier,
                        type(request),
                    )

                # Step 5: Success - break out of retry loop
                break

            except RuntimeError as e:
                # WORKAROUND: The A2A SDK raises StopAsyncIteration for connection failures,
                # which Python 3.7+ automatically converts to RuntimeError (PEP 479).
                # We catch this here to provide a more meaningful error message.
                # This should be fixed upstream in the A2A SDK to raise proper connection exceptions.
                if "StopAsyncIteration" in str(e):
                    error_msg = (
                        f"Failed to connect to agent '{agent_name}': "
                        "Connection refused or agent unreachable"
                    )
                    log.error(
                        "%s Connection error (SDK raised StopAsyncIteration): %s",
                        log_identifier,
                        error_msg,
                    )
                    # Raise a more descriptive error that will be caught by the outer handler
                    raise ConnectionError(error_msg) from e
                else:
                    # Some other RuntimeError - re-raise it
                    raise

            except A2AClientJSONRPCError as e:
                # Handle JSON-RPC protocol errors

                # Special case: Task already in terminal state (canceled/completed/failed)
                # This is not a fatal error - the cancellation is effectively a no-op
                if (e.error.code == -32002 and
                    "cannot be canceled" in e.error.message.lower() and
                    isinstance(request, CancelTaskRequest)):
                    log.warning(
                        "%s Task %s is already in terminal state: %s. Treating as successful cancellation.",
                        log_identifier,
                        task_context.downstream_task_id,
                        e.error.message,
                    )
                    # Task is already done - return success (cancellation is effectively complete)
                    # We don't need to publish a response because the task already sent its final response
                    break

                log.error(
                    "%s JSON-RPC error from agent '%s': %s",
                    log_identifier,
                    agent_name,
                    e.error,
                )
                # TODO: Publish error response to Solace
                # Do not retry - this is a protocol-level error
                raise

            except ConnectionError as e:
                # Connection errors (including those converted from RuntimeError above)
                log.error(
                    "%s Connection error forwarding request to agent '%s': %s",
                    log_identifier,
                    agent_name,
                    e,
                )
                raise

            except A2AClientHTTPError as e:
                # Step 4: Add specific handling for 401 Unauthorized errors
                # The error might be wrapped in an SSE parsing error, so we need to check
                # if the underlying cause is a 401
                is_401_error = False

                # Check if this is directly a 401
                if hasattr(e, "status_code") and e.status_code == 401:
                    is_401_error = True
                # Check if this is an SSE parsing error caused by a 401 response
                elif "401" in str(e) or "Unauthorized" in str(e):
                    is_401_error = True
                # Check if the error message mentions application/json content type
                # (which is what 401 responses typically return)
                elif "application/json" in str(e) and "text/event-stream" in str(e):
                    # This is likely an SSE parsing error caused by a 401 JSON response
                    is_401_error = True

                if is_401_error and auth_retry_count < max_auth_retries:
                    log.warning(
                        "%s Received 401 Unauthorized from agent '%s' (detected from error: %s). Attempting token refresh (retry %d/%d).",
                        log_identifier,
                        agent_name,
                        str(e)[:100],
                        auth_retry_count + 1,
                        max_auth_retries,
                    )

                    should_retry = await self._handle_auth_error(
                        agent_name, task_context
                    )
                    if should_retry:
                        auth_retry_count += 1
                        continue  # Retry with fresh token

                # Not a retryable auth error, or max retries exceeded
                log.exception(
                    "%s HTTP error forwarding request: %s",
                    log_identifier,
                    e,
                )
                raise

            except Exception as e:
                log.exception(
                    "%s Unexpected error forwarding request: %s",
                    log_identifier,
                    e,
                )
                # Let base class exception handler in _handle_a2a_request catch this
                # and publish an error response.
                raise

        # After retry loop completes - check if we received a final task
        # This detects cases where the stream closes without error but also without final response
        if not received_final_task and isinstance(request, (SendStreamingMessageRequest, SendMessageRequest)):
            from ....common.a2a import create_error_response

            error_msg = f"Remote agent '{agent_name}' disconnected without completing the task. Agent may have crashed."
            log.error("%s %s", log_identifier, error_msg)

            error = InternalError(message=error_msg, data={"agent_name": agent_name})
            reply_topic = task_context.a2a_context.get("reply_to_topic")
            if reply_topic:
                response = create_error_response(error=error, request_id=task_context.a2a_context.get("jsonrpc_request_id"))
                self._publish_a2a_message(response.model_dump(exclude_none=True), reply_topic)

    async def _handle_auth_error(
        self, agent_name: str, task_context: ProxyTaskContext
    ) -> bool:
        """
        Handles authentication errors by invalidating cached tokens and clients.

        This method is called when a 401 Unauthorized response is received from
        a downstream agent. It checks if the agent uses OAuth 2.0 authentication,
        and if so, invalidates the cached token and removes ALL cached clients
        for this agent/session combination (both streaming and non-streaming).

        Args:
            agent_name: The name of the agent that returned 401.
            task_context: The current task context.

        Returns:
            True if token was invalidated and retry should be attempted.
            False if no retry should be attempted (e.g., static token).
        """
        log_identifier = f"{self.log_identifier}[AuthError:{agent_name}]"

        # Step 1: Retrieve agent configuration using O(1) lookup
        agent_config = self._get_agent_config(agent_name)

        if not agent_config:
            log.warning(
                "%s Agent configuration not found. Cannot handle auth error.",
                log_identifier,
            )
            return False

        # Step 2: Check authentication type
        auth_config = agent_config.get("authentication")
        if not auth_config:
            log.debug(
                "%s No authentication configured for agent. No retry needed.",
                log_identifier,
            )
            return False

        auth_type = auth_config.get("type")
        if not auth_type:
            # Legacy config - infer from scheme
            scheme = auth_config.get("scheme", "bearer")
            auth_type = "static_bearer" if scheme == "bearer" else "static_apikey"

        if auth_type != "oauth2_client_credentials":
            log.debug(
                "%s Agent uses '%s' authentication (not OAuth 2.0). No retry for static tokens.",
                log_identifier,
                auth_type,
            )
            return False

        # Step 3: Invalidate cached OAuth token
        log.info(
            "%s Invalidating cached OAuth 2.0 token for agent '%s'.",
            log_identifier,
            agent_name,
        )
        await self._oauth_token_cache.invalidate(agent_name)

        # Step 4: Remove ALL cached Clients for this agent/session combination
        # We clear both streaming and non-streaming clients because:
        # 1. Both share the same session_id in the credential store
        # 2. Both would have been created with the same expired token
        # 3. We want fresh tokens for any subsequent requests
        # The cache key is a 3-tuple: (agent_name, session_id, is_streaming)
        session_id = task_context.a2a_context.get("session_id", "default_session")

        clients_removed = 0
        for is_streaming in [True, False]:
            cache_key = (agent_name, session_id, is_streaming)
            if cache_key in self._a2a_clients:
                self._a2a_clients.pop(cache_key)
                clients_removed += 1
                log.info(
                    "%s Removed cached Client for agent '%s' session '%s' streaming=%s.",
                    log_identifier,
                    agent_name,
                    session_id,
                    is_streaming,
                )

        if clients_removed == 0:
            log.warning(
                "%s No cached Clients found for agent '%s' session '%s'. This is unexpected.",
                log_identifier,
                agent_name,
                session_id,
            )
        else:
            log.info(
                "%s Removed %d cached Client(s). Will create fresh client(s) with new token on retry.",
                log_identifier,
                clients_removed,
            )

        # Step 5: Return True to signal retry should be attempted
        log.info(
            "%s Auth error handling complete. Retry will be attempted with fresh token.",
            log_identifier,
        )
        return True

    async def _fetch_oauth2_token(
        self, agent_name: str, auth_config: Dict[str, Any]
    ) -> str:
        """
        Fetches an OAuth 2.0 access token using the client credentials flow.

        This method implements token caching to avoid unnecessary token requests.
        Tokens are cached per agent and automatically expire based on the configured
        cache duration (default: 55 minutes).

        Args:
            agent_name: The name of the agent (used as cache key).
            auth_config: Authentication configuration dictionary containing:
                - token_url: OAuth 2.0 token endpoint (required)
                - client_id: OAuth 2.0 client identifier (required)
                - client_secret: OAuth 2.0 client secret (required)
                - scope: (optional) Space-separated scope string
                - token_cache_duration_seconds: (optional) Cache duration in seconds

        Returns:
            A valid OAuth 2.0 access token (string).

        Raises:
            ValueError: If required OAuth parameters are missing or invalid.
            httpx.HTTPStatusError: If token request returns non-2xx status.
            httpx.RequestError: If network error occurs.
        """
        log_identifier = f"{self.log_identifier}[OAuth2:{agent_name}]"

        # Step 1: Check cache first
        cached_token = await self._oauth_token_cache.get(agent_name)
        if cached_token:
            log.debug("%s Using cached OAuth token.", log_identifier)
            return cached_token

        # Step 2: Validate required parameters
        token_url = auth_config.get("token_url")
        client_id = auth_config.get("client_id")
        client_secret = auth_config.get("client_secret")

        if not all([token_url, client_id, client_secret]):
            raise ValueError(
                f"{log_identifier} OAuth 2.0 client credentials flow requires "
                "'token_url', 'client_id', and 'client_secret'."
            )

        # SECURITY: Enforce HTTPS for token URL using common utility
        validate_https_url(token_url)

        # Step 3: Extract optional parameters
        scope = auth_config.get("scope", "")
        # Why 3300 seconds (55 minutes): Provides a 5-minute safety margin before
        # typical 60-minute token expiration, preventing token expiration mid-request
        cache_duration = auth_config.get("token_cache_duration_seconds", 3300)

        # Step 4: Log token acquisition attempt
        # SECURITY: Never log client_secret or access_token to prevent credential leakage
        log.info(
            "%s Fetching new OAuth 2.0 token from %s (scope: %s)",
            log_identifier,
            token_url,
            scope or "default",
        )

        try:
            # Step 5: Fetch token using common OAuth client (no retry for A2A)
            token_data = await self._oauth_client.fetch_client_credentials_token(
                token_url=token_url,
                client_id=client_id,
                client_secret=client_secret,
                scope=scope,
                verify=True,
                timeout=30.0,
            )

            access_token = token_data["access_token"]

            # Step 6: Cache the token
            await self._oauth_token_cache.set(
                agent_name, access_token, cache_duration
            )

            # Step 7: Log success
            log.info(
                "%s Successfully obtained OAuth 2.0 token (cached for %ds)",
                log_identifier,
                cache_duration,
            )

            # Step 8: Return access token
            return access_token

        except httpx.HTTPStatusError as e:
            log.error(
                "%s OAuth 2.0 token request failed with status %d: %s",
                log_identifier,
                e.response.status_code,
                e.response.text,
            )
            raise
        except httpx.RequestError as e:
            log.error(
                "%s OAuth 2.0 token request failed: %s",
                log_identifier,
                e,
            )
            raise
        except Exception as e:
            log.exception(
                "%s Unexpected error fetching OAuth 2.0 token: %s",
                log_identifier,
                e,
            )
            raise

    async def _get_or_create_a2a_client(
        self, agent_name: str, task_context: ProxyTaskContext
    ) -> Optional[Client]:
        """
        Gets a cached Client or creates a new one for the given agent, session, and streaming mode.

        Caches clients per (agent_name, session_id, is_streaming) to ensure each session gets its
        own client with session-specific credentials and the correct streaming mode. This is necessary because:
        1. The A2A SDK's AuthInterceptor uses session-based credential lookup
        2. The Client's streaming mode is set at creation time and cannot be changed

        Supports multiple authentication types:
        - static_bearer: Static bearer token authentication
        - static_apikey: Static API key authentication
        - oauth2_client_credentials: OAuth 2.0 Client Credentials flow with automatic token refresh
        - oauth2_authorization_code: OAuth 2.0 Authorization Code flow

        For backward compatibility, legacy configurations without a 'type' field
        will have their type inferred from the 'scheme' field.

        The client's streaming mode is determined by the original request type from
        the gateway (message/send vs message/stream).
        """
        session_id = task_context.a2a_context.get("session_id", "default_session")
        is_streaming = task_context.a2a_context.get("is_streaming", True)
        cache_key = (agent_name, session_id, is_streaming)

        if cache_key in self._a2a_clients:
            return self._a2a_clients[cache_key]

        # Use O(1) lookup for agent configuration
        agent_config = self._get_agent_config(agent_name)
        if not agent_config:
            log.error(f"No configuration found for proxied agent '{agent_name}'")
            return None

        agent_card = self.agent_registry.get_agent(agent_name)
        if not agent_card:
            log.error(f"Agent card not found for '{agent_name}' in registry.")
            return None

        # Check if we should use the configured URL or the agent card URL
        use_agent_card_url = agent_config.get("use_agent_card_url", True)
        if not use_agent_card_url:
            # Override the agent card URL with the configured URL
            configured_url = agent_config.get("url")
            log.info(
                "%s Overriding agent card URL with configured URL for agent '%s': %s",
                self.log_identifier,
                agent_name,
                configured_url,
            )
            # Create a modified copy of the agent card with the configured URL
            agent_card = agent_card.model_copy(update={"url": configured_url})

        # Resolve timeout - ensure we always have a valid timeout value
        default_timeout = self.get_config("default_request_timeout_seconds", 300)
        agent_timeout = agent_config.get("request_timeout_seconds")
        if agent_timeout is None:
            agent_timeout = default_timeout
        log.info("Using timeout of %ss for agent '%s'.", agent_timeout, agent_name)

        # Build custom headers for task invocation
        # Authentication handling depends on whether the agent card defines security_schemes:
        # - If agent card HAS security_schemes: Use A2A SDK's AuthInterceptor (middleware level)
        #   which looks up credentials from the credential store using scheme names
        # - If agent card has NO security_schemes: Apply auth headers directly via httpx client
        #   since AuthInterceptor cannot work without security_schemes defined
        # This ensures authentication works both with compliant A2A agents (with security_schemes)
        # and legacy/non-compliant agents (without security_schemes) based solely on YAML/DB config.
        has_security_schemes = bool(agent_card and agent_card.security_schemes)
        task_headers = await self._build_headers(
            agent_name=agent_name,
            agent_config=agent_config,
            custom_headers_key="task_headers",
            use_auth=not has_security_schemes,  # Apply auth directly if no security_schemes
        )

        # Create a new httpx client with the specific timeout and custom headers for this agent
        # httpx.Timeout requires explicit values for connect, read, write, and pool
        httpx_client_for_agent = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=agent_timeout,
                read=agent_timeout,
                write=agent_timeout,
                pool=agent_timeout,
            ),
            headers=task_headers if task_headers else None,
        )

        if task_headers:
            log.info(
                "%s Applied %d custom task header(s) for agent '%s'",
                self.log_identifier,
                len(task_headers),
                agent_name,
            )

        # Setup authentication if configured
        # Track whether AuthInterceptor is needed (separate from has_security_schemes)
        # because oauth2_authorization_code requires AuthInterceptor even without security_schemes
        needs_auth_interceptor = has_security_schemes

        auth_config = agent_config.get("authentication")
        if auth_config:
            auth_type = auth_config.get("type")

            # Determine auth type (with backward compatibility)
            if not auth_type:
                # Legacy config: infer type from 'scheme' field
                scheme = auth_config.get("scheme", "bearer")
                if scheme == "bearer":
                    auth_type = "static_bearer"
                elif scheme == "apikey":
                    auth_type = "static_apikey"
                else:
                    raise ValueError(
                        f"Unknown legacy authentication scheme '{scheme}' for agent '{agent_name}'. "
                        f"Supported schemes: 'bearer', 'apikey'."
                    )

                log.warning(
                    "%s Using legacy authentication config for agent '%s'. "
                    "Consider migrating to 'type' field.",
                    self.log_identifier,
                    agent_name,
                )

            log.info(
                "%s Configuring authentication type '%s' for agent '%s'",
                self.log_identifier,
                auth_type,
                agent_name,
            )

            # Route to appropriate handler
            if auth_type == "static_bearer":
                token = auth_config.get("token")
                if not token:
                    raise ValueError(
                        f"Authentication type 'static_bearer' requires 'token' for agent '{agent_name}'"
                    )
                # Only store credentials in credential store if agent card has security_schemes
                # (AuthInterceptor requires security_schemes to work)
                # If no security_schemes, auth is applied directly via httpx headers
                if has_security_schemes:
                    await self._ensure_credentials(
                        agent_card, auth_type, agent_name, session_id, token
                    )

            elif auth_type == "static_apikey":
                token = auth_config.get("token")
                if not token:
                    raise ValueError(
                        f"Authentication type 'static_apikey' requires 'token' for agent '{agent_name}'"
                    )
                # Only store credentials in credential store if agent card has security_schemes
                # (AuthInterceptor requires security_schemes to work)
                # If no security_schemes, auth is applied directly via httpx headers
                if has_security_schemes:
                    await self._ensure_credentials(
                        agent_card, auth_type, agent_name, session_id, token
                    )

            elif auth_type == "oauth2_client_credentials":
                # OAuth 2.0 Client Credentials Flow
                try:
                    access_token = await self._fetch_oauth2_token(
                        agent_name, auth_config
                    )
                    # Only store credentials in credential store if agent card has security_schemes
                    # (AuthInterceptor requires security_schemes to work)
                    # If no security_schemes, auth is applied directly via httpx headers
                    if has_security_schemes:
                        await self._ensure_credentials(
                            agent_card, auth_type, agent_name, session_id, access_token
                        )
                except Exception as e:
                    log.error(
                        "%s Failed to obtain OAuth 2.0 token for agent '%s': %s",
                        self.log_identifier,
                        agent_name,
                        e,
                    )
                    raise

            elif auth_type == "oauth2_authorization_code":
                # OAuth 2.0 Authorization Code Flow (enterprise feature)
                # At this point, user has already authorized (checked in _forward_request)
                # We just need to get the access token from enterprise helpers
                try:
                    from solace_agent_mesh_enterprise.auth.a2a import get_access_token

                    # Get access token (enterprise handles refresh if needed)
                    access_token = await get_access_token(
                        component=self,
                        agent_name=agent_name,
                        task_context=task_context,
                    )

                    if not access_token:
                        raise ValueError(
                            f"No OAuth2 credential found for agent '{agent_name}'. "
                            "User authorization should have completed in _forward_request()."
                        )

                    # ALWAYS use credential store + AuthInterceptor for oauth2_authorization_code
                    # (not conditional like other auth types) because:
                    # 1. Token is fetched AFTER httpx headers are built, so cannot use httpx header approach
                    # 2. Enterprise code expects credential_store + AuthInterceptor pattern for token application
                    # 3. Enterprise requires agent card to exist (enforced in enterprise oauth2_helpers.py:437-439)
                    # 4. This maintains backward compatibility with existing enterprise OAuth2 flows
                    await self._ensure_credentials(
                        agent_card, auth_type, agent_name, session_id, access_token
                    )
                    # Ensure AuthInterceptor is added for this auth type (even if no security_schemes)
                    needs_auth_interceptor = True

                except ImportError:
                    log.error(
                        "%s OAuth2 authorization code requires solace-agent-mesh-enterprise package",
                        self.log_identifier,
                    )
                    raise ValueError(
                        "OAuth2 authorization code requires solace-agent-mesh-enterprise package"
                    )

            else:
                raise ValueError(
                    f"Unsupported authentication type '{auth_type}' for agent '{agent_name}'. "
                    f"Supported types: static_bearer, static_apikey, oauth2_client_credentials, oauth2_authorization_code."
                )

        # Create ClientConfig for the modern client
        # Use the streaming mode from the original request
        config = ClientConfig(
            streaming=is_streaming,
            polling=False,
            httpx_client=httpx_client_for_agent,
            supported_transports=[TransportProtocol.jsonrpc],
            accepted_output_modes=[],
        )

        # Create client using ClientFactory
        # Add AuthInterceptor if:
        # 1. Agent card has security_schemes (standard path), OR
        # 2. Auth type is oauth2_authorization_code (enterprise requirement)
        # Otherwise, auth is handled via httpx client headers
        factory = ClientFactory(config)
        interceptors = [self._auth_interceptor] if needs_auth_interceptor else []
        client = factory.create(
            agent_card,
            consumers=None,
            interceptors=interceptors,
        )

        self._a2a_clients[cache_key] = client
        return client

    async def _handle_outbound_artifacts(
        self,
        response: Any,
        task_context: ProxyTaskContext,
        agent_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Finds artifacts with byte content, saves them to the proxy's artifact store,
        and mutates the response object to replace bytes with a URI.
        It also uses TextParts within an artifact as a description for the saved file.

        Returns:
            A list of dictionaries, each representing a saved artifact with its filename and version.
        """
        from ....agent.utils.artifact_helpers import save_artifact_with_metadata

        log_identifier = (
            f"{self.log_identifier}[HandleOutboundArtifacts:{task_context.task_id}]"
        )
        saved_artifacts_manifest = []

        artifacts_to_process: List[Artifact] = []
        if isinstance(response, Task) and response.artifacts:
            artifacts_to_process = response.artifacts
        elif isinstance(response, TaskArtifactUpdateEvent):
            artifacts_to_process = [response.artifact]

        if not artifacts_to_process:
            return saved_artifacts_manifest

        if not self.artifact_service:
            log.warning(
                "%s Artifact service not configured. Cannot save outbound artifacts.",
                log_identifier,
            )
            return saved_artifacts_manifest

        for artifact in artifacts_to_process:
            contextual_description = "\n".join(
                [
                    a2a.get_text_from_text_part(part.root)
                    for part in artifact.parts
                    if a2a.is_text_part(part)
                ]
            )

            for i, part_container in enumerate(artifact.parts):
                part = part_container.root
                if (
                    a2a.is_file_part(part_container)
                    and a2a.is_file_part_bytes(part)
                    and a2a.get_bytes_from_file_part(part)
                ):
                    file_part = part
                    file_content = file_part.file
                    log.info(
                        "%s Found outbound artifact '%s' with byte content. Saving...",
                        log_identifier,
                        file_content.name,
                    )

                    metadata_to_save = artifact.metadata or {}
                    if artifact.description:
                        metadata_to_save["description"] = artifact.description
                    elif contextual_description:
                        metadata_to_save["description"] = contextual_description
                    else:
                        metadata_to_save["description"] = (
                            f"Artifact created by {agent_name}"
                        )

                    metadata_to_save["proxied_from_artifact_id"] = artifact.artifact_id
                    user_id = task_context.a2a_context.get("user_id", "default_user")
                    session_id = task_context.a2a_context.get("session_id")

                    # Get file content using facade helpers
                    content_bytes = a2a.get_bytes_from_file_part(file_part)
                    filename = a2a.get_filename_from_file_part(file_part)
                    mime_type = a2a.get_mimetype_from_file_part(file_part)

                    save_result = await save_artifact_with_metadata(
                        artifact_service=self.artifact_service,
                        app_name=agent_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=filename,
                        content_bytes=content_bytes,
                        mime_type=mime_type,
                        metadata_dict=metadata_to_save,
                        timestamp=datetime.now(timezone.utc),
                    )

                    if save_result.get("status") in ["success", "partial_success"]:
                        data_version = save_result.get("data_version")
                        saved_uri = format_artifact_uri(
                            app_name=agent_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=filename,
                            version=data_version,
                        )

                        new_file_part = a2a.create_file_part_from_uri(
                            uri=saved_uri,
                            name=filename,
                            mime_type=mime_type,
                            metadata=a2a.get_metadata_from_part(file_part),
                        )
                        from a2a.types import Part

                        artifact.parts[i] = Part(root=new_file_part)

                        saved_artifacts_manifest.append(
                            {"filename": filename, "version": data_version}
                        )
                        log.info(
                            "%s Saved artifact '%s' as version %d. URI: %s",
                            log_identifier,
                            filename,
                            data_version,
                            saved_uri,
                        )
                    else:
                        log.error(
                            "%s Failed to save artifact '%s': %s",
                            log_identifier,
                            filename,
                            save_result.get("message"),
                        )

        return saved_artifacts_manifest

    async def _process_downstream_response(
        self,
        event: Union[
            tuple, Message, Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent
        ],
        task_context: ProxyTaskContext,
        client: Client,
        agent_name: str,
    ) -> None:
        """
        Processes a single event from the downstream agent.

        When using the normal client (non-streaming), events are:
        - A ClientEvent tuple: (Task, Optional[UpdateEvent])
        - A Message object (for direct responses)

        When using transport directly (streaming workaround), events are raw:
        - Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, or Message objects
        """
        log_identifier = (
            f"{self.log_identifier}[ProcessResponse:{task_context.task_id}]"
        )

        # Use facade helpers to determine event type
        event_payload = None

        # Handle raw transport events (from streaming workaround)
        if isinstance(event, (Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent)):
            event_payload = event
            log.debug(
                "%s Received raw transport event: %s",
                log_identifier,
                type(event).__name__,
            )
        elif a2a.is_client_event(event):
            # Unpack the ClientEvent tuple
            task, update_event = a2a.unpack_client_event(event)
            # If there's an update event, that's what we should process
            # The task is just context; the update is the actual event
            if update_event is not None:
                event_payload = update_event
                log.debug(
                    "%s Received ClientEvent with update: %s (task state: %s)",
                    log_identifier,
                    type(update_event).__name__,
                    task.status.state if task.status else "unknown",
                )
            else:
                # No update event means this is the final task state
                event_payload = task
                log.debug(
                    "%s Received ClientEvent with final task state: %s",
                    log_identifier,
                    task.status.state if task.status else "unknown",
                )
        elif a2a.is_message_object(event):
            # Direct Message response
            event_payload = event
            log.debug(
                "%s Received direct Message response",
                log_identifier,
            )
        else:
            log.warning(
                "%s Received unexpected event type: %s",
                log_identifier,
                type(event).__name__,
            )
            return

        if not event_payload:
            log.warning(
                "%s Received an event with no processable payload: %s",
                log_identifier,
                event,
            )
            return

        produced_artifacts = await self._handle_outbound_artifacts(
            event_payload, task_context, agent_name
        )

        # Add produced_artifacts to metadata if any artifacts were processed
        if produced_artifacts and isinstance(
            event_payload, (Task, TaskStatusUpdateEvent)
        ):
            if not event_payload.metadata:
                event_payload.metadata = {}
            event_payload.metadata["produced_artifacts"] = produced_artifacts
            log.info(
                "%s Added manifest of %d produced artifacts to %s metadata.",
                log_identifier,
                len(produced_artifacts),
                type(event_payload).__name__,
            )

        # Add agent_name to metadata for all response types
        if isinstance(
            event_payload, (Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent)
        ):
            if not event_payload.metadata:
                event_payload.metadata = {}
            event_payload.metadata["agent_name"] = agent_name
            log.debug(
                "%s Added agent_name '%s' to %s metadata.",
                log_identifier,
                agent_name,
                type(event_payload).__name__,
            )

        # Convert TextParts to AgentProgressUpdateData for intermediate status updates if configured
        # Only convert non-final status updates; final status updates are used to construct the final Task
        if isinstance(event_payload, TaskStatusUpdateEvent) and not event_payload.final:
            agent_config = self._get_agent_config(agent_name)
            convert_progress = agent_config.get("convert_progress_updates", True) if agent_config else True

            # DEBUG: Log config lookup results
            log.info(
                "%s DEBUG convert_progress_updates: agent_name='%s', agent_config_name='%s', agent_config_keys=%s, convert_progress_value=%s, convert_progress=%s",
                log_identifier,
                agent_name,
                agent_config.get('name') if agent_config else None,
                list(agent_config.keys()) if agent_config else None,
                agent_config.get("convert_progress_updates") if agent_config else None,
                convert_progress,
            )

            if convert_progress and event_payload.status and event_payload.status.message:
                message = event_payload.status.message
                original_parts = a2a.get_parts_from_message(message)

                if original_parts:
                    converted_parts = []
                    text_parts_converted = 0

                    for part in original_parts:
                        if isinstance(part, TextPart) and part.text:
                            # Convert TextPart to DataPart with AgentProgressUpdateData
                            progress_data = AgentProgressUpdateData(
                                type="agent_progress_update",
                                status_text=part.text
                            )
                            data_part = DataPart(
                                kind="data",
                                data=progress_data.model_dump(),
                                metadata=part.metadata
                            )
                            converted_parts.append(data_part)
                            text_parts_converted += 1
                        else:
                            # Keep non-text parts as-is
                            converted_parts.append(part)

                    if text_parts_converted > 0:
                        # Update the message with converted parts
                        event_payload.status.message = a2a.update_message_parts(
                            message, converted_parts
                        )
                        log.debug(
                            "%s Converted %d TextPart(s) to AgentProgressUpdateData in status update",
                            log_identifier,
                            text_parts_converted,
                        )

        # Capture the downstream task ID before we replace it
        # This is needed for forwarding cancellation requests to the downstream agent
        downstream_id = None
        if hasattr(event_payload, "task_id") and event_payload.task_id:
            downstream_id = event_payload.task_id
        elif hasattr(event_payload, "id") and event_payload.id:
            downstream_id = event_payload.id

        # Store the downstream task ID in the context if we haven't already
        if downstream_id and not task_context.downstream_task_id:
            task_context.downstream_task_id = downstream_id
            log.debug(
                "%s Captured downstream task ID: %s (SAM task ID: %s)",
                log_identifier,
                downstream_id,
                task_context.task_id,
            )

        # Replace the downstream task ID with SAM's task ID for upstream responses
        original_task_id = task_context.task_id
        if hasattr(event_payload, "task_id") and event_payload.task_id:
            event_payload.task_id = original_task_id
        elif hasattr(event_payload, "id") and event_payload.id:
            event_payload.id = original_task_id

        if isinstance(event_payload, Task) and event_payload.artifacts:
            text_only_artifacts_content = []
            remaining_artifacts = []
            for artifact in event_payload.artifacts:
                if a2a.is_text_only_artifact(artifact):
                    text_only_artifacts_content.extend(
                        a2a.get_text_content_from_artifact(artifact)
                    )
                else:
                    remaining_artifacts.append(artifact)

            if text_only_artifacts_content:
                log.info(
                    "%s Consolidating %d text-only artifacts into status message.",
                    log_identifier,
                    len(event_payload.artifacts) - len(remaining_artifacts),
                )
                event_payload.artifacts = (
                    remaining_artifacts if remaining_artifacts else None
                )

                consolidated_text = "\n".join(text_only_artifacts_content)
                summary_message_part = TextPart(
                    text=(
                        "The following text-only artifacts were returned and have been consolidated into this message:\n\n---\n\n"
                        f"{consolidated_text}"
                    )
                )

                if not event_payload.status.message:
                    from a2a.types import Part

                    event_payload.status.message = Message(
                        message_id=str(uuid.uuid4()),
                        role="agent",
                        parts=[Part(root=summary_message_part)],
                    )
                else:
                    from a2a.types import Part

                    event_payload.status.message.parts.append(
                        Part(root=summary_message_part)
                    )

        # Convert text-only TaskArtifactUpdateEvents to TaskStatusUpdateEvents
        # Some A2A agents send text content as artifacts, which SAM expects as status updates
        if isinstance(event_payload, TaskArtifactUpdateEvent):
            artifact = event_payload.artifact
            if a2a.is_text_only_artifact(artifact):
                log.info(
                    "%s Converting text-only artifact to status update",
                    log_identifier,
                )
                # Extract text from text-only artifact
                text_content = "\n".join(a2a.get_text_content_from_artifact(artifact))

                # Convert to status update
                text_message = a2a.create_agent_text_message(
                    text=text_content,
                    task_id=event_payload.task_id,
                    context_id=event_payload.context_id,
                )

                status_event = TaskStatusUpdateEvent(
                    task_id=event_payload.task_id,
                    context_id=event_payload.context_id,
                    kind="status-update",
                    status=TaskStatus(state=TaskState.working, message=text_message),
                    final=False,
                    metadata=event_payload.metadata,
                )

                # Replace event_payload with the converted status update
                event_payload = status_event
                log.info(
                    "%s Converted text-only artifact (length: %d bytes) to status update",
                    log_identifier,
                    len(text_content.encode("utf-8")),
                )

        # Determine if this is a terminal event requiring cleanup
        should_cleanup_task = False

        # Route based on event type
        if isinstance(event_payload, Task):
            # Discard initial Task events (non-completed states)
            # The final Task will be constructed from the final status update
            if event_payload.status.state != TaskState.completed:
                log.debug(
                    "%s Discarding Task event with state=%s (not completed). Final Task will be constructed from final status update.",
                    log_identifier,
                    event_payload.status.state,
                )
                # Don't publish, don't cleanup - wait for final status update
                return

            # Forward completed Task to reply topic
            await self._publish_task_response(event_payload, task_context.a2a_context)

            # Completed Task is terminal - cleanup
            should_cleanup_task = True
            log.debug(
                "%s Task in terminal state: %s",
                log_identifier,
                event_payload.status.state,
            )

        elif isinstance(event_payload, TaskStatusUpdateEvent):
            # Forward status update to status topic
            await self._publish_status_update(event_payload, task_context.a2a_context)

            # Check if final event - construct and send Task
            if event_payload.final:
                log.info(
                    "%s Received final status update (final=true). Constructing completed Task.",
                    log_identifier,
                )

                # Construct Task from final status update
                # Copy the status but ensure state is "completed"
                final_task_status = TaskStatus(
                    state=TaskState.completed,
                    message=event_payload.status.message if event_payload.status else None,
                )

                final_task = Task(
                    id=event_payload.task_id,
                    context_id=event_payload.context_id,
                    status=final_task_status,
                    artifacts=None,  # Artifacts come via separate events
                    metadata=event_payload.metadata,
                )

                # Add produced_artifacts metadata if any artifacts were processed
                if produced_artifacts:
                    if not final_task.metadata:
                        final_task.metadata = {}
                    final_task.metadata["produced_artifacts"] = produced_artifacts
                    log.info(
                        "%s Added manifest of %d produced artifacts to final Task metadata.",
                        log_identifier,
                        len(produced_artifacts),
                    )

                # Publish the constructed Task
                await self._publish_task_response(final_task, task_context.a2a_context)

                should_cleanup_task = True
                log.debug(
                    "%s Published final Task constructed from status update",
                    log_identifier,
                )

        elif isinstance(event_payload, TaskArtifactUpdateEvent):
            # Forward artifact update to status topic
            await self._publish_artifact_update(event_payload, task_context.a2a_context)

        elif isinstance(event_payload, Message):
            # Wrap Message in Task for gateway compatibility
            log.info(
                "%s Received direct Message response. Wrapping in completed Task.",
                log_identifier,
            )
            final_task = Task(
                id=task_context.task_id,
                context_id=task_context.a2a_context.get("session_id"),
                status=TaskStatus(state=TaskState.completed, message=event_payload),
            )

            # Add produced_artifacts metadata if any artifacts were processed
            if produced_artifacts:
                final_task.metadata = {"produced_artifacts": produced_artifacts}
                log.info(
                    "%s Added manifest of %d produced artifacts to wrapped Task metadata.",
                    log_identifier,
                    len(produced_artifacts),
                )

            await self._publish_task_response(final_task, task_context.a2a_context)
            should_cleanup_task = True

        else:
            log.warning(
                "%s Received unhandled response payload type: %s",
                log_identifier,
                type(event_payload).__name__,
            )

        # Cleanup task state if terminal event detected
        if should_cleanup_task:
            log.info(
                "%s Terminal event detected for task %s. Cleaning up state.",
                log_identifier,
                task_context.task_id,
            )
            self._cleanup_task_state(task_context.task_id)

    def clear_client_cache(self):
        """
        Clears all cached A2A clients and OAuth tokens.
        This is useful for testing when authentication configuration changes.
        """
        num_clients = len(self._a2a_clients)
        self._a2a_clients.clear()
        log.info(
            "%s Cleared all cached A2A clients (%d clients removed).",
            self.log_identifier,
            num_clients,
        )

    def cleanup(self):
        """Cleans up resources on component shutdown."""
        log.info("%s Cleaning up A2A proxy component resources...", self.log_identifier)

        # Token cache cleanup:
        # - OAuth2TokenCache is automatically garbage collected
        # - No persistent state to clean up
        # - Tokens are lost on component restart (by design)

        async def _async_cleanup():
            # Close all created clients using public API
            for cache_key, client in self._a2a_clients.items():
                agent_name, session_id = cache_key
                log.info(
                    "%s Closing client for agent '%s' session '%s'",
                    self.log_identifier,
                    agent_name,
                    session_id,
                )
                await client.close()
            self._a2a_clients.clear()

        if self._async_loop and self._async_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                _async_cleanup(), self._async_loop
            )
            try:
                future.result(timeout=5)
            except Exception as e:
                log.error("%s Error during async cleanup: %s", self.log_identifier, e)

        super().cleanup()
