"""
Solace Agent Mesh Component class for the McpGateway Gateway.
"""

import asyncio  # If needed for async operations with external system
import base64
import time
from datetime import datetime, timezone
from ..solace_agent_mesh.common.types import TaskState
from typing import Any, Dict, List, Optional, Tuple, Union, Annotated
from pydantic import Field, BaseModel

from solace_ai_connector.common.log import log
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from fastmcp import FastMCP, Context
from solace_agent_mesh.common.types import (
    Part as A2APart,
    TextPart,
    FilePart,  # If handling files
    DataPart,  # If handling structured data
    Task,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    FileContent,  # Added for FilePart example
)

from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    load_artifact_content_or_metadata,
    get_artifact_info_list,
)
from solace_agent_mesh.common.utils.mime_helpers import is_text_based_mime_type

# from solace_agent_mesh.core_a2a.service import CoreA2AService # If direct interaction needed

class FileUpload(BaseModel):
    """Simple schema for file uploads in MCP tools"""
    filename: str
    content: str

info = {
    "class_name": "McpGatewayGatewayComponent",
    "description": (
        "Implements the A2A McpGateway Gateway, inheriting from BaseGatewayComponent. "
        "Handles communication between the mcp_gateway system and the A2A agent ecosystem."
    ),
    "config_parameters": [],  # Defined by McpGatewayGatewayApp
    "input_schema": {
        "type": "object",
        "description": "Not typically used directly by GDK; component reacts to external events or A2A control messages.",
    },
    "output_schema": {
        "type": "object",
        "description": "Not typically used directly by GDK; component publishes results to external system or A2A.",
    },
}


