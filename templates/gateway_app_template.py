"""
Solace Agent Mesh App class for the __GATEWAY_NAME_PASCAL_CASE__ Gateway.
"""

import logging
from typing import Any, Dict, List, Type

from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import __GATEWAY_NAME_PASCAL_CASE__GatewayComponent

log = logging.getLogger(__name__)

info = {
    "class_name": "__GATEWAY_NAME_PASCAL_CASE__GatewayApp",
    "description": "Custom App class for the A2A __GATEWAY_NAME_PASCAL_CASE__ Gateway.",
}

class __GATEWAY_NAME_PASCAL_CASE__GatewayApp(BaseGatewayApp):
    """
    App class for the A2A __GATEWAY_NAME_PASCAL_CASE__ Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines __GATEWAY_NAME_PASCAL_CASE__-specific configuration parameters below.
    """

    # Define __GATEWAY_NAME_PASCAL_CASE__-specific parameters
    # This list will be automatically merged with BaseGatewayApp's schema.
    # These parameters will be configurable in the yaml config file
    # under the 'app_config' section.
    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        # --- Example Required Parameter ---
        # {
        #     "name": "api_endpoint_url",
        #     "required": True,
        #     "type": "string",
        #     "description": "The API endpoint URL for the __GATEWAY_NAME_SNAKE_CASE__ service.",
        # },
        # --- Example Optional Parameter with Default ---
        # {
        #     "name": "connection_timeout_seconds",
        #     "required": False,
        #     "type": "integer",
        #     "default": 30,
        #     "description": "Timeout in seconds for connecting to the __GATEWAY_NAME_SNAKE_CASE__ service.",
        # },
        # --- Example List Parameter ---
        # {
        #     "name": "processing_rules",
        #     "required": False,
        #     "type": "list",
        #     "default": [],
        #     "description": "List of processing rules for the gateway.",
        #     "items": { # Schema for each item in the list
        #         "type": "object",
        #         "properties": {
        #             "rule_name": {"type": "string", "required": True},
        #             "action_type": {"type": "string", "enum": ["process", "ignore"]},
        #             # ... other rule-specific schema fields
        #         }
        #     }
        # }
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log_prefix = app_info.get("name", "__GATEWAY_NAME_PASCAL_CASE__GatewayApp")
        log.debug("[%s] Initializing __GATEWAY_NAME_PASCAL_CASE__GatewayApp...", log_prefix)
        super().__init__(app_info=app_info, **kwargs)
        log.debug("[%s] __GATEWAY_NAME_PASCAL_CASE__GatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this app.
        """
        return __GATEWAY_NAME_PASCAL_CASE__GatewayComponent
