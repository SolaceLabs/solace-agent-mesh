"""
Concrete implementation of a proxy for standard A2A-over-HTTPS agents.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

import httpx

from a2a.client import (
    A2ACardResolver,
    A2AClient,
    A2AClientHTTPError,
    AuthInterceptor,
    InMemoryContextCredentialStore,
)
from .oauth_token_cache import OAuth2TokenCache
from a2a.types import (
    A2ARequest,
    AgentCard,
    Artifact as ModernArtifact,
    DataPart,
    FilePart,
    FileWithBytes,
    Message,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

from solace_ai_connector.common.log import log

from datetime import datetime, timezone
from urllib.parse import urlparse

from ....common import a2a
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
        self._a2a_clients: Dict[str, A2AClient] = {}
        self._credential_store: InMemoryContextCredentialStore = InMemoryContextCredentialStore()
        self._auth_interceptor: AuthInterceptor = AuthInterceptor(self._credential_store)
        # OAuth 2.0 token cache for client credentials flow
        # Why use asyncio.Lock: Ensures thread-safe access to the token cache
        # when multiple concurrent requests target the same agent
        self._oauth_token_cache: OAuth2TokenCache = OAuth2TokenCache()
        
        # Validate OAuth 2.0 configuration at startup
        self._validate_oauth_config()

    def _validate_oauth_config(self):
        """
        Validates OAuth 2.0 configuration for all proxied agents at startup.
        
        This method performs fail-fast validation to catch configuration errors
        early, before any requests are processed. It checks:
        - token_url is a valid HTTPS URL
        - client_id is non-empty
        - client_secret is non-empty
        - token_cache_duration_seconds is positive (if specified)
        
        Raises:
            ValueError: If any OAuth 2.0 configuration is invalid.
        """
        log_identifier = f"{self.log_identifier}[ValidateOAuth]"
        
        for agent_config in self.proxied_agents_config:
            agent_name = agent_config.get("name", "unknown")
            auth_config = agent_config.get("authentication")
            
            if not auth_config:
                continue
            
            auth_type = auth_config.get("type")
            
            # Infer type from legacy scheme if not specified
            if not auth_type:
                scheme = auth_config.get("scheme", "bearer")
                if scheme == "bearer":
                    auth_type = "static_bearer"
                elif scheme == "apikey":
                    auth_type = "static_apikey"
            
            # Only validate OAuth 2.0 configurations
            if auth_type != "oauth2_client_credentials":
                continue
            
            log.info(
                "%s Validating OAuth 2.0 configuration for agent '%s'",
                log_identifier,
                agent_name,
            )
            
            # Validate token_url
            token_url = auth_config.get("token_url")
            if not token_url or not isinstance(token_url, str) or not token_url.strip():
                log.error(
                    "%s Agent '%s': 'token_url' is required and must be a non-empty string for OAuth 2.0",
                    log_identifier,
                    agent_name,
                )
                raise ValueError(
                    f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                    "'token_url' is required and must be a non-empty string."
                )
            
            # Validate token_url is HTTPS
            try:
                parsed_url = urlparse(token_url)
                if parsed_url.scheme != "https":
                    log.error(
                        "%s Agent '%s': 'token_url' must use HTTPS for security. Got scheme: '%s'",
                        log_identifier,
                        agent_name,
                        parsed_url.scheme,
                    )
                    raise ValueError(
                        f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                        f"'token_url' must use HTTPS for security. Got: {parsed_url.scheme}://"
                    )
            except Exception as e:
                log.error(
                    "%s Agent '%s': Failed to parse 'token_url': %s",
                    log_identifier,
                    agent_name,
                    e,
                )
                raise ValueError(
                    f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                    f"Failed to parse 'token_url': {e}"
                )
            
            # Validate client_id
            client_id = auth_config.get("client_id")
            if not client_id or not isinstance(client_id, str) or not client_id.strip():
                log.error(
                    "%s Agent '%s': 'client_id' is required and must be a non-empty string for OAuth 2.0",
                    log_identifier,
                    agent_name,
                )
                raise ValueError(
                    f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                    "'client_id' is required and must be a non-empty string."
                )
            
            # Validate client_secret
            client_secret = auth_config.get("client_secret")
            if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
                log.error(
                    "%s Agent '%s': 'client_secret' is required and must be a non-empty string for OAuth 2.0",
                    log_identifier,
                    agent_name,
                )
                raise ValueError(
                    f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                    "'client_secret' is required and must be a non-empty string."
                )
            
            # Validate token_cache_duration_seconds if specified
            cache_duration = auth_config.get("token_cache_duration_seconds")
            if cache_duration is not None:
                if not isinstance(cache_duration, int) or cache_duration <= 0:
                    log.error(
                        "%s Agent '%s': 'token_cache_duration_seconds' must be a positive integer. Got: %s",
                        log_identifier,
                        agent_name,
                        cache_duration,
                    )
                    raise ValueError(
                        f"OAuth 2.0 configuration for agent '{agent_name}' is invalid: "
                        f"'token_cache_duration_seconds' must be a positive integer. Got: {cache_duration}"
                    )
            
            log.info(
                "%s OAuth 2.0 configuration for agent '%s' is valid",
                log_identifier,
                agent_name,
            )

    async def _fetch_agent_card(self, agent_config: Dict[str, Any]) -> Optional[AgentCard]:
        """
        Fetches the AgentCard from a downstream A2A agent via HTTPS.
        """
        agent_name = agent_config.get("name")
        agent_url = agent_config.get("url")
        agent_card_path = agent_config.get("agent_card_path", "/agent/card.json")
        log_identifier = f"{self.log_identifier}[FetchCard:{agent_name}]"

        if not agent_url:
            log.error("%s No URL configured for agent.", log_identifier)
            return None

        try:
            log.info("%s Fetching agent card from %s", log_identifier, agent_url)
            async with httpx.AsyncClient() as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=agent_url)
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

        # Step 1: Initialize retry counter
        # Why only retry once: Prevents infinite loops on persistent auth failures.
        # First 401 may be due to token expiration between cache check and request;
        # second 401 indicates a configuration or authorization issue (not transient).
        max_auth_retries: int = 1
        auth_retry_count: int = 0

        # Step 2: Create while loop for retry logic
        while auth_retry_count <= max_auth_retries:
            try:
                # Get or create A2AClient
                client = await self._get_or_create_a2a_client(agent_name, task_context)
                if not client:
                    raise ValueError(
                        f"Could not create A2A client for agent '{agent_name}'"
                    )

                # Forward the request
                if isinstance(request, SendStreamingMessageRequest):
                    response_generator = client.send_message_streaming(request)
                    async for response in response_generator:
                        await self._process_downstream_response(
                            response, task_context, client, agent_name
                        )
                elif isinstance(request, SendMessageRequest):
                    response = await client.send_message(request)
                    await self._process_downstream_response(
                        response, task_context, client, agent_name
                    )
                else:
                    log.warning(
                        "%s Unhandled request type for forwarding: %s",
                        log_identifier,
                        type(request),
                    )

                # Step 5: Success - break out of retry loop
                break

            except A2AClientHTTPError as e:
                # Step 4: Add specific handling for 401 Unauthorized errors
                if e.status_code == 401 and auth_retry_count < max_auth_retries:
                    log.warning(
                        "%s Received 401 Unauthorized from agent '%s'. Attempting token refresh (retry %d/%d).",
                        log_identifier,
                        agent_name,
                        auth_retry_count + 1,
                        max_auth_retries,
                    )
                    
                    should_retry = await self._handle_auth_error(agent_name, task_context)
                    if should_retry:
                        auth_retry_count += 1
                        continue  # Retry with fresh token
                
                # Not a retryable auth error, or max retries exceeded
                log.exception(
                    "%s HTTP error forwarding request (status %d): %s",
                    log_identifier,
                    e.status_code,
                    e,
                )
                raise
                
            except Exception as e:
                log.exception("%s Error forwarding request: %s", log_identifier, e)
                # The base class exception handler in _handle_a2a_request will catch this
                # and publish an error response.
                raise

    async def _handle_auth_error(
        self, 
        agent_name: str, 
        task_context: ProxyTaskContext
    ) -> bool:
        """
        Handles authentication errors by invalidating cached tokens.
        
        This method is called when a 401 Unauthorized response is received from
        a downstream agent. It checks if the agent uses OAuth 2.0 authentication,
        and if so, invalidates the cached token and removes the cached A2AClient
        to force a fresh token fetch on the next request.
        
        Args:
            agent_name: The name of the agent that returned 401.
            task_context: The current task context.
        
        Returns:
            True if token was invalidated and retry should be attempted.
            False if no retry should be attempted (e.g., static token).
        """
        log_identifier = f"{self.log_identifier}[AuthError:{agent_name}]"
        
        # Step 1: Retrieve agent configuration
        agent_config = next(
            (
                agent
                for agent in self.proxied_agents_config
                if agent.get("name") == agent_name
            ),
            None,
        )
        
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
        
        # Step 3: Invalidate cached token
        log.info(
            "%s Invalidating cached OAuth 2.0 token for agent '%s'.",
            log_identifier,
            agent_name,
        )
        await self._oauth_token_cache.invalidate(agent_name)
        
        # Step 4: Remove cached A2AClient
        # Why remove the A2AClient: The cached client holds a reference to the old token
        # via the AuthInterceptor and CredentialStore. Removing it forces creation of a
        # new client with a fresh token on the next request.
        if agent_name in self._a2a_clients:
            old_client = self._a2a_clients.pop(agent_name)
            
            # Close the httpx client if not already closed
            if old_client._client and not old_client._client.is_closed:
                try:
                    await old_client._client.aclose()
                    log.info(
                        "%s Closed httpx client for agent '%s'.",
                        log_identifier,
                        agent_name,
                    )
                except Exception as e:
                    log.warning(
                        "%s Error closing httpx client for agent '%s': %s",
                        log_identifier,
                        agent_name,
                        e,
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
        
        # SECURITY: Enforce HTTPS for token URL
        parsed_url = urlparse(token_url)
        if parsed_url.scheme != "https":
            log.error(
                "%s OAuth 2.0 token_url must use HTTPS for security. Got scheme: '%s'",
                log_identifier,
                parsed_url.scheme,
            )
            raise ValueError(
                f"{log_identifier} OAuth 2.0 token_url must use HTTPS for security. "
                f"Got: {parsed_url.scheme}://"
            )
        
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
            # Step 5: Create temporary httpx client with 30-second timeout
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 6: Execute POST request
                # SECURITY: client_secret is sent in POST body (not logged or in URL)
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": scope,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                
                # Step 7: Parse response
                token_response = response.json()
                access_token = token_response.get("access_token")
                
                if not access_token:
                    raise ValueError(
                        f"{log_identifier} Token response missing 'access_token' field. "
                        f"Response keys: {list(token_response.keys())}"
                    )
                
                # Step 8: Cache the token
                await self._oauth_token_cache.set(
                    agent_name, access_token, cache_duration
                )
                
                # Step 9: Log success
                log.info(
                    "%s Successfully obtained OAuth 2.0 token (cached for %ds)",
                    log_identifier,
                    cache_duration,
                )
                
                # Step 10: Return access token
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
    ) -> Optional[A2AClient]:
        """
        Gets a cached A2AClient or creates a new one for the given agent.
        
        Supports multiple authentication types:
        - static_bearer: Static bearer token authentication
        - static_apikey: Static API key authentication
        - oauth2_client_credentials: OAuth 2.0 Client Credentials flow with automatic token refresh
        
        For backward compatibility, legacy configurations without a 'type' field
        will have their type inferred from the 'scheme' field.
        """
        if agent_name in self._a2a_clients:
            return self._a2a_clients[agent_name]

        agent_config = next(
            (
                agent
                for agent in self.proxied_agents_config
                if agent.get("name") == agent_name
            ),
            None,
        )
        if not agent_config:
            log.error(f"No configuration found for proxied agent '{agent_name}'")
            return None

        agent_card = self.agent_registry.get_agent(agent_name)
        if not agent_card:
            log.error(f"Agent card not found for '{agent_name}' in registry.")
            return None

        # Resolve timeout
        default_timeout = self.get_config("default_request_timeout_seconds", 300)
        agent_timeout = agent_config.get("request_timeout_seconds", default_timeout)
        log.info("Using timeout of %ss for agent '%s'.", agent_timeout, agent_name)

        # Create a new httpx client with the specific timeout for this agent
        httpx_client_for_agent = httpx.AsyncClient(timeout=agent_timeout)

        # Setup authentication if configured
        auth_config = agent_config.get("authentication")
        if auth_config:
            session_id = task_context.a2a_context.get("session_id", "default_session")
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
                await self._credential_store.set_credentials(session_id, "bearer", token)
            
            elif auth_type == "static_apikey":
                token = auth_config.get("token")
                if not token:
                    raise ValueError(
                        f"Authentication type 'static_apikey' requires 'token' for agent '{agent_name}'"
                    )
                await self._credential_store.set_credentials(session_id, "apikey", token)
            
            elif auth_type == "oauth2_client_credentials":
                # NEW: OAuth 2.0 Client Credentials Flow
                try:
                    access_token = await self._fetch_oauth2_token(agent_name, auth_config)
                    await self._credential_store.set_credentials(session_id, "bearer", access_token)
                except Exception as e:
                    log.error(
                        "%s Failed to obtain OAuth 2.0 token for agent '%s': %s",
                        self.log_identifier,
                        agent_name,
                        e,
                    )
                    raise
            
            else:
                raise ValueError(
                    f"Unsupported authentication type '{auth_type}' for agent '{agent_name}'. "
                    f"Supported types: static_bearer, static_apikey, oauth2_client_credentials."
                )

        client = A2AClient(
            httpx_client=httpx_client_for_agent,
            agent_card=agent_card,
            interceptors=[self._auth_interceptor],
        )
        self._a2a_clients[agent_name] = client
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

        artifacts_to_process: List[ModernArtifact] = []
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
                    part.root.text
                    for part in artifact.parts
                    if isinstance(part.root, TextPart)
                ]
            )

            for i, part_container in enumerate(artifact.parts):
                part = part_container.root
                if (
                    isinstance(part, FilePart)
                    and part.file
                    and isinstance(part.file, FileWithBytes)
                    and part.file.bytes
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
                    user_id = task_context.a2a_context.get("userId", "default_user")
                    session_id = task_context.a2a_context.get("sessionId")

                    save_result = await save_artifact_with_metadata(
                        artifact_service=self.artifact_service,
                        app_name=agent_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=file_content.name,
                        content_bytes=file_content.bytes,
                        mime_type=file_content.mime_type,
                        metadata_dict=metadata_to_save,
                        timestamp=datetime.now(timezone.utc),
                    )

                    if save_result.get("status") in ["success", "partial_success"]:
                        data_version = save_result.get("data_version")
                        saved_uri = format_artifact_uri(
                            app_name=agent_name,
                            user_id=user_id,
                            session_id=session_id,
                            filename=file_content.name,
                            version=data_version,
                        )

                        new_file_part = a2a.create_file_part_from_uri(
                            uri=saved_uri,
                            name=file_content.name,
                            mime_type=file_content.mime_type,
                            metadata=file_part.metadata,
                        )
                        artifact.parts[i] = Part(root=new_file_part)

                        saved_artifacts_manifest.append(
                            {"filename": file_content.name, "version": data_version}
                        )
                        log.info(
                            "%s Saved artifact '%s' as version %d. URI: %s",
                            log_identifier,
                            file_content.name,
                            data_version,
                            saved_uri,
                        )
                    else:
                        log.error(
                            "%s Failed to save artifact '%s': %s",
                            log_identifier,
                            file_content.name,
                            save_result.get("message"),
                        )

        return saved_artifacts_manifest

    async def _process_downstream_response(
        self,
        response: Union[
            SendMessageResponse,
            SendStreamingMessageResponse,
            Task,
            TaskStatusUpdateEvent,
        ],
        task_context: ProxyTaskContext,
        client: A2AClient,
        agent_name: str,
    ) -> None:
        """
        Processes a single response from the downstream agent.
        """
        log_identifier = (
            f"{self.log_identifier}[ProcessResponse:{task_context.task_id}]"
        )

        event_payload = None
        if isinstance(response, (SendMessageResponse, SendStreamingMessageResponse)):
            if hasattr(response.root, "result") and response.root.result:
                event_payload = response.root.result
            elif hasattr(response.root, "error") and response.root.error:
                log.error(
                    "%s Downstream agent returned an error: %s",
                    log_identifier,
                    response.root.error,
                )
                # TODO: Translate and forward the error to the original client.
                return
        else:
            event_payload = response

        if not event_payload:
            log.warning(
                "%s Received a response with no processable payload: %s",
                log_identifier,
                response,
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

        original_task_id = task_context.task_id
        if hasattr(event_payload, "task_id") and event_payload.task_id:
            event_payload.task_id = original_task_id
        elif hasattr(event_payload, "id") and event_payload.id:
            event_payload.id = original_task_id

        if isinstance(event_payload, Task) and event_payload.artifacts:
            text_only_artifacts_content = []
            remaining_artifacts = []
            for artifact in event_payload.artifacts:
                is_text_only = True
                artifact_text_parts = []
                if not artifact.parts:
                    is_text_only = False

                for part in artifact.parts:
                    if isinstance(part.root, TextPart):
                        artifact_text_parts.append(part.root.text)
                    elif isinstance(part.root, (FilePart, DataPart)):
                        is_text_only = False
                        break

                if is_text_only:
                    text_only_artifacts_content.extend(artifact_text_parts)
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
                    event_payload.status.message = Message(
                        message_id=str(uuid.uuid4()),
                        role="agent",
                        parts=[summary_message_part],
                    )
                else:
                    event_payload.status.message.parts.append(summary_message_part)

        if isinstance(event_payload, (Task, TaskStatusUpdateEvent)):
            if isinstance(event_payload, Task):
                await self._publish_final_response(
                    event_payload, task_context.a2a_context
                )
            else:
                await self._publish_status_update(
                    event_payload, task_context.a2a_context
                )
        elif isinstance(event_payload, TaskArtifactUpdateEvent):
            await self._publish_artifact_update(event_payload, task_context.a2a_context)
        elif isinstance(event_payload, Message):
            log.info(
                "%s Received a direct Message response. Wrapping in a completed Task.",
                log_identifier,
            )
            final_task = Task(
                id=task_context.task_id,
                context_id=task_context.a2a_context.get("sessionId"),
                status=TaskStatus(state=TaskState.completed, message=event_payload),
            )

            # Add produced_artifacts metadata to the wrapped Task if any artifacts were processed
            if produced_artifacts:
                final_task.metadata = {"produced_artifacts": produced_artifacts}
                log.info(
                    "%s Added manifest of %d produced artifacts to wrapped Task metadata.",
                    log_identifier,
                    len(produced_artifacts),
                )

            await self._publish_final_response(final_task, task_context.a2a_context)
        else:
            log.warning(
                f"Received unhandled response payload type: {type(event_payload)}"
            )

    def cleanup(self):
        """Cleans up resources on component shutdown."""
        log.info("%s Cleaning up A2A proxy component resources...", self.log_identifier)

        # Token cache cleanup:
        # - OAuth2TokenCache is automatically garbage collected
        # - No persistent state to clean up
        # - Tokens are lost on component restart (by design)

        async def _async_cleanup():
            # Close all created httpx clients
            for agent_name, client in self._a2a_clients.items():
                if client._client and not client._client.is_closed:
                    log.info(
                        "%s Closing httpx client for agent '%s'",
                        self.log_identifier,
                        agent_name,
                    )
                    await client._client.aclose()
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
