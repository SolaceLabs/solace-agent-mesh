"""
Custom Solace AI Connector App class for the Web UI Backend.
Defines configuration schema and programmatically creates the WebUIBackendComponent.
"""

import logging
from typing import Any, Dict, List

from ...gateway.http_sse.component import WebUIBackendComponent

from ...gateway.base.app import BaseGatewayApp
from ...gateway.base.component import BaseGatewayComponent

log = logging.getLogger(__name__)

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
            "name": "model",
            "required": False,
            "type": "dict",
            "default": None,
            "description": "The model to use for the WebUI gateway.",
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
        {
            "name": "frontend_server_url",
            "required": False,
            "type": "string",
            "default": "",
            "description": (
                "The WebUI Gateway's public URL for frontend API requests. "
                "If empty (default), the frontend uses relative URLs for same-origin requests. "
                "Only set this if the frontend is served from a different origin than the WebUI Gateway. "
                "Examples: "
                "  - Same-origin (default): '' (empty, uses relative URLs like /api/v1/...) "
                "  - Cross-origin: https://webui-gateway.example.com"
            ),
        },
        {
            "name": "session_service",
            "required": False,
            "type": "dict",
            "default": {"type": "memory"},
            "description": "Configuration for the Session Service.",
            "dict_schema": {
                "type": {
                    "type": "string",
                    "required": True,
                    "default": "memory",
                    "allowed": ["memory", "sql"],
                    "description": "The type of session service to use ('memory' or 'sql').",
                },
                "database_url": {
                    "type": "string",
                    "required": False,
                    "default": None,
                    "description": "Database URL for SQL session service. Required if type is 'sql'.",
                },
            },
        },
        {
            "name": "platform_service",
            "required": False,
            "type": "dict",
            "default": {},
            "description": "Configuration for connecting to the Platform Service (runs separately on port 8001).",
            "dict_schema": {
                "url": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": (
                        "Platform Service URL for frontend API routing to enterprise endpoints. "
                        "Frontend will call this URL for /api/v1/platform/* requests. "
                        "Examples: "
                        "  - Docker: http://platform-service:8001 "
                        "  - K8s: http://platform-service:8001 "
                        "  - Local: http://localhost:8001"
                    ),
                },
            },
        },
        {
            "name": "task_logging",
            "required": False,
            "type": "dict",
            "description": "Configuration for the A2A task logging service.",
            "dict_schema": {
                "enabled": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Enable/disable the task logging service.",
                },
                "log_status_updates": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Log intermediate TaskStatusUpdate events.",
                },
                "log_artifact_events": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Log TaskArtifactUpdate events.",
                },
                "log_file_parts": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Log FilePart content within events.",
                },
                "max_file_part_size_bytes": {
                    "type": "integer",
                    "required": False,
                    "default": 102400,  # 100KB
                    "description": "Maximum size of a FilePart's content to store in the database. Larger files will have their content stripped.",
                },
            },
        },
        {
            "name": "feedback_publishing",
            "required": False,
            "type": "dict",
            "description": "Configuration for publishing user feedback to the message broker.",
            "dict_schema": {
                "enabled": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Enable/disable feedback publishing.",
                },
                "topic": {
                    "type": "string",
                    "required": False,
                    "default": "sam/feedback/v1",
                    "description": "The Solace topic to publish feedback events to.",
                },
                "include_task_info": {
                    "type": "string",
                    "required": False,
                    "default": "none",
                    "enum": ["none", "summary", "stim"],
                    "description": "Level of task detail to include in the feedback event.",
                },
                "max_payload_size_bytes": {
                    "type": "integer",
                    "required": False,
                    "default": 9000000,
                    "description": "Max payload size in bytes before 'stim' falls back to 'summary'.",
                },
            },
        },
        {
            "name": "data_retention",
            "required": False,
            "type": "dict",
            "description": "Configuration for automatic cleanup of old data.",
            "dict_schema": {
                "enabled": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Enable/disable automatic data cleanup.",
                },
                "task_retention_days": {
                    "type": "integer",
                    "required": False,
                    "default": 90,
                    "description": "Number of days to retain task and task_event records. Minimum: 1 day.",
                },
                "feedback_retention_days": {
                    "type": "integer",
                    "required": False,
                    "default": 90,
                    "description": "Number of days to retain feedback records. Minimum: 1 day.",
                },
                "cleanup_interval_hours": {
                    "type": "integer",
                    "required": False,
                    "default": 24,
                    "description": "How often to run the cleanup job (in hours). Minimum: 1 hour.",
                },
                "batch_size": {
                    "type": "integer",
                    "required": False,
                    "default": 1000,
                    "description": "Number of records to delete per batch to avoid long-running transactions. Range: 1-10000.",
                },
            },
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

    def get_component(self) -> WebUIBackendComponent | None:
        """
        Retrieves the running WebUIBackendComponent instance from the app's flow.
        """
        if self.flows and self.flows[0].component_groups:
            for group in self.flows[0].component_groups:
                for component_wrapper in group:
                    component = (
                        component_wrapper.component
                        if hasattr(component_wrapper, "component")
                        else component_wrapper
                    )
                    if isinstance(component, WebUIBackendComponent):
                        return component
        return None
