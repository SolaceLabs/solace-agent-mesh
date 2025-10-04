"""
Custom Solace AI Connector App class for the Web UI Backend.
Defines configuration schema and programmatically creates the WebUIBackendComponent.
"""

from typing import Any, Dict, List
from solace_ai_connector.common.log import log

from ...gateway.http_sse.component import WebUIBackendComponent

from ...gateway.base.app import BaseGatewayApp
from ...gateway.base.component import BaseGatewayComponent


info = {
    "class_name": "WebUIBackendApp",
    "description": "Custom App class for the A2A Web UI Backend with automatic subscription generation.",
}


class WebUIBackendApp(BaseGatewayApp):
    """
    Custom App class for the A2A Web UI Backend.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines WebUI-specific configuration parameters.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "session_secret_key",
            "required": True,
            "type": "string",
            "description": "Secret key for signing web user sessions.",
        },
        {
            "name": "fastapi_host",
            "required": False,
            "type": "string",
            "default": "127.0.0.1",
            "description": "Host address for the embedded FastAPI server.",
        },
        {
            "name": "fastapi_port",
            "required": False,
            "type": "integer",
            "default": 8000,
            "description": "Port for the embedded FastAPI server.",
        },
        {
            "name": "fastapi_https_port",
            "required": False,
            "type": "integer",
            "default": 8443,
            "description": "Port for the embedded FastAPI server when SSL is enabled.",
        },
        {
            "name": "cors_allowed_origins",
            "required": False,
            "type": "list",
            "default": ["*"],
            "description": "List of allowed origins for CORS requests.",
        },
        {
            "name": "sse_max_queue_size",
            "required": False,
            "type": "integer",
            "default": 200,
            "description": "Maximum size of the SSE connection queues. Adjust based on expected load.",
        },
        {
            "name": "resolve_artifact_uris_in_gateway",
            "required": False,
            "type": "boolean",
            "default": True,
            "description": "If true, the gateway will resolve artifact:// URIs found in A2A messages and embed the content as bytes before sending to the UI. If false, URIs are passed through.",
        },
        {
            "name": "system_purpose",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Detailed description of the system's overall purpose, to be optionally used by agents.",
        },
        {
            "name": "response_format",
            "required": False,
            "type": "string",
            "default": "",
            "description": "General guidelines on how agent responses should be structured, to be optionally used by agents.",
        },
        {
            "name": "frontend_welcome_message",
            "required": False,
            "type": "string",
            "default": "Hi! How can I help?",
            "description": "Initial welcome message displayed in the chat.",
        },
        {
            "name": "frontend_bot_name",
            "required": False,
            "type": "string",
            "default": "A2A Agent",
            "description": "Name displayed for the bot/agent in the UI.",
        },
        {
            "name": "frontend_collect_feedback",
            "required": False,
            "type": "boolean",
            "default": False,
            "description": "Enable/disable the feedback buttons in the UI.",
        },
        {
            "name": "frontend_auth_login_url",
            "required": False,
            "type": "string",
            "default": "",
            "description": "URL for the external login page (if auth is enabled).",
        },
        {
            "name": "frontend_use_authorization",
            "required": False,
            "type": "boolean",
            "default": False,
            "description": "Tell frontend whether backend expects authorization.",
        },
        {
            "name": "frontend_redirect_url",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Redirect URL for OAuth flows (if auth is enabled).",
        },
        {
            "name": "external_auth_callback_uri",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Redirect URI for the OIDC application.",
        },
        {
            "name": "external_auth_service_url",
            "required": False,
            "type": "string",
            "default": "http://localhost:8080",
            "description": "External authorization service URL for login initiation.",
        },
        {
            "name": "external_auth_provider",
            "required": False,
            "type": "string",
            "default": "",
            "description": "The external authentication provider.",
        },
        {
            "name": "ssl_keyfile",
            "required": False,
            "type": "string",
            "default": "",
            "description": "The file path to the SSL private key.",
        },
        {
            "name": "ssl_certfile",
            "required": False,
            "type": "string",
            "default": "",
            "description": "The file path to the SSL certificate.",
        },
        {
            "name": "ssl_keyfile_password",
            "required": False,
            "type": "string",
            "default": "",
            "description": "The passphrase for the SSL private key.",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the WebUIBackendApp.
        Most setup is handled by BaseGatewayApp.
        """
        log.debug(
            "%s Initializing WebUIBackendApp...",
            app_info.get("name", "WebUIBackendApp"),
        )
        super().__init__(app_info, **kwargs)


        log.debug("%s WebUIBackendApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> type[BaseGatewayComponent]:
        return WebUIBackendComponent