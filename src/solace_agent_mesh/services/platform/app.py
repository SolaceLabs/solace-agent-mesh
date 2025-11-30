"""
Platform Service App class for Solace Agent Mesh.
Defines configuration schema and creates the PlatformServiceComponent.
"""

import logging
from typing import Any, Dict, List

from solace_ai_connector.flow.app import App

from .component import PlatformServiceComponent

log = logging.getLogger(__name__)

info = {
    "class_name": "PlatformServiceApp",
    "description": "Platform Service for configuration management",
}


class PlatformServiceApp(App):
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
            "name": "cors_allowed_origins",
            "required": False,
            "type": "list",
            "default": ["*"],
            "description": "List of allowed origins for CORS requests.",
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
            "default": "azure",
            "description": "OAuth2 provider name (e.g., 'azure', 'google', 'okta').",
        },
        {
            "name": "use_authorization",
            "required": False,
            "type": "boolean",
            "default": True,
            "description": "Enable OAuth2 token validation. Set to false for development mode.",
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initialize the PlatformServiceApp.
        Most setup is handled by the base App class.
        """
        log.debug(
            "%s Initializing PlatformServiceApp...",
            app_info.get("name", "PlatformServiceApp"),
        )
        super().__init__(app_info, **kwargs)
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
