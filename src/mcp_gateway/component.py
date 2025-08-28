"""
Solace Agent Mesh Component class for the McpGateway Gateway.
"""

import asyncio  # If needed for async operations with external system
import base64
import time
from datetime import datetime, timezone
from ..solace_agent_mesh.common.types import TaskState
from typing import Any, Dict, List, Optional, Tuple, Union

from solace_ai_connector.common.log import log
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from fastmcp import FastMCP
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

from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

# from solace_agent_mesh.core_a2a.service import CoreA2AService # If direct interaction needed

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
                files: list[dict[str, str]] = None
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

    async def _call_agent_via_a2a(self, agent_name: str, message: str, files: list[dict[str, str]] = None) -> str:
        """Calls an agent via A2A protocol with proper OAuth user context"""
        log_id_prefix = f"{self.log_identifier}[CallAgent:{agent_name}]"
        log.info("%s MCP tool called for agent '%s' with message: %s", 
                log_id_prefix, agent_name, message[:50] + "..." if len(message) > 50 else message)
        
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
                
                for i, file_dict in enumerate(files):
                    # Claude sends files as {filename: content} pairs
                    for filename, content in file_dict.items():
                        try:
                            # Convert content to bytes (Claude sends raw text)
                            if isinstance(content, str):
                                content_bytes = content.encode('utf-8')
                            else:
                                content_bytes = content
                        
                            if not content_bytes:
                                log.warning("%s Skipping empty file: %s", log_id_prefix, filename)
                                continue
                                
                            log.info("%s Processing file: %s (%d bytes)", 
                                    log_id_prefix, filename, len(content_bytes))
                            
                            # Save to artifact service (following HTTP SSE gateway pattern)
                            save_result = await save_artifact_with_metadata(
                                artifact_service=self.shared_artifact_service,
                                app_name=self.gateway_id,
                                user_id=authenticated_user,
                                session_id=session_id,
                                filename=filename,
                                content_bytes=content_bytes,
                                mime_type="application/octet-stream",  # Default, could be improved with MIME detection
                                metadata_dict={
                                    "source": "mcp_gateway_upload",
                                    "original_filename": filename,
                                    "upload_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "gateway_id": self.gateway_id,
                                    "mcp_user_id": authenticated_user,
                                    "a2a_session_id": session_id,
                                },
                                timestamp=datetime.now(timezone.utc),
                            )
                            
                            if save_result["status"] in ["success", "partial_success"]:
                                data_version = save_result.get("data_version", 0)
                                artifact_uri = f"artifact://{self.gateway_id}/{authenticated_user}/{session_id}/{filename}?version={data_version}"
                                
                                # Create FileContent object
                                file_content = FileContent(
                                    name=filename,
                                    mimeType="application/octet-stream",
                                    uri=artifact_uri,
                                )
                                
                                # Add FilePart to A2A message
                                a2a_parts.append(FilePart(file=file_content))
                                file_metadata_summary_parts.append(
                                    f"- {filename} ({len(content_bytes)} bytes, URI: {artifact_uri})"
                                )
                                
                                log.info("%s Successfully saved file to artifact service: %s", 
                                        log_id_prefix, artifact_uri)
                            else:
                                log.error("%s Failed to save file %s: %s", 
                                        log_id_prefix, filename, save_result.get("message"))
                            
                        except Exception as e:
                            log.exception("%s Error processing file (%s): %s", 
                                         log_id_prefix, filename, e)
                
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
            
            # Submit A2A task and wait for completion
            task_id = await self.submit_a2a_task(
                target_agent_name=agent_name,
                a2a_parts=a2a_parts,
                external_request_context=external_request_context,
                user_identity=user_identity,
                is_streaming=False  # Non-streaming for Phase 2 simplicity
            )
            
            log.info("%s Submitted OAuth-authenticated A2A task %s for user %s", 
                    log_id_prefix, task_id, authenticated_user)
            
            # Wait for task completion (simple polling approach for Phase 2)
            response_text = await self._wait_for_task_completion(task_id, external_request_context)
            
            log.info("%s Task %s completed successfully", log_id_prefix, task_id)
            return response_text
            
        except Exception as e:
            log.exception("%s Error calling agent '%s': %s", log_id_prefix, agent_name, e)
            return f"Error communicating with agent '{agent_name}': {str(e)}"

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

    async def _wait_for_task_completion(self, task_id: str, external_request_context: Dict[str, Any], timeout_seconds: int = 30) -> str:
        """Wait for A2A task completion and extract response text"""
        log_id_prefix = f"{self.log_identifier}[WaitTask:{task_id}]"
        
        import asyncio
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check if we've exceeded timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                raise TimeoutError(f"Task {task_id} did not complete within {timeout_seconds} seconds")
            
            # Check task context for completion
            task_context = self.task_context_manager.get_context(task_id)
            if not task_context:
                # Task context removed means task completed or failed
                # Check if we have a stored response
                response_key = f"{task_id}_response"
                stored_response = self.task_context_manager.get_context(response_key)
                if stored_response:
                    self.task_context_manager.remove_context(response_key)
                    return stored_response
                else:
                    raise RuntimeError(f"Task {task_id} completed but no response found")
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
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
            
            # Store response for _wait_for_task_completion to retrieve
            response_key = f"{task_id}_response"
            self.task_context_manager.store_context(response_key, response_text)
            
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
        GDK Hook: Sends intermediate A2A task updates (status or artifacts) to the external system.
        - This is optional. If your gateway doesn't support streaming intermediate updates,
        - you can leave this method as a no-op (just log).
        - `is_final_chunk_of_update`: True if this is the last part of a streamed TextPart from TaskStatusUpdateEvent.
        """
        log_id_prefix = f"{self.log_identifier}[SendUpdate]"
        # task_id = event_data.id
        # log.debug("%s Received A2A update for task %s. Type: %s. FinalChunk: %s",
        #           log_id_prefix, task_id, type(event_data).__name__, is_final_chunk_of_update)

        # --- Implement Logic to Send Intermediate Update (if supported) ---
        # if isinstance(event_data, TaskStatusUpdateEvent):
        #     if event_data.status and event_data.status.message and event_data.status.message.parts:
        #         for part in event_data.status.message.parts:
        #             if isinstance(part, TextPart):
        #                 # Send part.text to external system
        #                 pass
        #             elif isinstance(part, DataPart) and part.data.get("a2a_signal_type") == "agent_status_message":
        #                 # Send agent status signal text part.data.get("text")
        #                 pass
        # elif isinstance(event_data, TaskArtifactUpdateEvent):
        #     # Handle artifact updates (e.g., notify external system of new artifact URI)
        #     pass

        # Default: Log that this gateway does not handle intermediate updates.
        # log.debug("%s McpGateway Gateway does not process intermediate updates. Update for task %s ignored.",
        #           log_id_prefix, task_id)
        pass  # No-op by default

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
