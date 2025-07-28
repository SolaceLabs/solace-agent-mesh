"""
Concrete implementation of a proxy for standard A2A-over-HTTPS agents.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

from a2a.client import (
    A2ACardResolver,
    A2AClient,
    A2AClientHTTPError,
    AuthInterceptor,
    InMemoryContextCredentialStore,
)
from solace_ai_connector.common.log import log

from a2a.types import (
    A2ARequest,
    AgentCard,
    FilePart,
    SendMessageRequest,
    SendMessageResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
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
        self._credential_store = InMemoryContextCredentialStore()
        self._auth_interceptor = AuthInterceptor(self._credential_store)

    async def _fetch_agent_card(self, agent_config: dict) -> Optional[AgentCard]:
        """
        Fetches the AgentCard from a downstream A2A agent via HTTPS.
        """
        agent_name = agent_config.get("name")
        agent_url = agent_config.get("url")
        log_identifier = f"{self.log_identifier}[FetchCard:{agent_name}]"

        if not agent_url:
            log.error("%s No URL configured for agent.", log_identifier)
            return None

        try:
            log.info("%s Fetching agent card from %s", log_identifier, agent_url)
            resolver = A2ACardResolver(
                httpx_client=self._httpx_client, base_url=agent_url
            )
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
        self, task_context: "ProxyTaskContext", request: A2ARequest, agent_name: str
    ):
        """
        Forwards an A2A request to a downstream A2A-over-HTTPS agent.
        """
        log_identifier = f"{self.log_identifier}[ForwardRequest:{task_context.task_id}:{agent_name}]"

        try:
            # Get or create A2AClient
            client = await self._get_or_create_a2a_client(agent_name, task_context)
            if not client:
                raise ValueError(f"Could not create A2A client for agent '{agent_name}'")

            # Handle inbound artifacts
            await self._handle_inbound_artifacts(request)

            # Forward the request
            if isinstance(request, SendStreamingMessageRequest):
                response_generator = client.send_message_streaming(
                    request, context=task_context.a2a_context
                )
                async for response in response_generator:
                    await self._process_downstream_response(
                        response, task_context, client
                    )
            elif isinstance(request, SendMessageRequest):
                response = await client.send_message(
                    request, context=task_context.a2a_context
                )
                await self._process_downstream_response(response, task_context, client)
            else:
                log.warning("%s Unhandled request type for forwarding: %s", log_identifier, type(request))

        except Exception as e:
            log.exception("%s Error forwarding request: %s", log_identifier, e)
            # The base class exception handler in _handle_a2a_request will catch this
            # and publish an error response.
            raise

    async def _get_or_create_a2a_client(self, agent_name: str, task_context: "ProxyTaskContext") -> Optional[A2AClient]:
        """
        Gets a cached A2AClient or creates a new one for the given agent.
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

        # Setup authentication if configured
        auth_config = agent_config.get("authentication")
        if auth_config:
            session_id = task_context.a2a_context.get("session_id", "default_session")
            await self._credential_store.set_credentials(
                session_id, auth_config["scheme"], auth_config["token"]
            )

        client = A2AClient(
            httpx_client=self._httpx_client,
            agent_card=agent_card,
            interceptors=[self._auth_interceptor],
        )
        self._a2a_clients[agent_name] = client
        return client

    async def _handle_inbound_artifacts(self, request: A2ARequest):
        """
        Checks for artifact references in the request and loads their content.
        """
        if not hasattr(request.params, "message") or not request.params.message.parts:
            return

        for part in request.params.message.parts:
            if isinstance(part, FilePart) and part.file and part.file.uri:
                if part.file.uri.startswith("artifact://"):
                    # This is a simplified placeholder. A real implementation
                    # would need to parse the URI and use the artifact service.
                    log.info(f"Loading artifact from URI: {part.file.uri}")
                    # loaded_content = await self.artifact_service.load(...)
                    # part.file.bytes = loaded_content
                    # part.file.uri = None
                    pass  # Placeholder for artifact loading logic

    async def _process_downstream_response(
        self,
        response: Union[
            SendMessageResponse, SendStreamingMessageResponse, Task, TaskStatusUpdateEvent
        ],
        task_context: "ProxyTaskContext",
        client: A2AClient,
    ):
        """
        Processes a single response from the downstream agent.
        """
        log_identifier = f"{self.log_identifier}[ProcessResponse:{task_context.task_id}]"

        # Handle outbound artifacts
        await self._handle_outbound_artifacts(response, task_context, client)

        # Publish response back to Solace
        if isinstance(response, (Task, TaskStatusUpdateEvent)):
            if isinstance(response, Task):
                # This is a final response
                await self._publish_final_response(response, task_context.a2a_context)
            else:
                # This is a status update
                await self._publish_status_update(response, task_context.a2a_context)
        elif isinstance(response, TaskArtifactUpdateEvent):
            # This is already handled by _handle_outbound_artifacts, but we could
            # forward the event if needed. For now, we assume saving is enough.
            await self._publish_artifact_update(response, task_context.a2a_context)
        else:
            log.warning(f"Received unhandled response type: {type(response)}")

    async def _handle_outbound_artifacts(
        self,
        response: Any,
        task_context: "ProxyTaskContext",
        client: A2AClient,
    ):
        """
        Checks for artifacts in the response, saves them, and rewrites the response.
        """
        parts_to_check = []
        if isinstance(response, Task) and response.status and response.status.message:
            parts_to_check = response.status.message.parts
        elif isinstance(response, TaskStatusUpdateEvent) and response.status and response.status.message:
            parts_to_check = response.status.message.parts
        elif isinstance(response, TaskArtifactUpdateEvent):
            parts_to_check = response.artifact.parts

        for part in parts_to_check:
            if isinstance(part, FilePart) and part.file and part.file.bytes:
                # Save artifact and rewrite part
                # This is a simplified placeholder.
                log.info(f"Saving outbound artifact: {part.file.name}")
                # saved_uri = await self.artifact_service.save(...)
                # part.file.uri = saved_uri
                # part.file.bytes = None
                pass  # Placeholder for artifact saving logic

    async def cleanup(self):
        """Cleans up resources on component shutdown."""
        # httpx_client is now closed by the base class
        await super().cleanup()
