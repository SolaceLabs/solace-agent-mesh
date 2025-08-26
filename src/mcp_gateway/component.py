"""
Solace Agent Mesh Component class for the McpGateway Gateway.
"""

import asyncio  # If needed for async operations with external system
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

        # --- Initialize FastMCP Server ---
        self.mcp_server = FastMCP(name="Solace Agent Mesh")
        self.registered_agents = {}  # Track registered agent tools: {agent_name: tool_name}
        self.discovery_task = None
        self.http_server_task = None

        log.info(
            "%s MCP Gateway Component initialization complete. Server: %s:%d",
            self.log_identifier, self.mcp_host, self.mcp_port
        )

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
            async def agent_tool(message: str) -> str:
                """Dynamically created tool for agent interaction"""
                return await self._call_agent_via_a2a(agent_name, message)
            
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

    async def _call_agent_via_a2a(self, agent_name: str, message: str) -> str:
        """Placeholder A2A integration - will be implemented in later phases"""
        log.info("%s MCP tool called for agent '%s' with message: %s", 
                self.log_identifier, agent_name, message[:50] + "..." if len(message) > 50 else message)
        return f"Agent '{agent_name}' tool called successfully. Message received: {message[:100]}"

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

    async def _authenticate_external_user(
        self, external_event_data: Any  # Type hint with actual external event data type
    ) -> Optional[str]:
        """
        GDK Hook: Authenticates the user or system from the external event data.
        - Implement logic based on your gateway's authentication mechanism (e.g., API key, token, signature).
        - Use configurations retrieved in __init__ (e.g., self.service_api_key).
        - Return a unique user/system identifier (string) on success, or None on failure.
          This identifier will be used for A2A authorization (scope checking).
        """
        log_id_prefix = f"{self.log_identifier}[AuthenticateUser]"
        # log.debug("%s Authenticating external event: %s", log_id_prefix, external_event_data)

        # --- Implement Authentication Logic Here ---
        # Example: Check an API key from headers or payload
        # provided_key = external_event_data.get("headers", {}).get("X-API-Key")
        # if provided_key and provided_key == self.service_api_key:
        #     user_identity = external_event_data.get("user_id_field", "default_system_user")
        #     log.info("%s Authentication successful for user: %s", log_id_prefix, user_identity)
        #     return user_identity
        # else:
        #     log.warning("%s Authentication failed: API key mismatch or missing.", log_id_prefix)
        #     return None

        # If no authentication is needed for this gateway:
        # return "anonymous_mcp_gateway_user"

        log.warning(
            "%s _authenticate_external_user not fully implemented.", log_id_prefix
        )
        return "placeholder_user_identity"  # Replace with actual logic

    async def _translate_external_input(
        self, external_event_data: Any, authenticated_user_identity: str
    ) -> Tuple[Optional[str], List[A2APart], Dict[str, Any]]:
        """
        GDK Hook: Translates the incoming external event/request into an A2A task.
        - `external_event_data`: The raw data from the external system.
        - `authenticated_user_identity`: The identity returned by _authenticate_external_user.

        Returns a tuple:
        - `target_agent_name` (str | None): Name of the A2A agent to route the task to. None if translation fails.
        - `a2a_parts` (List[A2APart]): List of A2A Parts (TextPart, FilePart, DataPart) for the task.
        - `external_request_context` (Dict[str, Any]): Dictionary to store any context needed later
          (e.g., for _send_final_response_to_external, like original request ID, reply-to address).
        """
        log_id_prefix = f"{self.log_identifier}[TranslateInput]"
        # log.debug("%s Translating external event: %s", log_id_prefix, external_event_data)

        a2a_parts: List[A2APart] = []
        target_agent_name: Optional[str] = (
            None  # Determine this based on event data or config
        )
        external_request_context: Dict[str, Any] = {
            "user_id_for_a2a": authenticated_user_identity,
            "app_name_for_artifacts": self.gateway_id,  # For artifact service context
            "user_id_for_artifacts": authenticated_user_identity,
            "a2a_session_id": f"mcp_gateway-session-{self.generate_uuid()}",  # Example session ID
            # Add any other relevant context from external_event_data needed for response handling
            # "original_request_id": external_event_data.get("id"),
        }

        # --- Implement Translation Logic Here ---
        # 1. Determine Target Agent:
        #    - Statically from config: target_agent_name = self.get_config("default_target_agent")
        #    - Dynamically from event_data: target_agent_name = external_event_data.get("target_agent_field")
        #    - Based on processing_rules:
        #      for rule in self.processing_rules:
        #          if rule.matches(external_event_data):
        #              target_agent_name = rule.get_agent_name()
        #              break
        target_agent_name = "OrchestratorAgent"  # Placeholder

        # 2. Construct A2A Parts:
        #    - Extract text:
        #      text_content = external_event_data.get("message_text", "")
        #      if text_content:
        #          a2a_parts.append(TextPart(text=text_content))
        #    - Handle files (if any): Download, save to artifact service, create FilePart with URI.
        #      (Requires self.shared_artifact_service to be configured and available)
        #      # if "file_url" in external_event_data and self.shared_artifact_service:
        #      #     file_bytes = await download_file(external_event_data["file_url"])
        #      #     file_name = external_event_data.get("file_name", "attachment.dat")
        #      #     mime_type = external_event_data.get("mime_type", "application/octet-stream")
        #      #     artifact_uri = await self.save_to_artifact_service(
        #      #         file_bytes, file_name, mime_type,
        #      #         authenticated_user_identity, external_request_context["a2a_session_id"]
        #      #     )
        #      #     if artifact_uri:
        #      #         a2a_parts.append(FilePart(file=FileContent(name=file_name, mimeType=mime_type, uri=artifact_uri)))
        #    - Handle structured data:
        #      # structured_data = external_event_data.get("data_payload")
        #      # if structured_data:
        #      #    a2a_parts.append(DataPart(data=structured_data, metadata={"source": "mcp_gateway"}))

        # Example: Simple text passthrough
        raw_text = str(
            external_event_data.get(
                "text_input_field", "Default text from mcp_gateway"
            )
        )
        a2a_parts.append(TextPart(text=raw_text))

        if not target_agent_name:
            log.error("%s Could not determine target_agent_name.", log_id_prefix)
            return None, [], {}  # Indicate translation failure

        if not a2a_parts:
            log.warning(
                "%s No A2A parts created from external event. Task might be empty.",
                log_id_prefix,
            )
            # Depending on requirements, you might want to return None, [], {} here too.

        log.info(
            "%s Translation complete. Target: %s, Parts: %d",
            log_id_prefix,
            target_agent_name,
            len(a2a_parts),
        )
        return target_agent_name, a2a_parts, external_request_context

    async def _send_final_response_to_external(
        self, external_request_context: Dict[str, Any], task_data: Task
    ) -> None:
        """
        GDK Hook: Sends the final A2A Task result back to the external mcp_gateway system.
        - `external_request_context`: The context dictionary returned by _translate_external_input.
        - `task_data`: The final A2A Task object (contains status, results, etc.).
        """
        log_id_prefix = f"{self.log_identifier}[SendFinalResponse]"
        # log.debug("%s Sending final response for task %s. Context: %s", log_id_prefix, task_data.id, external_request_context)

        # --- Implement Logic to Send Response to External System ---
        # 1. Extract relevant information from task_data:
        #    - task_data.status.state (e.g., TaskState.COMPLETED, TaskState.FAILED)
        #    - task_data.status.message.parts (usually TextPart for final agent response)
        #    - task_data.artifacts (if agent produced artifacts)

        # 2. Format the response according to the external system's requirements.
        #    response_text = "Task completed."
        #    if task_data.status and task_data.status.message and task_data.status.message.parts:
        #        for part in task_data.status.message.parts:
        #            if isinstance(part, TextPart):
        #                response_text = part.text
        #                break
        #    if task_data.status and task_data.status.state == TaskState.FAILED:
        #        response_text = f"Task failed: {response_text}"

        # 3. Use information from external_request_context to send the response
        #    (e.g., reply-to address, original request ID).
        #    # original_request_id = external_request_context.get("original_request_id")
        #    # await self.external_client.send_reply(original_request_id, response_text)

        log.warning(
            "%s _send_final_response_to_external not fully implemented for task %s.",
            log_id_prefix,
            task_data.id,
        )

    async def _send_error_to_external(
        self, external_request_context: Dict[str, Any], error_data: JSONRPCError
    ) -> None:
        """
        GDK Hook: Sends an A2A error back to the external mcp_gateway system.
        This is called if an error occurs within the A2A GDK processing (e.g., task submission failure,
        authorization failure after initial authentication).
        - `external_request_context`: Context from _translate_external_input.
        - `error_data`: A JSONRPCError object.
        """
        log_id_prefix = f"{self.log_identifier}[SendError]"
        # log.warning("%s Sending error to external system. Error: %s. Context: %s", log_id_prefix, error_data.message, external_request_context)

        # --- Implement Logic to Send Error to External System ---
        # error_message_to_send = f"A2A Error: {error_data.message} (Code: {error_data.code})"
        # # original_request_id = external_request_context.get("original_request_id")
        # # await self.external_client.send_error_reply(original_request_id, error_message_to_send)

        log.warning(
            "%s _send_error_to_external not fully implemented. Error: %s",
            log_id_prefix,
            error_data.message,
        )

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

    # --- Optional: Helper methods for your gateway ---
    def generate_uuid(self) -> str:  # Made this a method of the class
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
