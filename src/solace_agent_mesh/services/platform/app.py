"""
Platform Service App class for Solace Agent Mesh.
Defines configuration schema and creates the PlatformServiceComponent.
"""

import logging
from typing import Any, Dict, List

from ...common.app_base import SamAppBase

from .component import PlatformServiceComponent
from ...common.a2a import get_discovery_subscription_topic

log = logging.getLogger(__name__)

info = {
    "class_name": "PlatformServiceApp",
    "description": "Platform Service for configuration management",
}


class PlatformServiceApp(SamAppBase):
    """
    Platform Service App.

    Provides REST API for platform configuration management.
    - CRUD operations with OAuth2 token validation
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "namespace",
            "required": True,
            "type": "string",
            "description": "Namespace for service configuration.",
        },
        {
            "name": "database_url",
            "required": True,
            "type": "string",
            "description": "Platform database connection string (PostgreSQL, MySQL, or SQLite).",
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
            "default": 8001,
            "description": "Port for the embedded FastAPI server.",
        },
        {
            "name": "fastapi_https_port",
            "required": False,
            "type": "integer",
            "default": 8444,
            "description": "Port for the embedded FastAPI server when SSL is enabled.",
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
            "name": "cors_allowed_origins",
            "required": False,
            "type": "list",
            "default": ["*"],
            "description": "List of allowed origins for CORS requests.",
        },
        {
            "name": "cors_allowed_origin_regex",
            "required": False,
            "type": "string",
            "default": "",
            "description": "Regex pattern for allowed CORS origins. Useful for local development with dynamic ports (e.g., 'https?://(localhost|127\\.0\\.0\\.1):\\\\d+').",
        },
        {
            "name": "external_auth_service_url",
            "required": False,
            "type": "string",
            "description": "OAuth2 authentication service base URL for token validation.",
        },
        {
            "name": "external_auth_provider",
            "required": False,
            "type": "string",
            "default": "",
            "description": "The external authentication provider.",
        },
        {
            "name": "frontend_use_authorization",
            "required": False,
            "type": "boolean",
            "default": False,
            "description": "Enable OAuth2 token validation. When true, all API requests must include valid OAuth2 bearer tokens.",
        },
        {
            "name": "max_message_size_bytes",
            "required": False,
            "type": "integer",
            "default": 10000000,
            "description": "Maximum message size in bytes for A2A messages (default: 10MB).",
        },
        {
            "name": "deployment_timeout_minutes",
            "required": False,
            "type": "integer",
            "default": 5,
            "description": "Timeout for agent deployments (default: 5 minutes).",
        },
        {
            "name": "heartbeat_timeout_seconds",
            "required": False,
            "type": "integer",
            "default": 90,
            "description": "Deployer heartbeat timeout in seconds (default: 90 seconds).",
        },
        {
            "name": "deployment_check_interval_seconds",
            "required": False,
            "type": "integer",
            "default": 60,
            "description": "Interval for checking deployment status in seconds (default: 60 seconds).",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initialize the PlatformServiceApp.
        Programmatically creates the component and configures broker before calling parent App.__init__().
        """
        log.debug(
            "%s Initializing PlatformServiceApp...",
            app_info.get("name", "PlatformServiceApp"),
        )

        modified_app_info = app_info.copy()
        app_config = modified_app_info.get("app_config", {})

        # Get namespace from config
        namespace = app_config.get("namespace", "")
        if not namespace:
            raise ValueError("Namespace is required in app_config for PlatformServiceApp")

        # Create subscriptions for agent and gateway discovery
        subscriptions = [
            {"topic": get_discovery_subscription_topic(namespace)},
        ]

        # Create component definition with subscriptions
        # (SAC framework looks for subscriptions in component definition for simplified apps)
        component_definition = {
            "name": f"{app_info.get('name', 'platform_service')}_component",
            "component_class": PlatformServiceComponent,
            "component_config": {"app_config": app_config},
            "subscriptions": subscriptions,
        }

        modified_app_info["components"] = [component_definition]

        # Configure broker connection
        broker_config = modified_app_info.setdefault("broker", {})
        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True

        log.info(
            "Configured broker for Platform Service with namespace: %s and %d subscription(s): %s",
            namespace,
            len(subscriptions),
            subscriptions
        )

        super().__init__(modified_app_info, **kwargs)
        log.debug("%s PlatformServiceApp initialization complete.", self.name)

    def get_component(self) -> PlatformServiceComponent | None:
        """
        Retrieve the running PlatformServiceComponent instance from the app's flow.

        Returns:
            PlatformServiceComponent instance if found, None otherwise.
        """
        if self.flows and self.flows[0].component_groups:
            for group in self.flows[0].component_groups:
                for component_wrapper in group:
                    component = (
                        component_wrapper.component
                        if hasattr(component_wrapper, "component")
                        else component_wrapper
                    )
                    if isinstance(component, PlatformServiceComponent):
                        return component
        return None