class McpGatewayGatewayComponent(BaseGatewayComponent):
    """
    Solace Agent Mesh Component implementing the A2A McpGateway Gateway.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        log.info(
            "%s Initializing MCP Gateway Component (Post-Base)...",
            self.log_identifier,
        )

        # --- Retrieve MCP Gateway-Specific Configurations ---
        self.mcp_host = self.get_config("mcp_host", "127.0.0.1")
        self.mcp_port = self.get_config("mcp_port", 8080)
        self.agent_discovery_interval = self.get_config("agent_discovery_interval", 60)
        self.tool_name_format = self.get_config("tool_name_format", "{agent_name}_agent")

        # --- Initialize FastMCP Server with optional OAuth ---
        if self.get_config("enable_authentication", False):
            self.mcp_server = FastMCP(name="Solace Agent Mesh", auth=self._create_oauth_proxy())
        else:
            self.mcp_server = FastMCP(name="Solace Agent Mesh")
        
        self.registered_agents = {}  # Track registered agent tools: {agent_name: tool_name}
        self.discovery_task = None
        self.http_server_task = None
        
        # Streaming response management for MCP tools
        self.streaming_responses = {}  # {task_id: {"text_buffer": str, "artifacts": []}}
        self.streaming_lock = asyncio.Lock()

        # Register MCP resources and tools for file handling
        self._register_artifact_resources_and_tools()

        log.info(
            "%s MCP Gateway Component initialization complete. Server: %s:%d",
            self.log_identifier, self.mcp_host, self.mcp_port
        )

    def _create_oauth_proxy(self):
        """Create OAuth proxy with appropriate token verification for the provider"""
        try:
            from fastmcp.server.auth import OAuthProxy
            
            # Construct the base URL - this must match your Azure redirect URI exactly
            base_url = self.get_config("oauth_base_url") or f"http://{self.mcp_host}:{self.mcp_port}"
            log.info("%s OAuth proxy base URL: %s", self.log_identifier, base_url)
            
            # Get scopes configuration
            scopes_config = self.get_config("oauth_scopes", "openid profile email")
            required_scopes = scopes_config.split() if scopes_config else []
            
            # Detect provider and use appropriate token verifier
            auth_endpoint = self.get_config("oauth_authorization_endpoint", "")
            
            if "login.microsoftonline.com" in auth_endpoint:
                # Azure requires Graph API validation instead of JWT verification
                log.info("%s Detected Azure OAuth provider - using Graph API token verification", self.log_identifier)
                from fastmcp.server.auth.providers.azure import AzureTokenVerifier
                token_verifier = AzureTokenVerifier(
                    required_scopes=required_scopes + ["User.Read"],  # User.Read needed for Graph API
                    timeout_seconds=10
                )
            else:
                # Standard JWT verification for most other providers (Google, etc.)
                log.info("%s Using standard JWT token verification", self.log_identifier)
                from fastmcp.server.auth.providers.jwt import JWTVerifier
                token_verifier = JWTVerifier(
                    jwks_uri=self.get_config("oauth_jwks_uri"),
                    issuer=self.get_config("oauth_issuer"),
                    audience=self.get_config("oauth_audience"),
                    required_scopes=required_scopes
                )
            
            # Create OAuth proxy with appropriate token verifier
            return OAuthProxy(
                upstream_authorization_endpoint=self.get_config("oauth_authorization_endpoint"),
                upstream_token_endpoint=self.get_config("oauth_token_endpoint"),
                upstream_client_id=self.get_config("oauth_client_id"),
                upstream_client_secret=self.get_config("oauth_client_secret"),
                token_verifier=token_verifier,
                base_url=base_url,
                redirect_path="/mcp/auth/callback"
            )
        except Exception as e:
            log.exception("%s Error creating OAuth proxy: %s", self.log_identifier, e)
            raise

    def _register_artifact_resources_and_tools(self):
        """Register MCP resources and tools for artifact file handling"""
        log_id_prefix = f"{self.log_identifier}[RegisterArtifactResources]"
        
        if not self.get_config("enable_artifact_resources", True):
            log.info("%s Artifact resources disabled in configuration", log_id_prefix)
            return
            
        try:
            # Register dynamic artifact resource template
            @self.mcp_server.resource(
                "artifact://{app_name}/{user_id}/{session_id}/{filename}",
                name="Agent Artifact",
                description="Artifact file generated by SAM agents",
                annotations={
                    "readOnlyHint": True,
                    "idempotentHint": True
                }
            )
            async def get_agent_artifact(app_name: str, user_id: str, session_id: str, filename: str, ctx: Context) -> Union[str, bytes]:
                """Dynamic resource template for agent-generated artifacts"""
                return await self._get_artifact_content(app_name, user_id, session_id, filename, ctx)
            
            # Removed list_agent_artifacts tool - clients should use resources directly via URIs
            
            log.info("%s Successfully registered artifact resources and tools", log_id_prefix)
            
        except Exception as e:
            log.exception("%s Error registering artifact resources: %s", log_id_prefix, e)
            raise

    def _start_listener(self) -> None:
        """
        GDK Hook: Start the MCP HTTP server and agent discovery loop.
        This method is called by BaseGatewayComponent.run().
        """
        log_id_prefix = f"{self.log_identifier}[StartListener]"
        log.info(
            "%s Starting MCP HTTP server on %s:%d...",
            log_id_prefix, self.mcp_host, self.mcp_port
        )

        # Start MCP server in a separate thread (similar to HTTP SSE pattern)
        import threading
        
        def run_server():
            # Run the FastMCP server with HTTP transport
            self.mcp_server.run(
                transport="http",
                host=self.mcp_host,
                port=self.mcp_port
            )
        
        self.mcp_thread = threading.Thread(target=run_server, daemon=True, name="MCP_Server_Thread")
        self.mcp_thread.start()
        
        # Start agent discovery in the async loop
        if hasattr(self, 'async_loop') and self.async_loop:
            # Create discovery task - this should work since we're in the component's async context
            import asyncio
            try:
                # Get the current event loop (should be the component's loop)
                loop = asyncio.get_event_loop()
                self.discovery_task = loop.create_task(self._agent_discovery_loop())
                log.info("%s Agent discovery task started.", log_id_prefix)
            except Exception as e:
                log.exception("%s Error starting agent discovery: %s", log_id_prefix, e)
        
        log.info("%s MCP gateway listener startup complete.", log_id_prefix)

    async def _agent_discovery_loop(self):
        """Periodic agent discovery and tool registration loop"""
        log_id_prefix = f"{self.log_identifier}[AgentDiscovery]"
        log.info("%s Starting agent discovery loop...", log_id_prefix)
        
        while not self.stop_signal.is_set():
            try:
                # Get current agents from registry
                current_agents = await self._discover_agents()
                
                # Register new agents as tools
                for agent_name, agent_info in current_agents.items():
                    if agent_name not in self.registered_agents:
                        self._register_agent_as_tool(agent_name, agent_info)
                
                # Remove tools for agents that no longer exist
                for agent_name in list(self.registered_agents.keys()):
                    if agent_name not in current_agents:
                        self._unregister_agent_tool(agent_name)
                
                log.debug("%s Agent discovery cycle complete. Registered: %d agents", 
                         log_id_prefix, len(self.registered_agents))
                await asyncio.sleep(self.agent_discovery_interval)
                
            except asyncio.CancelledError:
                log.info("%s Agent discovery loop cancelled.", log_id_prefix)
                break
            except Exception as e:
                log.exception("%s Error in agent discovery loop: %s", log_id_prefix, e)
                await asyncio.sleep(60)  # Wait before retry on error
        
        log.info("%s Agent discovery loop stopped.", log_id_prefix)

    async def _discover_agents(self) -> Dict[str, Dict[str, Any]]:
        """Discover available agents from the agent registry"""
        log_id_prefix = f"{self.log_identifier}[DiscoverAgents]"
        
        try:
            if not self.agent_registry:
                log.warning("%s Agent registry not available", log_id_prefix)
                return {}
            
            # Get all available agent names from the registry
            agent_names = self.agent_registry.get_agent_names()
            log.debug("%s Discovered %d agents", log_id_prefix, len(agent_names))
            
            # Get full agent cards for each name
            agent_dict = {}
            for agent_name in agent_names:
                agent_card = self.agent_registry.get_agent(agent_name)
                if agent_card:
                    agent_dict[agent_name] = {
                        "description": agent_card.description or f"Agent: {agent_name}",
                        "capabilities": agent_card.capabilities,
                        "skills": agent_card.skills
                    }
                else:
                    # Fallback if agent card not found
                    agent_dict[agent_name] = {
                        "description": f"Agent: {agent_name}",
                        "capabilities": [],
                        "skills": []
                    }
            
            return agent_dict
            
        except Exception as e:
            log.exception("%s Error discovering agents: %s", log_id_prefix, e)
            return {}

    def _register_agent_as_tool(self, agent_name: str, agent_info: Dict[str, Any]):
        """Register an agent as an MCP tool"""
        log_id_prefix = f"{self.log_identifier}[RegisterTool]"
        
        try:
            tool_name = self.tool_name_format.format(agent_name=agent_name)
            description = agent_info.get("description", f"Interact with {agent_name} agent")
            
            # Create dynamic tool function
            async def agent_tool(
                message: str,
                files: Optional[Union[List[FileUpload], str]] = None
            ) -> str:
                """Dynamically created tool for agent interaction with file support"""
                return await self._call_agent_via_a2a(agent_name, message, files)
            
            # Set function metadata
            agent_tool.__name__ = tool_name
            agent_tool.__doc__ = description
            
            # Register with FastMCP
            self.mcp_server.tool(agent_tool)
            self.registered_agents[agent_name] = tool_name
            
            log.info("%s Registered agent '%s' as MCP tool '%s'", 
                    log_id_prefix, agent_name, tool_name)
            
        except Exception as e:
            log.exception("%s Error registering agent '%s' as tool: %s", 
                         log_id_prefix, agent_name, e)

    def _unregister_agent_tool(self, agent_name: str):
        """Remove an agent tool from MCP server"""
        log_id_prefix = f"{self.log_identifier}[UnregisterTool]"
        
        try:
            tool_name = self.registered_agents.get(agent_name)
            if tool_name:
                # Remove from FastMCP server
                self.mcp_server.remove_tool(tool_name)
                del self.registered_agents[agent_name]
                
                log.info("%s Unregistered agent '%s' tool '%s'", 
                        log_id_prefix, agent_name, tool_name)
            
        except Exception as e:
            log.exception("%s Error unregistering agent '%s' tool: %s", 
                         log_id_prefix, agent_name, e)

    async def _call_agent_via_a2a(self, agent_name: str, message: str, files: Optional[Union[List[FileUpload], str]] = None) -> str:
        """Calls an agent via A2A protocol with proper OAuth user context"""
        log_id_prefix = f"{self.log_identifier}[CallAgent:{agent_name}]"
        log.info("%s MCP tool called for agent '%s' with message: %s", 
                log_id_prefix, agent_name, message[:50] + "..." if len(message) > 50 else message)
        
        # Handle case where files might be passed as JSON string
        if files and isinstance(files, str):
            try:
                import json
                files_data = json.loads(files)
                files = [FileUpload(**file_data) for file_data in files_data]
                log.info("%s Parsed files from JSON string: %d files", log_id_prefix, len(files))
            except Exception as e:
                log.error("%s Failed to parse files JSON string: %s", log_id_prefix, e)
                files = None
        
        try:
            # Get authenticated user identity
            authenticated_user = await self._authenticate_external_user(None)  # MCP token in context
            if not authenticated_user:
                return "Authentication required. Please authenticate with the MCP gateway."
            
            # Get user details for better context
            initial_claims = await self._extract_initial_claims(None)
            user_identity = {
                "id": authenticated_user,
                "name": initial_claims.get("name", "OAuth User") if initial_claims else "OAuth User",
                "source": "oauth"
            }
            
            # Create session ID for artifact storage
            session_id = f"mcp-oauth-{self.generate_uuid()}"
            
            # Create A2A parts starting with the message
            a2a_parts = [TextPart(text=message)]
            
            # Process files if provided (Phase 1 Substep 2: Save to artifact service)
            if files and self.shared_artifact_service:
                log.info("%s Received %d files from MCP client:", log_id_prefix, len(files))
                file_metadata_summary_parts = []
                
                for i, file_upload in enumerate(files):
                    try:
                        filename = file_upload.filename
                        content = file_upload.content
                        
                        # Simple approach: treat all content as text, auto-detect if it's base64
                        try:
                            # Try to decode as base64 first (binary files)
                            content_bytes = base64.b64decode(content, validate=True)
                            encoding = "base64"
                            mime_type = "application/octet-stream"
                        except:
                            # If not valid base64, treat as text
                            content_bytes = content.encode('utf-8')
                            encoding = "text"
                            mime_type = "text/plain"
                        
                        if not content_bytes:
                            log.warning("%s Skipping empty file: %s", log_id_prefix, filename)
                            continue
                            
                        log.info("%s Processing file: %s (%d bytes, %s)", 
                                log_id_prefix, filename, len(content_bytes), encoding)
                        
                        # Save to artifact service (following HTTP SSE gateway pattern)
                        save_result = await save_artifact_with_metadata(
                            artifact_service=self.shared_artifact_service,
                            app_name=self.gateway_id,
                            user_id=authenticated_user,
                            session_id=session_id,
                            filename=filename,
                            content_bytes=content_bytes,
                            mime_type=mime_type,
                            metadata_dict={
                                "source": "mcp_gateway_upload",
                                "original_filename": filename,
                                "upload_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "gateway_id": self.gateway_id,
                                "mcp_user_id": authenticated_user,
                                "a2a_session_id": session_id,
                                "encoding": encoding,
                            },
                            timestamp=datetime.now(timezone.utc),
                        )
                        
                        if save_result["status"] in ["success", "partial_success"]:
                            data_version = save_result.get("data_version", 0)
                            artifact_uri = f"artifact://{self.gateway_id}/{authenticated_user}/{session_id}/{filename}?version={data_version}"
                            
                            # Create FileContent object
                            file_content = FileContent(
                                name=filename,
                                mimeType=mime_type,
                                uri=artifact_uri,
                            )
                            
                            # Add FilePart to A2A message
                            a2a_parts.append(FilePart(file=file_content))
                            file_metadata_summary_parts.append(
                                f"- {filename} ({len(content_bytes)} bytes, {encoding}, URI: {artifact_uri})"
                            )
                            
                            log.info("%s Successfully saved file to artifact service: %s", 
                                    log_id_prefix, artifact_uri)
                        else:
                            log.error("%s Failed to save file %s: %s", 
                                    log_id_prefix, filename, save_result.get("message"))
                        
                    except Exception as e:
                        log.exception("%s Error processing file (%s): %s", 
                                     log_id_prefix, filename if 'filename' in locals() else f"file_{i}", e)
                
                # Add file summary to message if files were processed
                if file_metadata_summary_parts:
                    file_summary = (
                        "The user uploaded the following file(s):\n" + 
                        "\n".join(file_metadata_summary_parts) + 
                        f"\n\nUser message: {message}"
                    )
                    # Update the text part with file information
                    a2a_parts[0] = TextPart(text=file_summary)
                    
            elif files and not self.shared_artifact_service:
                log.error("%s Files provided but artifact service not available", log_id_prefix)
                return "File upload not available: artifact service not configured"
            else:
                log.debug("%s No files provided with this request", log_id_prefix)
            
            # Create external request context
            external_request_context = {
                "user_id_for_a2a": authenticated_user,
                "app_name_for_artifacts": self.gateway_id,
                "user_id_for_artifacts": authenticated_user,
                "a2a_session_id": session_id,
                "original_message": message,
                "target_agent": agent_name,
                "source": "mcp_oauth_gateway"
            }
            
            # Submit A2A task and wait for completion (streaming to get artifact events)
            task_id = await self.submit_a2a_task(
                target_agent_name=agent_name,
                a2a_parts=a2a_parts,
                external_request_context=external_request_context,
                user_identity=user_identity,
                is_streaming=True  # Streaming to receive TaskArtifactUpdateEvent
            )
            
            # Initialize streaming response buffer for this task
            async with self.streaming_lock:
                self.streaming_responses[task_id] = {
                    "text_buffer": "",
                    "artifacts": []
                }
            
            log.info("%s Submitted OAuth-authenticated A2A task %s for user %s", 
                    log_id_prefix, task_id, authenticated_user)
            
            # Wait for task completion (simple polling approach for Phase 2)
            response_text = await self._wait_for_task_completion(task_id, external_request_context)
            
            log.info("%s Task %s completed successfully", log_id_prefix, task_id)
            return response_text
            
        except Exception as e:
            log.exception("%s Error calling agent '%s': %s", log_id_prefix, agent_name, e)
            return f"Error communicating with agent '{agent_name}': {str(e)}"

    async def _get_artifact_content(self, app_name: str, user_id: str, session_id: str, filename: str, ctx: Context) -> Union[str, bytes]:
        """Get artifact content for MCP resource template"""
        log_id_prefix = f"{self.log_identifier}[GetArtifactContent:{filename}]"
        
        try:
            # Authenticate user from MCP context
            authenticated_user = await self._authenticate_external_user(None)
            if not authenticated_user:
                from fastmcp.exceptions import ResourceError
                raise ResourceError("Authentication required")
                
            # Verify user can access this artifact (basic authorization)
            if authenticated_user != user_id:
                from fastmcp.exceptions import ResourceError 
                raise ResourceError("Access denied to artifact")
            
            if not self.shared_artifact_service:
                from fastmcp.exceptions import ResourceError
                raise ResourceError("Artifact service not available")
            
            # Load artifact using existing helper
            result = await load_artifact_content_or_metadata(
                artifact_service=self.shared_artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                version="latest",  # Default to latest version
                return_raw_bytes=True,
                log_identifier_prefix=log_id_prefix
            )
            
            if result.get("status") != "success":
                from fastmcp.exceptions import ResourceError
                raise ResourceError(f"Failed to load artifact: {result.get('message', 'Unknown error')}")
            
            raw_bytes = result.get("raw_bytes")
            mime_type = result.get("mime_type", "application/octet-stream")
            
            log.info("%s Successfully loaded artifact %s (%d bytes, %s)", 
                    log_id_prefix, filename, len(raw_bytes), mime_type)
            
            # Return content per MCP spec: text as string, binary as base64
            if is_text_based_mime_type(mime_type):
                try:
                    return raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    # Fallback to base64 if text decoding fails
                    return base64.b64encode(raw_bytes).decode("ascii")
            else:
                # Return binary as base64 string
                return base64.b64encode(raw_bytes).decode("ascii")
                
        except Exception as e:
            log.exception("%s Error getting artifact content: %s", log_id_prefix, e)
            # Re-raise as ResourceError for proper MCP error handling
            from fastmcp.exceptions import ResourceError
            if isinstance(e, ResourceError):
                raise
            raise ResourceError(f"Internal error loading artifact: {str(e)}")

    async def _list_agent_artifacts(self, session_id: str = None, ctx: Context = None) -> dict:
        """List available artifacts with enhanced metadata for MCP clients"""
        log_id_prefix = f"{self.log_identifier}[ListAgentArtifacts]"
        
        try:
            # Authenticate user from MCP context
            authenticated_user = await self._authenticate_external_user(None)
            if not authenticated_user:
                return {"error": "Authentication required", "artifacts": []}
            
            # Use provided session_id or try to determine from context
            target_session_id = session_id
            if not target_session_id and ctx and hasattr(ctx, 'request_id'):
                # We could try to map request context to session, but for now use a default approach
                # This could be enhanced based on how sessions are managed in MCP context
                log.warning("%s No session_id provided and cannot determine from context", log_id_prefix)
                return {"error": "session_id parameter required", "artifacts": []}
            
            if not self.shared_artifact_service:
                return {"error": "Artifact service not available", "artifacts": []}
            
            # Get artifact list using existing helper
            artifacts = await get_artifact_info_list(
                artifact_service=self.shared_artifact_service,
                app_name=self.gateway_id,
                user_id=authenticated_user,
                session_id=target_session_id
            )
            
            # Enhance with MCP-specific metadata
            enhanced_artifacts = []
            max_auto_read_size = self.get_config("max_auto_read_size_bytes", 1048576)
            large_file_threshold = self.get_config("large_file_threshold_tokens", 10000)
            
            for artifact in artifacts:
                file_size = getattr(artifact, 'size_bytes', 0) or 0
                estimated_tokens = file_size // 4  # Rough estimate: 4 bytes per token
                
                enhanced = {
                    "filename": artifact.filename,
                    "size_bytes": file_size,
                    "mime_type": getattr(artifact, 'mime_type', 'application/octet-stream'),
                    "uri": f"artifact://{self.gateway_id}/{authenticated_user}/{target_session_id}/{artifact.filename}",
                    "estimated_tokens": estimated_tokens,
                    "auto_read_safe": file_size <= max_auto_read_size,
                    "large_file_warning": estimated_tokens > large_file_threshold,
                    "last_modified": getattr(artifact, 'last_modified', None)
                }
                enhanced_artifacts.append(enhanced)
            
            log.info("%s Found %d artifacts for user %s, session %s", 
                    log_id_prefix, len(enhanced_artifacts), authenticated_user, target_session_id)
            
            return {
                "artifacts": enhanced_artifacts, 
                "session_id": target_session_id,
                "user_id": authenticated_user,
                "count": len(enhanced_artifacts)
            }
            
        except Exception as e:
            log.exception("%s Error listing artifacts: %s", log_id_prefix, e)
            return {"error": f"Failed to list artifacts: {str(e)}", "artifacts": []}

    async def _register_signaled_artifacts_as_resources(self, external_request_context: Dict[str, Any], task_data: Task) -> None:
        """Register individual artifact resources - NO-OP in streaming mode since artifacts are handled via _send_update_to_external"""
        log_id_prefix = f"{self.log_identifier}[RegisterSignaledArtifacts]"
        task_id = task_data.id
        
        if not self.get_config("enable_artifact_resources", True):
            log.debug("%s Artifact resource registration disabled", log_id_prefix)
            return
            
        # In streaming mode, all artifacts should have been registered via TaskArtifactUpdateEvent in _send_update_to_external
        # This method becomes a no-op since we're using streaming A2A tasks
        log.debug("%s Using streaming mode - artifacts already registered via _send_update_to_external. Task %s artifacts in final response: %d", 
                 log_id_prefix, task_id, len(task_data.artifacts) if task_data.artifacts else 0)
        
        # No need to process task_data.artifacts since streaming handles everything
        return

    async def _enhance_response_with_artifact_info(self, response_text: str, external_request_context: Dict[str, Any], task_data: Task) -> str:
        """Enhance response with information about available artifacts so MCP client knows to fetch them"""
        log_id_prefix = f"{self.log_identifier}[EnhanceResponse]"
        
        if not self.get_config("enable_artifact_resources", True):
            return response_text
            
        # Extract artifact information from task completion
        available_artifacts = []
        user_id = external_request_context.get("user_id_for_artifacts") 
        session_id = external_request_context.get("a2a_session_id")
        
        if task_data.artifacts:
            for artifact in task_data.artifacts:
                if artifact.parts:
                    for part in artifact.parts:
                        if isinstance(part, FilePart) and part.file:
                            if part.file.uri:
                                # Parse artifact URI to get details
                                try:
                                    uri_info = self._parse_artifact_uri(part.file.uri)
                                    if uri_info:
                                        available_artifacts.append({
                                            'filename': uri_info['filename'],
                                            'uri': part.file.uri,
                                            'name': part.file.name or uri_info['filename'],
                                            'mime_type': part.file.mimeType or 'application/octet-stream'
                                        })
                                except Exception as e:
                                    log.warning("%s Error parsing artifact URI %s: %s", log_id_prefix, part.file.uri, e)
        
        if not available_artifacts:
            return response_text
            
        # Build explicit MCP resource information for client
        artifact_info_lines = [
            "\n\n📎 **New MCP Resources Created:**",
            "The agent has created the following files as MCP resources (you should have received resource notifications):"
        ]
        
        for artifact in available_artifacts:
            filename = artifact['filename']
            mime_type = artifact['mime_type']
            uri = artifact['uri']
            
            artifact_info_lines.append(f"- **{filename}** ({mime_type})")
            artifact_info_lines.append(f"  MCP Resource URI: `{uri}`")
        
        artifact_info_lines.extend([
            "",
            "**How to access these files:**",
            "1. Use MCP `resources/read` with the URIs above to fetch file content",
            "2. Your MCP client should have been notified of these new resources automatically"
        ])
        
        enhanced_response = response_text + "\n".join(artifact_info_lines)
        
        log.info("%s Enhanced response with %d artifact(s) information", log_id_prefix, len(available_artifacts))
        return enhanced_response

    def _parse_artifact_uri(self, uri: str) -> Optional[Dict[str, str]]:
        """Parse artifact:// URI to extract components"""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(uri)
            if parsed.scheme != "artifact":
                return None
            
            # URI format: artifact://app_name/user_id/session_id/filename?version=N
            # Since netloc might be empty, we need to handle the path properly
            full_path = parsed.netloc + parsed.path if parsed.netloc else parsed.path
            path_parts = full_path.strip("/").split("/")
            
            if len(path_parts) != 4:
                return None
                
            app_name, user_id, session_id, filename = path_parts
            
            query_params = parse_qs(parsed.query)
            version = query_params.get("version", ["latest"])[0]
            
            return {
                "app_name": app_name,
                "user_id": user_id, 
                "session_id": session_id,
                "filename": filename,
                "version": version
            }
        except Exception:
            return None

    # async def _poll_external_system(self): # Example polling loop
    #     log_id_prefix = f"{self.log_identifier}[PollLoop]"
    #     log.info("%s Starting mcp_gateway polling loop...", log_id_prefix)
    #     while not self.stop_signal.is_set():
    #         try:
    #             # new_events = await self.external_client.get_new_events() # Or sync equivalent
    #             # for event_data in new_events:
    #             #     # Process each event: authenticate, translate, submit A2A task
    #             #     # This often involves calling other GDK methods or internal helpers
    #             #     authenticated_user = await self._authenticate_external_user(event_data)
    #             #     if authenticated_user:
    #             #         target_agent, parts, context = await self._translate_external_input(event_data, authenticated_user)
    #             #         if target_agent and parts:
    #             #             await self.submit_a2a_task(target_agent, parts, context, authenticated_user)
    #             # await asyncio.sleep(self.get_config("polling_interval_seconds", 60))
    #             pass # Placeholder
    #         except asyncio.CancelledError:
    #             log.info("%s Polling loop cancelled.", log_id_prefix)
    #             break
    #         except Exception as e:
    #             log.exception("%s Error in polling loop: %s", log_id_prefix, e)
    #             await asyncio.sleep(60) # Wait before retrying on error
    #     log.info("%s mcp_gateway polling loop stopped.", log_id_prefix)

    async def _wait_for_task_completion(self, task_id: str, external_request_context: Dict[str, Any], timeout_seconds: int = 120) -> str:
        """Wait for A2A task completion and return aggregated streaming response"""
        log_id_prefix = f"{self.log_identifier}[WaitTask:{task_id}]"
        
        import asyncio
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check if we've exceeded timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                # Clean up streaming response buffer on timeout
                async with self.streaming_lock:
                    self.streaming_responses.pop(task_id, None)
                raise TimeoutError(f"Task {task_id} did not complete within {timeout_seconds} seconds")
            
            # Check task context for completion
            task_context = self.task_context_manager.get_context(task_id)
            if not task_context:
                # Task completed - combine streaming buffer with final response and enhance with artifacts
                try:
                    # Get streaming data
                    async with self.streaming_lock:
                        streaming_data = self.streaming_responses.pop(task_id, {})
                    
                    # Get buffered streaming text
                    buffered_response = streaming_data.get("text_buffer", "")
                    
                    # Get final response from _send_final_response_to_external (if any)
                    response_key = f"{task_id}_response"
                    stored_response = self.task_context_manager.get_context(response_key)
                    if stored_response:
                        self.task_context_manager.remove_context(response_key)
                    
                    # Combine streaming buffer with final response (prefer streaming buffer if both exist)
                    final_response = buffered_response or stored_response or "Task completed."
                    
                    # Get artifacts registered during streaming
                    artifacts = streaming_data.get("artifacts", [])
                    
                    # Enhance response with artifact information if any were created
                    if artifacts:
                        enhanced_response = await self._enhance_streaming_response_with_artifacts(
                            final_response, artifacts
                        )
                        log.info("%s Returning enhanced response with %d artifact(s)", 
                                log_id_prefix, len(artifacts))
                        return enhanced_response
                    else:
                        log.info("%s Returning final response (no artifacts)", log_id_prefix)
                        return final_response
                        
                except Exception as e:
                    log.exception("%s Error processing streaming response: %s", log_id_prefix, e)
                    return f"Task completed with response processing error: {str(e)}"
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
    async def _enhance_streaming_response_with_artifacts(self, response_text: str, artifacts: List[Dict]) -> str:
        """Enhance streaming response with artifact information for MCP client"""
        log_id_prefix = f"{self.log_identifier}[EnhanceStreamingResponse]"
        
        if not artifacts:
            return response_text
            
        # Build explicit MCP resource information for client (same format as _enhance_response_with_artifact_info)
        artifact_info_lines = [
            "\n\n📎 **New MCP Resources Created:**",
            "The agent has created the following files as MCP resources (you should have received resource notifications):"
        ]
        
        for artifact in artifacts:
            filename = artifact['filename']
            mime_type = artifact['mime_type']
            uri = artifact['uri']
            
            artifact_info_lines.append(f"- **{filename}** ({mime_type})")
            artifact_info_lines.append(f"  MCP Resource URI: `{uri}`")
        
        artifact_info_lines.extend([
            "",
            "**How to access these files:**",
            "1. Use MCP `resources/read` with the URIs above to fetch file content",
            "2. IMPORTANT: IF a file is returned then you must return it to the user, since only important files are signaled to be returned back",
        ])
        
        enhanced_response = response_text + "\n".join(artifact_info_lines)
        
        log.info("%s Enhanced streaming response with %d artifact(s) information", log_id_prefix, len(artifacts))
        return enhanced_response
    
    def _stop_listener(self) -> None:
        """
        GDK Hook: Stop the MCP HTTP server and clean up resources.
        This method is called by BaseGatewayComponent.cleanup().
        """
        log_id_prefix = f"{self.log_identifier}[StopListener]"
        log.info("%s Stopping MCP HTTP server and tasks...", log_id_prefix)

        # Cancel agent discovery task
        if hasattr(self, 'discovery_task') and self.discovery_task and not self.discovery_task.done():
            self.discovery_task.cancel()
            log.info("%s Agent discovery task cancelled", log_id_prefix)
        
        # MCP server thread will stop when the process exits (daemon thread)
        if hasattr(self, 'mcp_thread') and self.mcp_thread and self.mcp_thread.is_alive():
            log.info("%s MCP server thread will exit with process", log_id_prefix)

        # Clear registered agents
        self.registered_agents.clear()

        log.info("%s MCP gateway listener shutdown complete.", log_id_prefix)
        
    async def _extract_initial_claims(self, external_event_data: Any) -> Optional[Dict[str, Any]]:
        """Extract identity claims from MCP OAuth request"""
        log_id_prefix = f"{self.log_identifier}[ExtractClaims]"
        
        if not self.get_config("enable_authentication", False):
            # No auth mode - return anonymous user
            return {
                "user_id": "anonymous",
                "email": "anonymous@local",
                "name": "Anonymous User",
                "source": "no_auth"
            }
        
        try:
            from fastmcp.server.dependencies import get_access_token
            
            token = get_access_token()
            if not token or not token.claims:
                log.warning("%s No valid OAuth token found in request", log_id_prefix)
                return None
            
            claims = token.claims
            
            # Extract primary identifiers
            user_id = claims.get("sub") or claims.get("user_id") or claims.get("id")
            email = claims.get("email") or claims.get("preferred_username")
            
            if not user_id:
                log.warning("%s No user ID found in OAuth token claims", log_id_prefix)
                return None
            
            # Build initial claims
            initial_claims = {
                "user_id": user_id,
                "email": email,
                "name": claims.get("name") or email or user_id,
                "provider": claims.get("iss", "unknown"),
                "source": "oauth",
                "raw_claims": claims
            }
            
            log.debug("%s Extracted initial claims for user: %s", log_id_prefix, user_id)
            return initial_claims
            
        except Exception as e:
            log.exception("%s Error extracting OAuth claims: %s", log_id_prefix, e)
            return None
    
    async def _translate_external_input(self, external_event_data: Any, authenticated_user_identity: str) -> Tuple[Optional[str], List[A2APart], Dict[str, Any]]:
        """Translate MCP tool call to A2A format"""
        # This method is called by BaseGatewayComponent for external events
        # For MCP gateway, this is handled directly in _call_agent_via_a2a
        # Return empty values as this won't be used in our MCP flow
        return None, [], {}
    
    async def _send_final_response_to_external(self, external_request_context: Dict[str, Any], task_data: Task) -> None:
        """Send final A2A task result back to MCP client"""
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        task_id = task_data.id
        
        try:
            # PHASE 2: Process artifact signals for MCP resource registration
            await self._register_signaled_artifacts_as_resources(external_request_context, task_data)
            
            # Extract response text from task status
            response_text = "Task completed."
            if task_data.status and task_data.status.message and task_data.status.message.parts:
                text_parts = []
                for part in task_data.status.message.parts:
                    if isinstance(part, TextPart) and part.text:
                        text_parts.append(part.text)
                
                if text_parts:
                    response_text = "".join(text_parts)
            
            # Check if task failed
            if task_data.status and task_data.status.state == TaskState.FAILED:
                response_text = f"Task failed: {response_text}"
            
            # In streaming mode, store plain response text and let _wait_for_task_completion handle artifact enhancement
            # This avoids duplicate artifact information since streaming artifacts are already tracked
            response_key = f"{task_id}_response"
            self.task_context_manager.store_context(response_key, response_text)
            
            log.debug("%s Stored plain response text for streaming enhancement by _wait_for_task_completion", log_id_prefix)
            
            log.info("%s Stored final response for task %s: %s", log_id_prefix, task_id, 
                    response_text[:100] + "..." if len(response_text) > 100 else response_text)
            
        except Exception as e:
            log.exception("%s Error processing final response for task %s: %s", log_id_prefix, task_id, e)
            # Store error as response
            error_response = f"Error processing response: {str(e)}"
            response_key = f"{task_id}_response"
            self.task_context_manager.store_context(response_key, error_response)
    
    async def _send_error_to_external(self, external_request_context: Dict[str, Any], error_data: JSONRPCError) -> None:
        """Send A2A error back to MCP client"""
        log_id_prefix = f"{self.log_identifier}[SendError]"
        
        # Extract task ID from context if available
        task_id = external_request_context.get("a2a_task_id_for_event")
        if not task_id:
            log.warning("%s No task ID found in context for error handling", log_id_prefix)
            return
        
        # Store error as response
        error_message = f"A2A Error: {error_data.message} (Code: {error_data.code})"
        response_key = f"{task_id}_response"
        self.task_context_manager.store_context(response_key, error_message)
        
        log.warning("%s Stored error response for task %s: %s", log_id_prefix, task_id, error_message)
    
    async def _send_update_to_external(self, external_request_context: Dict[str, Any], event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent], is_final_chunk_of_update: bool) -> None:
        """Send intermediate A2A task updates to external system"""
        # For Phase 2, we're using non-streaming mode, so this is a no-op
        # In Phase 3, we could implement streaming updates here
        pass

    async def _authenticate_external_user(
        self, external_event_data: Any  # Type hint with actual external event data type
    ) -> Optional[str]:
        """
        Authenticate and get user identity from OAuth token
        """
        log_id_prefix = f"{self.log_identifier}[AuthenticateUser]"
        
        # Extract initial claims first
        initial_claims = await self._extract_initial_claims(external_event_data)
        if not initial_claims:
            log.warning("%s Failed to extract initial claims", log_id_prefix)
            return None
        
        user_id = initial_claims.get("user_id")
        email = initial_claims.get("email")
        name = initial_claims.get("name")
        
        log.info("%s Authenticated user: %s (%s)", log_id_prefix, name, email or user_id)
        
        # Return identifier for A2A (email preferred, fallback to user_id)
        return email or user_id




    async def _send_update_to_external(
        self,
        external_request_context: Dict[str, Any],
        event_data: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent],
        is_final_chunk_of_update: bool,
    ) -> None:
        """
        GDK Hook: Process streaming A2A updates for MCP gateway.
        - TaskStatusUpdateEvent: Buffer text for final aggregated response
        - TaskArtifactUpdateEvent: Register MCP resources immediately for client notification
        """
        task_id = event_data.id
        log_id_prefix = f"{self.log_identifier}[SendUpdate:{task_id}]"
        
        if isinstance(event_data, TaskStatusUpdateEvent):
            # Buffer text parts for final aggregated response (like Slack implementation)
            if (event_data.status 
                and event_data.status.message 
                and event_data.status.message.parts):
                
                text_parts = []
                for part in event_data.status.message.parts:
                    if isinstance(part, TextPart):
                        text_parts.append(part.text)
                        log.debug("%s Buffering text part: %d chars", log_id_prefix, len(part.text))
                    elif isinstance(part, DataPart):
                        if part.data.get("a2a_signal_type") == "agent_status_message":
                            # Log agent status but don't include in final response
                            status_text = part.data.get("text", "[Agent status update]")
                            log.debug("%s Agent status signal: %s", log_id_prefix, status_text)
                
                if text_parts:
                    combined_text = "".join(text_parts)
                    async with self.streaming_lock:
                        if task_id in self.streaming_responses:
                            self.streaming_responses[task_id]["text_buffer"] += combined_text
                            log.debug("%s Updated text buffer (total: %d chars)", 
                                    log_id_prefix, len(self.streaming_responses[task_id]["text_buffer"]))
        
        elif isinstance(event_data, TaskArtifactUpdateEvent):
            # Register artifacts as MCP resources immediately (based on Slack file handling)
            log.info("%s Processing TaskArtifactUpdateEvent", log_id_prefix)
            
            if event_data.artifact and event_data.artifact.parts:
                artifacts_registered = 0
                for part in event_data.artifact.parts:
                    if isinstance(part, FilePart) and part.file and part.file.uri:
                        try:
                            # Parse artifact URI to get details
                            uri_info = self._parse_artifact_uri(part.file.uri)
                            if uri_info:
                                filename = uri_info['filename']
                                resource_uri = part.file.uri
                                user_id = external_request_context.get("user_id_for_artifacts")
                                session_id = external_request_context.get("a2a_session_id")
                                
                                # Don't register individual resources - the dynamic template already handles all artifacts
                                # The template "artifact://{app_name}/{user_id}/{session_id}/{filename}" covers this URI
                                
                                # Also track for final response enhancement
                                # Use clean URI without version for MCP client (template handles version automatically)
                                clean_uri = f"artifact://{self.gateway_id}/{user_id}/{session_id}/{filename}"
                                artifact_info = {
                                    'filename': filename,
                                    'uri': clean_uri,  # Clean URI without version query params
                                    'name': part.file.name or filename,
                                    'mime_type': part.file.mimeType or 'application/octet-stream'
                                }
                                async with self.streaming_lock:
                                    if task_id in self.streaming_responses:
                                        self.streaming_responses[task_id]["artifacts"].append(artifact_info)
                                
                                artifacts_registered += 1
                                log.info("%s Artifact available via dynamic template: %s", 
                                        log_id_prefix, resource_uri)
                                        
                        except Exception as e:
                            log.warning("%s Error registering resource for artifact %s: %s", 
                                       log_id_prefix, part.file.uri, e)
                
                if artifacts_registered > 0:
                    log.info("%s Tracked %d artifacts from streaming event - available via dynamic resource template", 
                            log_id_prefix, artifacts_registered)
        
        else:
            log.debug("%s Received unknown event type: %s", log_id_prefix, type(event_data).__name__)

    def generate_uuid(self) -> str:
        """Generate a unique UUID string"""
        import uuid
        return str(uuid.uuid4())

    # async def save_to_artifact_service(self, content_bytes: bytes, filename: str, mime_type: str, user_id: str, session_id: str) -> Optional[str]:
    #     """Helper to save content to the shared artifact service."""
    #     if not self.shared_artifact_service:
    #         log.error("%s Artifact service not available. Cannot save file: %s", self.log_identifier, filename)
    #         return None
    #     try:
    #         from src.solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata # Adjust import
    #         from datetime import datetime, timezone

    #         save_result = await save_artifact_with_metadata(
    #             artifact_service=self.shared_artifact_service,
    #             app_name=self.gateway_id, # from BaseGatewayComponent
    #             user_id=user_id,
    #             session_id=session_id,
    #             filename=filename,
    #             content_bytes=content_bytes,
    #             mime_type=mime_type,
    #             metadata_dict={
    #                 "source": "mcp_gateway_upload",
    #                 "original_filename": filename,
    #                 "upload_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    #             },
    #             timestamp=datetime.now(timezone.utc)
    #         )
    #         if save_result["status"] in ["success", "partial_success"]:
    #             data_version = save_result.get("data_version", 0)
    #             artifact_uri = f"artifact://{self.gateway_id}/{user_id}/{session_id}/{filename}?version={data_version}"
    #             log.info("%s Saved artifact: %s", self.log_identifier, artifact_uri)
    #             return artifact_uri
    #         else:
    #             log.error("%s Failed to save artifact %s: %s", self.log_identifier, filename, save_result.get("message"))
    #             return None
    #     except Exception as e:
    #         log.exception("%s Error saving artifact %s: %s", self.log_identifier, filename, e)
    #         return None

    def cleanup(self):
        """
        GDK Hook: Called before the component is fully stopped.
        Perform any final cleanup specific to this component beyond _stop_listener.
        """
        log.info(
            "%s Cleaning up McpGateway Gateway Component (Pre-Base)...",
            self.log_identifier,
        )
        # Example: Close any persistent connections not handled in _stop_listener
        # if hasattr(self, "persistent_connection") and self.persistent_connection.is_open():
        #     self.persistent_connection.close()
        super().cleanup()  # Important to call super().cleanup()
        log.info(
            "%s McpGateway Gateway Component cleanup finished.",
            self.log_identifier,
        )
