"""
Custom Solace AI Connector App class for the REST API Gateway.
"""

from typing import Any, Dict, List, Type

from solace_ai_connector.common.log import log

from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import RestGatewayComponent

info = {
    "class_name": "RestGatewayApp",
    "description": "App class for the SAM REST API Gateway.",
}


class RestGatewayApp(BaseGatewayApp):
    """
    App class for the SAM REST API Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines REST Gateway-specific configuration parameters.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "rest_api_server_host",
            "required": False,
            "type": "string",
            "default": "127.0.0.1",
            "description": "Host address for the embedded FastAPI server.",
        },
        {
            "name": "rest_api_server_port",
            "required": False,
            "type": "integer",
            "default": 8080,
            "description": "Port for the embedded FastAPI server.",
        },
        {
            "name": "rest_api_https_port",
            "required": False,
            "type": "integer",
            "default": 1943,
            "description": "Port for the embedded FastAPI server.",
        },
    
        {
            "name": "sync_mode_timeout_seconds",
            "required": False,
            "type": "integer",
            "default": 60,
            "description": "Timeout in seconds for synchronous v1 API calls.",
        },
        {
            "name": "enforce_authentication",
            "required": False,
            "type": "boolean",
            "default": True,
            "description": "If true, all API endpoints will require authentication.",
        },
        {
            "name": "external_auth_service_url",
            "required": False,
            "type": "string",
            "description": "URL of the external authentication service for token validation.",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the RestGatewayApp.
        """
        log.debug(
            "%s Initializing RestGatewayApp...",
            app_info.get("name", "RestGatewayApp"),
        )
        super().__init__(app_info=app_info, **kwargs)
        log.debug("%s RestGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this application.
        """
        return RestGatewayComponent
