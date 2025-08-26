"""
Solace Agent Mesh App class for the McpGateway Gateway.
"""

from typing import Any, Dict, List, Type

from solace_ai_connector.common.log import log
from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import McpGatewayGatewayComponent

info = {
    "class_name": "McpGatewayGatewayApp",
    "description": "Custom App class for the A2A McpGateway Gateway.",
}

class McpGatewayGatewayApp(BaseGatewayApp):
    """
    App class for the A2A McpGateway Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines McpGateway-specific configuration parameters below.
    """

    # Define MCP Gateway-specific parameters
    # This list will be automatically merged with BaseGatewayApp's schema.
    # These parameters will be configurable in the yaml config file
    # under the 'app_config' section.
    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "mcp_host",
            "required": False,
            "type": "string", 
            "default": "127.0.0.1",
            "description": "Host address for the MCP HTTP server.",
        },
        {
            "name": "mcp_port",
            "required": False,
            "type": "integer",
            "default": 8080,
            "description": "Port for the MCP HTTP server.",
        },
        {
            "name": "agent_discovery_interval",
            "required": False,
            "type": "integer",
            "default": 60,
            "description": "Agent discovery refresh interval in seconds.",
        },
        {
            "name": "tool_name_format",
            "required": False,
            "type": "string",
            "default": "{agent_name}_agent",
            "description": "Format string for MCP tool names. Use {agent_name} placeholder.",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log_prefix = app_info.get("name", "McpGatewayGatewayApp")
        log.debug("[%s] Initializing McpGatewayGatewayApp...", log_prefix)
        super().__init__(app_info=app_info, **kwargs)
        log.debug("[%s] McpGatewayGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this app.
        """
        return McpGatewayGatewayComponent