"""
Custom Solace AI Connector App class for the Universal Webhook Gateway.
Defines configuration schema and programmatically creates the WebhookGatewayComponent.
"""

from typing import Any, Dict, List, Type

from solace_ai_connector.common.log import log

from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import WebhookGatewayComponent


info = {
    "class_name": "WebhookGatewayApp",
    "description": "Custom App class for the Universal Webhook Gateway.",
}


class WebhookGatewayApp(BaseGatewayApp):
    """
    Custom App class for the Universal Webhook Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines Webhook Gateway-specific configuration parameters.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "webhook_server_host",
            "required": False,
            "type": "string",
            "default": "0.0.0.0",
            "description": "Host address for the embedded FastAPI server.",
        },
        {
            "name": "webhook_server_port",
            "required": False,
            "type": "integer",
            "default": 8080,
            "description": "Port for the embedded FastAPI server.",
        },
        {
            "name": "cors_allowed_origins",
            "required": False,
            "type": "list",
            "default": ["*"],
            "items": {"type": "string"},
            "description": "List of allowed origins for CORS requests (e.g., ['http://localhost:3000']). Use ['*'] to allow all.",
        },
        {
            "name": "system_purpose",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Global system purpose for tasks initiated via this Webhook gateway. This can be used by agents to understand the broader context of requests. Per-endpoint definitions for this key in 'webhook_endpoints' will not be used for A2A metadata.",
        },
        {
            "name": "response_format",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Global response format guidelines for tasks initiated via this Webhook gateway. Agents can use this to tailor their responses. Per-endpoint definitions for this key in 'webhook_endpoints' will not be used for A2A metadata.",
        },
        {
            "name": "webhook_endpoints",
            "required": True,
            "type": "list",
            "description": "List of configurations for each dynamic webhook endpoint.",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "required": True,
                        "description": "HTTP URL path for the endpoint (e.g., '/hooks/my-data-feed'). Must start with a '/'.",
                    },
                    "method": {
                        "type": "string",
                        "required": False,
                        "default": "POST",
                        "enum": [
                            "GET",
                            "POST",
                            "PUT",
                            "DELETE",
                            "PATCH",
                            "HEAD",
                            "OPTIONS",
                        ],
                        "description": "HTTP method for the endpoint.",
                    },
                    "target_agent_name": {
                        "type": "string",
                        "required": True,
                        "description": "The name of the A2A agent to which tasks from this endpoint will be routed.",
                    },
                    "input_template": {
                        "type": "string",
                        "required": True,
                        "description": "SAC message template string to generate the text content for the A2A task.",
                    },
                    "auth": {
                        "type": "object",
                        "required": False,
                        "default": {"type": "none"},
                        "description": "Authentication configuration for this endpoint.",
                        "properties": {
                            "type": {
                                "type": "string",
                                "required": True,
                                "default": "none",
                                "enum": ["none", "token", "basic"],
                                "description": "Authentication type.",
                            },
                            "token_config": {
                                "type": "object",
                                "required": False,
                                "description": "Configuration for token-based authentication.",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "required": True,
                                        "enum": ["header", "query_param"],
                                        "description": "Location of the API token (header or query parameter).",
                                    },
                                    "name": {
                                        "type": "string",
                                        "required": True,
                                        "description": "Name of the header or query parameter containing the token.",
                                    },
                                    "value": {
                                        "type": "string",
                                        "required": True,
                                        "description": "The expected secret token value (supports ${ENV_VAR}).",
                                    },
                                },
                            },
                            "basic_auth_config": {
                                "type": "object",
                                "required": False,
                                "description": "Configuration for HTTP Basic authentication.",
                                "properties": {
                                    "credentials": {
                                        "type": "string",
                                        "required": True,
                                        "description": "Expected 'username:password' string (supports ${ENV_VAR}).",
                                    }
                                },
                            },
                        },
                    },
                    "payload_format": {
                        "type": "string",
                        "required": False,
                        "default": "json",
                        "enum": ["json", "yaml", "text", "form_data", "binary"],
                        "description": "Expected format of the incoming webhook payload. 'xml' and 'form_data' (without files) are treated as 'text'. 'binary' and 'form_data' (with files) imply artifact saving.",
                    },
                    "assumed_user_identity": {
                        "type": "string",
                        "required": False,
                        "default": None,
                        "description": "If provided and endpoint auth passes, this identity is used for A2A scope retrieval.",
                    },
                    "save_payload_as_artifact": {
                        "type": "boolean",
                        "required": False,
                        "default": False,
                        "description": "If true, the entire incoming webhook payload will be saved as an artifact.",
                    },
                    "artifact_filename_template": {
                        "type": "string",
                        "required": False,
                        "default": None,
                        "description": "SAC message template to generate the filename for the saved payload artifact. If empty and saving, a UUID-based name is used.",
                    },
                    "artifact_mime_type_override": {
                        "type": "string",
                        "required": False,
                        "default": None,
                        "description": "Explicitly sets the MIME type for the saved payload artifact, overriding automatic detection.",
                    },
                },
            },
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the WebhookGatewayApp.
        Most setup is handled by BaseGatewayApp.
        """
        log_prefix = app_info.get("name", "WebhookGatewayApp")
        log.debug(
            "[%s] Initializing WebhookGatewayApp...",
            log_prefix,
        )
        super().__init__(app_info=app_info, **kwargs)
        log.debug("[%s] WebhookGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this application.
        """
        return WebhookGatewayComponent
