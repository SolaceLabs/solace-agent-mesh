"""
MCP Gateway Adapter for the Generic Gateway Framework.

This adapter exposes SAM agents as MCP (Model Context Protocol) tools using FastMCP.
Agents are dynamically discovered from the agent registry and exposed as callable tools.
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from a2a.types import AgentCard, AgentSkill
from fastmcp import FastMCP, Context as McpContext
from mcp.types import (
    AudioContent,
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
    TextResourceContents,
)
from pydantic import BaseModel, Field

from ...common.utils.mime_helpers import is_text_based_file
from ..adapter import oauth_utils
from ..adapter.base import GatewayAdapter
from ..adapter.types import (
    AuthClaims,
    GatewayContext,
    ResponseContext,
    SamDataPart,
    SamError,
    SamFilePart,
    SamTask,
    SamTextPart,
    SamUpdate,
)
from .oauth_handler import OAuthFlowHandler
from .utils import sanitize_tool_name, format_agent_skill_description

log = logging.getLogger(__name__)

# Sentinel value to signal stream completion
STREAM_COMPLETE = object()


class McpAdapterConfig(BaseModel):
    """Configuration model for the McpAdapter."""

    mcp_server_name: str = Field(
        default="SAM MCP Gateway", description="Name of the MCP server"
    )
    mcp_server_description: str = Field(
        default="Model Context Protocol gateway to Solace Agent Mesh",
        description="Description of the MCP server",
    )
    transport: str = Field(
        default="http", description="Transport type: 'http' or 'stdio'"
    )
    port: int = Field(default=8000, description="Port for HTTP transport")
    host: str = Field(default="0.0.0.0", description="Host for HTTP transport")
    default_user_identity: str = Field(
        default="mcp_user", description="Default user identity for authentication"
    )
    stream_responses: bool = Field(
        default=True, description="Whether to stream responses back to MCP client"
    )
    task_timeout_seconds: int = Field(
        default=300,
        description="Timeout in seconds for waiting for agent task completion (default 5 minutes)",
    )

    # OAuth Authentication Configuration
    enable_auth: bool = Field(
        default=False,
        description="Enable OAuth authentication. Requires HTTP transport and external OAuth2 service.",
    )
    external_auth_service_url: str = Field(
        default="http://localhost:8050",
        description="URL of SAM's OAuth2 service (enterprise feature)",
    )
    external_auth_provider: str = Field(
        default="azure",
        description="OAuth provider configured in OAuth2 service (e.g., 'azure', 'google')",
    )
    dev_mode: bool = Field(
        default=False,
        description="Development mode - bypass auth and use default_user_identity (WARNING: insecure, dev only)",
    )

    # File handling configuration
    inline_image_max_bytes: int = Field(
        default=5_242_880,  # 5MB
        description="Maximum size in bytes for inline image returns (larger images become resource links)",
    )
    inline_audio_max_bytes: int = Field(
        default=10_485_760,  # 10MB
        description="Maximum size in bytes for inline audio returns (larger audio becomes resource links)",
    )
    inline_text_max_bytes: int = Field(
        default=1_048_576,  # 1MB
        description="Maximum size in bytes for inline text file returns (larger text files become resource links)",
    )
    inline_binary_max_bytes: int = Field(
        default=524_288,  # 512KB
        description="Maximum size in bytes for inline binary returns (larger binaries become resource links)",
    )

    # Resource configuration
    resource_uri_prefix: str = Field(
        default="artifact",
        description="URI prefix for artifact resources (e.g., 'artifact://session_id/filename')",
    )
    enable_artifact_resources: bool = Field(
        default=True,
        description="Whether to expose artifacts as MCP resources",
    )


class McpAdapter(GatewayAdapter):
    """
    MCP Gateway Adapter that exposes SAM agents as MCP tools.

    This adapter:
    - Discovers agents from the agent registry
    - Creates MCP tools dynamically based on agent skills
    - Handles streaming responses from SAM agents
    - Maps MCP tool calls to SAM tasks
    """

    ConfigModel = McpAdapterConfig

    def __init__(self):
        self.context: Optional[GatewayContext] = None
        self.mcp_server: Optional[FastMCP] = None
        self.oauth_handler: Optional[OAuthFlowHandler] = None
        self.tool_to_agent_map: Dict[str, tuple[str, str]] = (
            {}
        )  # tool_name -> (agent_name, skill_id)
        self.active_tasks: Dict[str, str] = {}  # task_id -> tool_name (for correlation)
        self.task_buffers: Dict[str, List[str]] = {}  # task_id -> list of text chunks
        self.task_futures: Dict[str, asyncio.Future] = (
            {}
        )  # task_id -> Future for completion
        self.task_errors: Dict[str, SamError] = {}  # task_id -> error if failed
        self.task_queues: Dict[str, asyncio.Queue] = (
            {}
        )  # task_id -> Queue for streaming chunks
        self.agent_to_tools: Dict[str, List[str]] = (
            {}
        )  # agent_name -> list of tool names

        # Resource management for artifact access
        # Track which artifacts exist per session for resource listing
        self.session_artifacts: Dict[str, Dict[str, Dict[str, Any]]] = (
            {}
        )  # session_id -> {filename -> metadata}

    async def init(self, context: GatewayContext) -> None:
        """Initialize the MCP server and register tools from discovered agents."""
        self.context = context
        config: McpAdapterConfig = self.context.adapter_config

        log.info("Initializing MCP Gateway Adapter...")

        # Validate OAuth configuration
        if config.enable_auth:
            if config.transport == "stdio":
                raise ValueError(
                    "OAuth authentication requires HTTP transport. "
                    "Set transport='http' in configuration when enable_auth=True."
                )
            if config.dev_mode:
                log.warning(
                    "⚠️  DEV MODE ENABLED: Authentication is bypassed! "
                    "This is insecure and should NEVER be used in production."
                )
            log.info(
                "OAuth authentication enabled: service=%s, provider=%s",
                config.external_auth_service_url,
                config.external_auth_provider,
            )
        elif config.dev_mode:
            log.warning(
                "⚠️  DEV MODE ENABLED with auth disabled: Using default_user_identity=%s",
                config.default_user_identity,
            )
        else:
            log.info(
                "OAuth authentication disabled, using default_user_identity=%s",
                config.default_user_identity,
            )

        # Initialize OAuth handler if authentication is enabled
        if config.enable_auth:
            callback_base_url = f"http://{config.host}:{config.port}"
            self.oauth_handler = OAuthFlowHandler(
                oauth_service_url=config.external_auth_service_url,
                oauth_provider=config.external_auth_provider,
                callback_base_url=callback_base_url,
                callback_path="/oauth/callback",
            )
            log.info("OAuth handler initialized")

        # Create FastMCP server
        self.mcp_server = FastMCP(name=config.mcp_server_name)

        # Register artifact resource template if enabled
        if config.enable_artifact_resources:
            self._register_artifact_resource_template()

        # Register OAuth endpoints if authentication is enabled
        if config.enable_auth and self.oauth_handler:
            self._register_oauth_endpoints()

        # Register tools dynamically from agent registry
        await self._register_tools_from_agents()

        # Start the MCP server in the background
        asyncio.create_task(self._run_mcp_server())

        log.info(
            "MCP Gateway Adapter initialized with %d tools", len(self.tool_to_agent_map)
        )

    async def _register_tools_from_agents(self):
        """Query agent registry and register MCP tools for each agent's skills."""
        try:
            agents: List[AgentCard] = self.context.list_agents()
            log.info("Discovered %d agents from registry", len(agents))

            for agent_card in agents:
                if not agent_card.skills:
                    log.debug("Agent %s has no skills, skipping", agent_card.name)
                    continue

                for skill in agent_card.skills:
                    self._register_tool_for_skill(agent_card, skill)

        except Exception as e:
            log.exception("Error registering tools from agents: %s", e)

    def _register_artifact_resource_template(self):
        """
        Register a resource template for artifacts.

        This allows MCP clients to access artifacts via URIs like:
        artifact://{session_id}/{filename}

        The template handler will dynamically load artifacts from the artifact service.
        """
        config: McpAdapterConfig = self.context.adapter_config

        @self.mcp_server.resource(
            uri=f"{config.resource_uri_prefix}://{{session_id}}/{{filename}}",
            name="artifact_template",
            description="Access artifacts created during tool execution",
        )
        async def artifact_resource_handler(session_id: str, filename: str):
            """
            Handles MCP resource read requests for artifacts.

            Args:
                session_id: The session ID (e.g., "mcp-client-abc123")
                filename: The artifact filename

            Returns:
                TextResourceContents or BlobResourceContents
            """
            return await self._handle_artifact_resource_read(session_id, filename)

        log.info(
            f"Registered artifact resource template: {config.resource_uri_prefix}://{{session_id}}/{{filename}}"
        )

    def _register_oauth_endpoints(self):
        """
        Register OAuth endpoints with the FastMCP server.

        Note: FastMCP HTTP server currently doesn't expose a way to add custom HTTP endpoints.
        This is a known limitation. The OAuth handler is initialized and ready, but OAuth
        endpoints would need to be exposed via a separate HTTP server or by modifying FastMCP.

        For now, this serves as documentation and preparation for when FastMCP supports
        custom HTTP endpoints, or when we implement a separate HTTP server for OAuth.

        OAuth endpoints that should be exposed:
        - GET /oauth/authorize - Initiates OAuth flow
        - GET /oauth/callback - Handles OAuth callback
        - POST /oauth/token - Token refresh endpoint
        - GET /.well-known/oauth-authorization-server - OAuth metadata
        """
        if not self.oauth_handler:
            return

        log.warning(
            "OAuth handler initialized but endpoints not exposed. "
            "FastMCP HTTP server does not currently support custom HTTP endpoints. "
            "OAuth flow must be handled externally or via a separate HTTP server. "
            "See documentation for workarounds."
        )

        # TODO: Once FastMCP supports custom HTTP endpoints, register them here:
        # - self.mcp_server.add_http_endpoint("GET", "/oauth/authorize", self._handle_oauth_authorize)
        # - self.mcp_server.add_http_endpoint("GET", "/oauth/callback", self._handle_oauth_callback)
        # - self.mcp_server.add_http_endpoint("POST", "/oauth/token", self._handle_oauth_token)
        # - self.mcp_server.add_http_endpoint("GET", "/oauth/metadata", self._handle_oauth_metadata)

    def _register_tool_for_skill(self, agent_card: AgentCard, skill: AgentSkill):
        """
        Register a single MCP tool for an agent skill.

        If the tool already exists, it will be removed and re-registered
        with the updated information.
        """
        # Create tool name: agent_skill format
        tool_name = sanitize_tool_name(f"{agent_card.name}_{skill.name}")

        # Check if tool already exists (handle re-registration)
        if tool_name in self.tool_to_agent_map:
            log.debug(
                "Tool %s already registered, removing old version before re-registering...",
                tool_name,
            )
            try:
                self.mcp_server.remove_tool(tool_name)
            except Exception as e:
                # If removal fails, log but continue with registration
                log.warning(f"Failed to remove existing tool {tool_name}: {e}")

        # Store mapping
        self.tool_to_agent_map[tool_name] = (agent_card.name, skill.id)

        # Create tool description from skill
        tool_description = format_agent_skill_description(skill)

        # Register the tool with FastMCP
        # We create a closure to capture the agent and skill info
        async def tool_handler(message: str, ctx: McpContext):
            """
            Handler for MCP tool invocation.

            Args:
                message: The input message text
                ctx: FastMCP Context for streaming updates
            """
            return await self._handle_tool_call(
                tool_name=tool_name, message=message, mcp_context=ctx
            )

        # Set function metadata for FastMCP introspection
        tool_handler.__name__ = tool_name
        tool_handler.__doc__ = tool_description

        # Register with decorator pattern
        # This automatically sends tool_list_changed notification to MCP clients
        self.mcp_server.tool(tool_handler)

        log.debug(
            "Registered MCP tool: %s -> %s/%s", tool_name, agent_card.name, skill.id
        )

    async def _handle_tool_call(
        self, tool_name: str, message: str, mcp_context: McpContext
    ) -> str:
        """
        Handle an MCP tool invocation by routing to the appropriate SAM agent.

        This method:
        1. Creates a Future and Queue for the task
        2. Starts a consumer coroutine to stream updates to MCP client
        3. Submits the task to SAM
        4. Waits for the task to complete (with timeout)
        5. Returns the final assembled response

        Args:
            tool_name: The name of the tool being called
            message: The message text from the MCP client
            mcp_context: FastMCP context for streaming updates (stays in this scope)

        Returns:
            Final response text from the agent
        """
        if tool_name not in self.tool_to_agent_map:
            error_msg = f"Tool {tool_name} not found in mapping"
            log.error(error_msg)
            return f"Error: {error_msg}"

        agent_name, skill_id = self.tool_to_agent_map[tool_name]
        config: McpAdapterConfig = self.context.adapter_config

        # Create Future and Queue for this task
        task_future = asyncio.Future()
        stream_queue = asyncio.Queue()

        try:
            # Use FastMCP's client_id for connection-based session
            # Note: client_id might be None for some transports, use fallback
            try:
                client_id = mcp_context.client_id
            except Exception as e:
                log.warning(f"Failed to access mcp_context.client_id: {e}")
                client_id = None

            if not client_id:
                # Fallback: try session_id first, then generate unique ID
                try:
                    client_id = mcp_context.session_id
                except Exception as e:
                    log.warning(f"Failed to access mcp_context.session_id: {e}")
                    client_id = None

                if not client_id:
                    # Last resort: generate a unique ID
                    import uuid

                    client_id = f"generated-{uuid.uuid4().hex[:12]}"

                log.warning(
                    f"mcp_context.client_id not available, using fallback: {client_id}"
                )

            # Extract access token from MCP context for OAuth authentication
            # The token can be provided by the MCP client in various ways
            access_token = None
            if config.enable_auth and not config.dev_mode:
                try:
                    # Try to get token from mcp_context metadata/headers
                    # FastMCP may provide this in different ways depending on transport
                    if hasattr(mcp_context, "request_context"):
                        # HTTP transport might have headers
                        request_ctx = mcp_context.request_context
                        if isinstance(request_ctx, dict):
                            access_token = oauth_utils.extract_bearer_token_from_dict(
                                request_ctx
                            )

                    # Try metadata attribute
                    if not access_token and hasattr(mcp_context, "metadata"):
                        metadata = mcp_context.metadata
                        if isinstance(metadata, dict):
                            access_token = oauth_utils.extract_bearer_token_from_dict(
                                metadata
                            )

                    if not access_token:
                        log.warning(
                            "OAuth enabled but no access token found in MCP context for tool call"
                        )
                except Exception as e:
                    log.warning(f"Error extracting access token from MCP context: {e}")

            # Create external input dict with client_id and optional token
            external_input = {
                "tool_name": tool_name,
                "agent_name": agent_name,
                "skill_id": skill_id,
                "message": message,
                "mcp_client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add token to external_input if OAuth is enabled
            if access_token:
                external_input["access_token"] = access_token
                log.debug("Added access token to external_input for authentication")

            # Submit to SAM via the generic gateway with endpoint_context
            task_id = await self.context.handle_external_input(
                external_input, endpoint_context={"mcp_client_id": client_id}
            )

            # Register Future, Queue, and buffers for this task
            self.task_futures[task_id] = task_future
            self.task_queues[task_id] = stream_queue
            self.task_buffers[task_id] = []
            self.active_tasks[task_id] = tool_name

            # Report submission to MCP client
            await mcp_context.info(f"Task {task_id} submitted to agent {agent_name}")

            # Start consumer coroutine to stream updates from queue to MCP client
            async def stream_consumer():
                """
                Consume chunks from the queue and stream them to the MCP client.
                Accumulates non-text content objects for final return.
                This runs in the MCP request context, so mcp_context is valid here.
                """
                content_objects = []

                if not config.stream_responses:
                    log.debug(f"Streaming disabled for task {task_id}")
                    return content_objects

                try:
                    while True:
                        # Wait for next chunk from the queue
                        chunk = await stream_queue.get()

                        # Check for sentinel (completion signal)
                        if chunk is STREAM_COMPLETE:
                            log.debug(
                                f"Stream consumer for task {task_id} received completion signal"
                            )
                            break

                        # Handle different chunk types
                        if isinstance(chunk, str):
                            # Text chunk - stream as info
                            try:
                                await mcp_context.info(chunk)
                            except Exception as e:
                                log.warning(
                                    f"Failed to stream text chunk to MCP client: {e}"
                                )
                        else:
                            # Content object (ImageContent, AudioContent, ResourceLink, EmbeddedResource)
                            # Don't stream these, accumulate for final return
                            content_objects.append(chunk)
                            # Optionally notify about the content
                            try:
                                content_type = getattr(chunk, "type", "content")
                                if content_type == "image":
                                    await mcp_context.info(f"📷 Image attached")
                                elif content_type == "audio":
                                    await mcp_context.info(f"🎵 Audio attached")
                                elif content_type == "resource_link":
                                    await mcp_context.info(
                                        f"📎 File available: {getattr(chunk, 'name', 'file')}"
                                    )
                                elif content_type == "resource":
                                    await mcp_context.info(f"📄 Resource embedded")
                            except Exception as e:
                                log.warning(
                                    f"Failed to notify about content object: {e}"
                                )

                        stream_queue.task_done()

                except asyncio.CancelledError:
                    log.debug(f"Stream consumer for task {task_id} was cancelled")
                except Exception as e:
                    log.error(
                        f"Error in stream consumer for task {task_id}: {e}",
                        exc_info=True,
                    )

                return content_objects

            # Start consumer in background
            consumer_task = asyncio.create_task(stream_consumer())

            # Wait for the task to complete (with timeout)
            try:
                result_text = await asyncio.wait_for(
                    task_future, timeout=config.task_timeout_seconds
                )

                # Wait for consumer to finish and get accumulated content objects
                try:
                    content_objects = await asyncio.wait_for(consumer_task, timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning(f"Consumer for task {task_id} did not finish in time")
                    consumer_task.cancel()
                    content_objects = []

                # Build final response
                if content_objects:
                    # We have mixed content - return as list
                    final_content = []

                    # Add text first if present
                    if result_text and result_text.strip():
                        final_content.append(TextContent(type="text", text=result_text))

                    # Add all content objects (images, audio, resources, etc.)
                    final_content.extend(content_objects)

                    log.info(
                        f"Task {task_id} completed with {len(final_content)} content parts"
                    )
                    return final_content
                else:
                    # Text-only response
                    log.info(
                        f"Task {task_id} completed successfully, returned {len(result_text)} chars"
                    )
                    return result_text

            except asyncio.TimeoutError:
                error_msg = f"Task {task_id} timed out after {config.task_timeout_seconds} seconds"
                log.error(error_msg)
                await mcp_context.error(error_msg)

                # Signal consumer to stop
                try:
                    await stream_queue.put(STREAM_COMPLETE)
                except:
                    pass
                consumer_task.cancel()

                self._cleanup_task(task_id)
                return f"Error: {error_msg}"

        except Exception as e:
            error_msg = f"Error invoking agent {agent_name}: {str(e)}"
            log.exception(error_msg)
            await mcp_context.error(error_msg)
            return f"Error: {error_msg}"

        finally:
            # Cleanup queue
            if task_id in self.task_queues:
                del self.task_queues[task_id]

    async def _run_mcp_server(self):
        """Start the FastMCP server with configured transport."""
        config: McpAdapterConfig = self.context.adapter_config

        try:
            if config.transport == "http":
                log.info(
                    "Starting MCP server on HTTP transport at %s:%d",
                    config.host,
                    config.port,
                )
                # Run in a thread pool to avoid blocking
                await asyncio.to_thread(
                    self.mcp_server.run,
                    transport="http",
                    host=config.host,
                    port=config.port,
                )
            elif config.transport == "stdio":
                log.info("Starting MCP server on stdio transport")
                # Run in a thread pool to avoid blocking
                await asyncio.to_thread(self.mcp_server.run, transport="stdio")
            else:
                log.error("Unknown transport: %s", config.transport)
        except Exception as e:
            log.exception("Error running MCP server: %s", e)

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        log.info("Cleaning up MCP Gateway Adapter...")
        # FastMCP handles cleanup internally
        self.active_tasks.clear()
        self.task_buffers.clear()
        self.task_futures.clear()
        self.task_errors.clear()
        self.task_queues.clear()
        self.session_artifacts.clear()
        self.agent_to_tools.clear()

    def _cleanup_task(self, task_id: str) -> None:
        """
        Clean up all state for a completed or failed task.

        Args:
            task_id: The ID of the task to clean up
        """
        if task_id in self.task_futures:
            del self.task_futures[task_id]
        if task_id in self.task_buffers:
            del self.task_buffers[task_id]
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        if task_id in self.task_errors:
            del self.task_errors[task_id]
        if task_id in self.task_queues:
            del self.task_queues[task_id]

    # --- File and Resource Handling Helper Methods ---

    def _determine_content_type(
        self, file_part: SamFilePart, config: McpAdapterConfig
    ) -> Literal["image", "audio", "text_embedded", "blob_embedded", "resource_link"]:
        """
        Determines how to return a file based on type and size.

        Returns:
            - "image": Return as ImageContent
            - "audio": Return as AudioContent
            - "text_embedded": Return as EmbeddedResource with TextResourceContents
            - "blob_embedded": Return as EmbeddedResource with BlobResourceContents
            - "resource_link": Return as ResourceLink (register as MCP resource)
        """
        mime_type = file_part.mime_type or "application/octet-stream"
        size = len(file_part.content_bytes) if file_part.content_bytes else 0

        # Image handling
        if mime_type.startswith("image/"):
            if size <= config.inline_image_max_bytes:
                return "image"
            else:
                return "resource_link"

        # Audio handling
        if mime_type.startswith("audio/"):
            if size <= config.inline_audio_max_bytes:
                return "audio"
            else:
                return "resource_link"

        # Text file handling - use existing helper!
        if is_text_based_file(mime_type, file_part.content_bytes):
            if size <= config.inline_text_max_bytes:
                return "text_embedded"
            else:
                return "resource_link"

        # Other binary
        if size <= config.inline_binary_max_bytes:
            return "blob_embedded"
        else:
            return "resource_link"

    async def _load_file_content_if_needed(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> bytes:
        """Loads file content from artifact service if not already present."""
        if file_part.content_bytes:
            return file_part.content_bytes

        # Load from artifact service
        content = await self.context.load_artifact_content(
            context=context, filename=file_part.name, version="latest"
        )

        if not content:
            raise ValueError(f"Failed to load content for {file_part.name}")

        return content

    async def _create_image_content(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> ImageContent:
        """Creates MCP ImageContent from file part."""
        content = await self._load_file_content_if_needed(file_part, context)

        return ImageContent(
            type="image",
            data=base64.b64encode(content).decode("utf-8"),
            mimeType=file_part.mime_type or "image/png",
        )

    async def _create_audio_content(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> AudioContent:
        """Creates MCP AudioContent from file part."""
        content = await self._load_file_content_if_needed(file_part, context)

        return AudioContent(
            type="audio",
            data=base64.b64encode(content).decode("utf-8"),
            mimeType=file_part.mime_type or "audio/mpeg",
        )

    async def _create_text_embedded_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> EmbeddedResource:
        """Creates MCP EmbeddedResource with TextResourceContents."""
        content = await self._load_file_content_if_needed(file_part, context)
        text = content.decode("utf-8")

        # Use session-scoped URI
        uri = f"{self.context.adapter_config.resource_uri_prefix}://{context.session_id}/{file_part.name}"

        return EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri=uri, mimeType=file_part.mime_type, text=text
            ),
        )

    async def _create_blob_embedded_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> EmbeddedResource:
        """Creates MCP EmbeddedResource with BlobResourceContents."""
        content = await self._load_file_content_if_needed(file_part, context)

        uri = f"{self.context.adapter_config.resource_uri_prefix}://{context.session_id}/{file_part.name}"

        return EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=uri,
                mimeType=file_part.mime_type,
                blob=base64.b64encode(content).decode("utf-8"),
            ),
        )

    async def _create_resource_link(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> ResourceLink:
        """Registers file as MCP resource and returns ResourceLink."""
        # Register the resource
        resource_name, uri, size = await self._register_artifact_resource(
            file_part, context
        )

        return ResourceLink(
            type="resource_link",
            uri=uri,
            name=file_part.name,
            description=f"Artifact: {file_part.name}",
            mimeType=file_part.mime_type,
            size=size,
        )

    async def _register_artifact_resource(
        self, file_part: SamFilePart, context: ResponseContext
    ) -> tuple[str, str, Optional[int]]:
        """
        Registers an artifact as available via the MCP resource template.

        This doesn't create individual resources, but tracks the artifact
        so it can be discovered via list_resources and accessed via the template.

        Returns:
            (resource_name, uri, size)
        """
        session_id = context.session_id
        filename = file_part.name

        # Build URI that matches our resource template
        uri = f"{self.context.adapter_config.resource_uri_prefix}://{session_id}/{filename}"

        # Get size
        if file_part.content_bytes:
            size = len(file_part.content_bytes)
        else:
            # Will be loaded on demand
            size = None

        # Track this artifact for the session with metadata (for list_resources)
        if session_id not in self.session_artifacts:
            self.session_artifacts[session_id] = {}

        self.session_artifacts[session_id][filename] = {
            "uri": uri,
            "mime_type": file_part.mime_type or "application/octet-stream",
            "size": size,
            "user_id": context.user_id,
        }

        # Also register as a concrete resource for discoverability via list_resources
        # This allows MCP clients to discover artifacts without knowing filenames in advance
        try:
            # Create a closure that captures session_id and filename
            async def concrete_resource_handler():
                return await self._handle_artifact_resource_read(session_id, filename)

            # Register the concrete resource with FastMCP
            self.mcp_server.add_resource_fn(
                fn=concrete_resource_handler,
                uri=uri,
                name=f"{session_id}_{filename}",
                description=f"Artifact: {filename}",
                mime_type=file_part.mime_type,
            )
            log.debug(f"Registered concrete resource: {uri}")
        except Exception as e:
            log.warning(f"Failed to register concrete resource for {uri}: {e}")

        log.info(
            f"Registered artifact for session {session_id}: {filename} (URI: {uri})"
        )
        return filename, uri, size

    async def _handle_artifact_resource_read(self, session_id: str, filename: str):
        """
        Handles MCP resource read requests for artifacts.

        Args:
            session_id: The session ID from the URI
            filename: The filename from the URI

        Returns:
            TextResourceContents or BlobResourceContents for FastMCP
        """
        config: McpAdapterConfig = self.context.adapter_config

        # Check if this artifact exists for this session
        if (
            session_id not in self.session_artifacts
            or filename not in self.session_artifacts[session_id]
        ):
            raise ValueError(f"Artifact not found: {filename} in session {session_id}")

        # Get artifact metadata
        artifact_metadata = self.session_artifacts[session_id][filename]
        user_id = artifact_metadata.get("user_id", config.default_user_identity)
        mime_type = artifact_metadata.get("mime_type", "application/octet-stream")

        # Create a ResponseContext for loading
        response_context = ResponseContext(
            task_id="resource-read",
            session_id=session_id,
            user_id=user_id,
            platform_context={},
        )

        # Load artifact content from the artifact service
        content = await self.context.load_artifact_content(
            context=response_context, filename=filename, version="latest"
        )

        if not content:
            raise ValueError(f"Failed to load artifact content: {filename}")

        # Build URI
        uri = artifact_metadata.get(
            "uri", f"{config.resource_uri_prefix}://{session_id}/{filename}"
        )

        # Return based on whether it's text or binary
        if is_text_based_file(mime_type, content):
            return TextResourceContents(
                uri=uri, mimeType=mime_type, text=content.decode("utf-8")
            )
        else:
            return BlobResourceContents(
                uri=uri,
                mimeType=mime_type,
                blob=base64.b64encode(content).decode("utf-8"),
            )

    def _deregister_session_artifacts(self, session_id: str):
        """Clears artifact tracking for a session."""
        if session_id not in self.session_artifacts:
            return

        artifact_count = len(self.session_artifacts[session_id])
        log.info(f"Clearing {artifact_count} artifact(s) for session {session_id}")

        del self.session_artifacts[session_id]

    def get_session_artifacts(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of all artifacts for a given session.

        This is useful for debugging and can also be exposed via a tool/API.

        Args:
            session_id: The session ID (e.g., "mcp-client-abc123")

        Returns:
            List of artifact metadata dicts with uri, filename, mime_type, size
        """
        if session_id not in self.session_artifacts:
            return []

        artifacts = []
        for filename, metadata in self.session_artifacts[session_id].items():
            artifacts.append(
                {
                    "filename": filename,
                    "uri": metadata.get("uri"),
                    "mime_type": metadata.get("mime_type"),
                    "size": metadata.get("size"),
                }
            )

        return artifacts

    # --- Required GatewayAdapter Methods ---

    async def extract_auth_claims(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> Optional[AuthClaims]:
        """
        Extract authentication claims from MCP request.

        This method implements OAuth authentication by:
        1. Checking if auth is enabled and not in dev mode
        2. Extracting bearer token from external_input
        3. Validating token against SAM's OAuth2 service
        4. Retrieving user info and creating AuthClaims

        If auth is disabled or in dev mode, falls back to default_user_identity.

        Args:
            external_input: Dictionary containing MCP request data
            endpoint_context: Optional endpoint-specific context

        Returns:
            AuthClaims with authenticated user info, or None if auth fails
        """
        config: McpAdapterConfig = self.context.adapter_config

        # Dev mode bypass (insecure, for development only)
        if config.dev_mode:
            log.debug(
                "Dev mode: Using default_user_identity=%s", config.default_user_identity
            )
            return AuthClaims(
                id=config.default_user_identity,
                source="mcp_dev",
                raw_context={"dev_mode": True},
            )

        # Authentication disabled - use default identity
        if not config.enable_auth:
            log.debug(
                "Auth disabled: Using default_user_identity=%s",
                config.default_user_identity,
            )
            return AuthClaims(id=config.default_user_identity, source="mcp")

        # OAuth authentication enabled - extract and validate token
        log.debug("OAuth authentication enabled, extracting token from request")

        # Extract token from external_input (could be in headers, metadata, or direct field)
        access_token = oauth_utils.extract_bearer_token_from_dict(
            external_input,
            token_keys=["access_token", "token", "Authorization", "authorization"],
        )

        if not access_token:
            log.warning("OAuth enabled but no access token found in MCP request")
            return None

        # Validate token and get user info
        try:
            claims = await oauth_utils.validate_and_create_auth_claims(
                auth_service_url=config.external_auth_service_url,
                auth_provider=config.external_auth_provider,
                access_token=access_token,
                source="mcp",
            )

            if claims:
                log.info("Successfully authenticated MCP user: %s", claims.id)
                return claims
            else:
                log.warning("Token validation failed for MCP request")
                return None

        except Exception as e:
            log.error("Error during OAuth authentication: %s", e)
            # If OAuth service is unreachable, fail closed (reject request)
            return None

    async def prepare_task(
        self, external_input: Dict, endpoint_context: Optional[Dict[str, Any]] = None
    ) -> SamTask:
        """
        Convert MCP tool invocation into a SamTask.

        Args:
            external_input: Dict with tool_name, agent_name, skill_id, message, mcp_client_id
            endpoint_context: Optional context with mcp_client_id

        Returns:
            SamTask ready for submission to SAM agent
        """
        agent_name = external_input.get("agent_name")
        message = external_input.get("message", "")
        tool_name = external_input.get("tool_name", "")
        mcp_client_id = external_input.get("mcp_client_id")

        if not agent_name:
            raise ValueError("Missing agent_name in external_input")

        if not message.strip():
            raise ValueError("Empty message")

        if not mcp_client_id:
            raise ValueError("Missing mcp_client_id in external_input")

        # Use connection-based session ID (persistent across tool calls)
        # This allows artifacts to accumulate and be accessible across multiple tool invocations
        session_id = f"mcp-client-{mcp_client_id}"

        # Create a simple text task with RUN_BASED behavior
        return SamTask(
            parts=[self.context.create_text_part(message)],
            session_id=session_id,
            target_agent=agent_name,
            is_streaming=True,
            session_behavior="RUN_BASED",  # No chat history between calls
            platform_context={
                "tool_name": tool_name,
                "mcp_client_id": mcp_client_id,
            },
        )

    async def handle_update(self, update: SamUpdate, context: ResponseContext) -> None:
        """
        Handle streaming updates from SAM agent.

        This puts chunks into the task's queue for the stream consumer to send.
        """
        task_id = context.task_id
        config: McpAdapterConfig = self.context.adapter_config

        # Get the queue for this task (if it exists)
        stream_queue = self.task_queues.get(task_id)

        for part in update.parts:
            if isinstance(part, SamTextPart):
                # Buffer text for final response
                if task_id not in self.task_buffers:
                    self.task_buffers[task_id] = []
                self.task_buffers[task_id].append(part.text)

                # Stream to MCP client via queue if enabled
                if config.stream_responses and stream_queue:
                    try:
                        stream_queue.put_nowait(part.text)
                    except Exception as e:
                        log.warning(
                            "Failed to queue text chunk for task %s: %s", task_id, e
                        )

            elif isinstance(part, SamFilePart):
                log.info("Received file part: %s", part.name)

                # Determine how to return this file
                content_type = self._determine_content_type(part, config)

                # Create appropriate content based on type
                content_obj = None
                try:
                    if content_type == "image":
                        content_obj = await self._create_image_content(part, context)
                    elif content_type == "audio":
                        content_obj = await self._create_audio_content(part, context)
                    elif content_type == "text_embedded":
                        content_obj = await self._create_text_embedded_resource(
                            part, context
                        )
                    elif content_type == "blob_embedded":
                        content_obj = await self._create_blob_embedded_resource(
                            part, context
                        )
                    elif content_type == "resource_link":
                        content_obj = await self._create_resource_link(part, context)
                except Exception as e:
                    log.error(
                        f"Failed to create {content_type} content for {part.name}: {e}",
                        exc_info=True,
                    )
                    # Fallback to simple notification
                    if stream_queue:
                        try:
                            stream_queue.put_nowait(
                                f"⚠️ Failed to process file: {part.name}"
                            )
                        except Exception as queue_err:
                            log.warning(
                                f"Failed to queue error notification: {queue_err}"
                            )
                    continue

                # Queue the content object for streaming
                if content_obj and stream_queue:
                    try:
                        stream_queue.put_nowait(content_obj)
                        log.debug(f"Queued {content_type} content for {part.name}")
                    except Exception as e:
                        log.warning(
                            f"Failed to queue {content_type} for task {task_id}: {e}"
                        )

            elif isinstance(part, SamDataPart):
                # Handle special data types
                data_type = part.data.get("type")

                if data_type == "agent_progress_update":
                    status = part.data.get("status_text", "")
                    if stream_queue and status:
                        try:
                            stream_queue.put_nowait(f"Status: {status}")
                        except Exception as e:
                            log.warning("Failed to queue status update: %s", e)

    async def handle_task_complete(self, context: ResponseContext) -> None:
        """
        Handle task completion.

        This method:
        1. Assembles the final response from buffered text chunks
        2. Signals stream completion via queue
        3. Resolves the Future (unblocking _handle_tool_call)
        4. Cleans up all task state
        """
        task_id = context.task_id

        # Assemble final response from buffer
        response_text = "".join(self.task_buffers.get(task_id, []))

        # If empty, provide a default message
        if not response_text.strip():
            response_text = "Task completed successfully (no text response)"

        # Signal stream completion to consumer
        if task_id in self.task_queues:
            try:
                await self.task_queues[task_id].put(STREAM_COMPLETE)
                log.debug("Sent STREAM_COMPLETE signal for task %s", task_id)
            except Exception as e:
                log.warning(
                    "Failed to signal stream completion for task %s: %s", task_id, e
                )

        # Resolve the Future - this unblocks _handle_tool_call()
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            if not future.done():
                future.set_result(response_text)
                log.info(
                    "Task %s completed, returned %d chars to MCP client",
                    task_id,
                    len(response_text),
                )
            else:
                log.warning("Task %s Future was already resolved", task_id)
        else:
            log.warning(
                "Task %s completed but no Future found (may have timed out)", task_id
            )

        # NOTE: Resources are NOT cleaned up here - they persist for the connection lifetime
        # This allows MCP clients to fetch ResourceLinks after task completion

        # Clean up all task state
        self._cleanup_task(task_id)

    async def handle_error(self, error: SamError, context: ResponseContext) -> None:
        """
        Handle errors from SAM.

        This method:
        1. Formats the error message
        2. Signals stream completion via queue
        3. Resolves the Future with the error message (unblocking _handle_tool_call)
        4. Cleans up all task state
        """
        task_id = context.task_id

        # Format error message based on category
        if error.category == "CANCELED":
            error_msg = "Task was canceled"
        else:
            error_msg = f"Error: {error.message}"

        # Signal stream completion to consumer
        if task_id in self.task_queues:
            try:
                await self.task_queues[task_id].put(STREAM_COMPLETE)
                log.debug("Sent STREAM_COMPLETE signal for failed task %s", task_id)
            except Exception as e:
                log.warning(
                    "Failed to signal stream completion for failed task %s: %s",
                    task_id,
                    e,
                )

        # Resolve the Future with error message - this unblocks _handle_tool_call()
        if task_id in self.task_futures:
            future = self.task_futures[task_id]
            if not future.done():
                # Return error message as the result (not raising exception)
                future.set_result(error_msg)
                log.error(
                    "Task %s failed with %s: %s", task_id, error.category, error.message
                )
            else:
                log.warning("Task %s Future was already resolved before error", task_id)
        else:
            log.warning(
                "Task %s failed but no Future found (may have timed out)", task_id
            )

        # Clean up all task state
        self._cleanup_task(task_id)

    # --- Agent Registry Change Handlers ---

    async def handle_agent_registered(self, agent_card: AgentCard) -> None:
        """
        Dynamically register new MCP tools when agents come online.

        This method is called when a new agent publishes its AgentCard.
        It registers MCP tools for each of the agent's skills.

        Args:
            agent_card: The AgentCard of the newly registered agent
        """
        log.info(
            "Agent %s registered with %d skills, adding tools to MCP server...",
            agent_card.name,
            len(agent_card.skills) if agent_card.skills else 0,
        )

        if not agent_card.skills:
            log.debug(f"Agent {agent_card.name} has no skills, no tools to register")
            return

        # Track which tools we register for this agent
        tool_names = []

        for skill in agent_card.skills:
            tool_name = sanitize_tool_name(f"{agent_card.name}_{skill.name}")
            tool_names.append(tool_name)

            # Register the tool (this handles duplicates)
            self._register_tool_for_skill(agent_card, skill)

        # Store mapping for later removal
        self.agent_to_tools[agent_card.name] = tool_names

        log.info(
            "Successfully registered %d MCP tools for agent %s: %s",
            len(tool_names),
            agent_card.name,
            ", ".join(tool_names),
        )

    async def handle_agent_deregistered(self, agent_name: str) -> None:
        """
        Remove MCP tools when agent goes offline.

        This method is called when an agent is removed from the registry
        (e.g., due to TTL expiry). It removes all tools associated with
        that agent from the MCP server.

        Args:
            agent_name: Name of the agent that was removed
        """
        if agent_name not in self.agent_to_tools:
            log.debug(f"Agent {agent_name} deregistered but had no registered tools")
            return

        tool_names = self.agent_to_tools[agent_name]
        log.info(
            "Agent %s deregistered, removing %d MCP tools...",
            agent_name,
            len(tool_names),
        )

        for tool_name in tool_names:
            try:
                # Use FastMCP's remove_tool method
                # This automatically sends notification to connected MCP clients
                self.mcp_server.remove_tool(tool_name)

                # Clean up mapping
                if tool_name in self.tool_to_agent_map:
                    del self.tool_to_agent_map[tool_name]

                log.debug(f"Removed MCP tool: {tool_name}")

            except Exception as e:
                log.error(f"Failed to remove tool {tool_name}: {e}", exc_info=True)

        # Clean up agent mapping
        del self.agent_to_tools[agent_name]

        log.info(
            "Successfully removed all tools for agent %s",
            agent_name,
        )
