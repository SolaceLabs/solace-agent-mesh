"""
Concrete implementation of a proxy for standard A2A-over-HTTPS agents.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, TYPE_CHECKING, Union

import httpx

from a2a.client import (
    A2ACardResolver,
    A2AClient,
    A2AClientHTTPError,
    AuthInterceptor,
    InMemoryContextCredentialStore,
)
from solace_ai_connector.common.log import log

from datetime import datetime, timezone

from a2a.types import (
    A2ARequest,
    AgentCard,
    Artifact as ModernArtifact,
    FilePart,
    Message,
    SendMessageRequest,
    SendMessageResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
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
            async with httpx.AsyncClient() as client:
                resolver = A2ACardResolver(
                    httpx_client=client, base_url=agent_url
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
        log_identifier = (
            f"{self.log_identifier}[ForwardRequest:{task_context.task_id}:{agent_name}]"
        )

        try:
            # Get or create A2AClient
            client = await self._get_or_create_a2a_client(agent_name, task_context)
            if not client:
                raise ValueError(
                    f"Could not create A2A client for agent '{agent_name}'"
                )

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
                log.warning(
                    "%s Unhandled request type for forwarding: %s",
                    log_identifier,
                    type(request),
                )

        except Exception as e:
            log.exception("%s Error forwarding request: %s", log_identifier, e)
            # The base class exception handler in _handle_a2a_request will catch this
            # and publish an error response.
            raise

    async def _get_or_create_a2a_client(
        self, agent_name: str, task_context: "ProxyTaskContext"
    ) -> Optional[A2AClient]:
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

        # Resolve timeout
        default_timeout = self.get_config("default_request_timeout_seconds", 300)
        agent_timeout = agent_config.get("request_timeout_seconds", default_timeout)
        log.info(
            f"Using timeout of {agent_timeout}s for agent '{agent_name}'."
        )

        # Create a new httpx client with the specific timeout for this agent
        httpx_client_for_agent = httpx.AsyncClient(timeout=agent_timeout)

        # Setup authentication if configured
        auth_config = agent_config.get("authentication")
        if auth_config:
            session_id = task_context.a2a_context.get("session_id", "default_session")
            await self._credential_store.set_credentials(
                session_id, auth_config["scheme"], auth_config["token"]
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
        task_context: "ProxyTaskContext",
    ) -> List[Dict[str, Any]]:
        """
        Finds artifacts with byte content, saves them to the proxy's artifact store,
        and mutates the response object to replace bytes with a URI.
        It also uses TextParts within an artifact as a description for the saved file.

        Returns:
            A list of dictionaries, each representing a saved artifact with its filename and version.
        """
        from ....agent.utils.artifact_helpers import save_artifact_with_metadata
        from a2a.types import TextPart

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

            for part in artifact.parts:
                if (
                    isinstance(part.root, FilePart)
                    and part.root.file
                    and part.root.file.bytes
                ):
                    file_part = part.root
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

                    metadata_to_save["proxied_from_artifact_id"] = artifact.artifact_id
                    user_id = task_context.a2a_context.get("userId", "default_user")
                    session_id = task_context.a2a_context.get("sessionId")

                    save_result = await save_artifact_with_metadata(
                        artifact_service=self.artifact_service,
                        app_name=self.name,
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
                        saved_uri = f"artifact://{self.name}/{user_id}/{session_id}/{file_content.name}?version={data_version}"

                        file_content.uri = saved_uri
                        file_content.bytes = None

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
        task_context: "ProxyTaskContext",
        client: A2AClient,
    ):
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
            event_payload, task_context
        )

        original_task_id = task_context.task_id
        if hasattr(event_payload, "task_id") and event_payload.task_id:
            event_payload.task_id = original_task_id
        elif hasattr(event_payload, "id") and event_payload.id:
            event_payload.id = original_task_id

        if isinstance(event_payload, (Task, TaskStatusUpdateEvent)):
            if isinstance(event_payload, Task):
                await self._publish_final_response(
                    event_payload, task_context.a2a_context, produced_artifacts
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
            await self._publish_final_response(
                final_task, task_context.a2a_context, produced_artifacts
            )
        else:
            log.warning(
                f"Received unhandled response payload type: {type(event_payload)}"
            )

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
        elif (
            isinstance(response, TaskStatusUpdateEvent)
            and response.status
            and response.status.message
        ):
            parts_to_check = response.status.message.parts
        elif isinstance(response, TaskArtifactUpdateEvent):
            parts_to_check = response.artifact.parts
        elif isinstance(response, Message):
            parts_to_check = response.parts

        for part in parts_to_check:
            if isinstance(part, FilePart) and part.file and part.file.bytes:
                # Save artifact and rewrite part
                # This is a simplified placeholder.
                log.info(f"Saving outbound artifact: {part.file.name}")
                # saved_uri = await self.artifact_service.save(...)
                # part.file.uri = saved_uri
                # part.file.bytes = None
                pass  # Placeholder for artifact saving logic

    def cleanup(self):
        """Cleans up resources on component shutdown."""
        log.info("%s Cleaning up A2A proxy component resources...", self.log_identifier)

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
            future = asyncio.run_coroutine_threadsafe(_async_cleanup(), self._async_loop)
            try:
                future.result(timeout=5)
            except Exception as e:
                log.error("%s Error during async cleanup: %s", self.log_identifier, e)

        super().cleanup()
