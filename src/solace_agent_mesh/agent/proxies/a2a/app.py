"""
Concrete App class for the A2A-over-HTTPS proxy.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Type

from ..base.app import BaseProxyApp
from ..base.component import BaseProxyComponent
from .component import A2AProxyComponent

info = {
    "class_name": "A2AProxyApp",
}


class A2AProxyApp(BaseProxyApp):
    """
    Concrete App class for the A2A-over-HTTPS proxy.

    Extends the BaseProxyApp to add specific configuration validation for
    A2A agents (e.g., URL, authentication).
    """

    # Deep copy the base schema to avoid modifying it in place
    app_schema = copy.deepcopy(BaseProxyApp.app_schema)

    # Find the proxied_agents definition in the copied schema
    proxied_agents_schema = next(
        (
            param
            for param in app_schema["config_parameters"]
            if param["name"] == "proxied_agents"
        ),
        None,
    )

    if proxied_agents_schema:
        # Add A2A-specific properties to the items schema
        proxied_agents_schema["items"]["properties"]["url"] = {
            "type": "string",
            "required": True,
            "description": "The base URL of the downstream A2A agent's HTTP endpoint.",
        }
        proxied_agents_schema["items"]["properties"]["authentication"] = {
            "type": "object",
            "required": False,
            "description": "Authentication details for the downstream agent.",
            "properties": {
                "type": {
                    "type": "string",
                    "required": False,
                    "enum": ["static_bearer", "static_apikey", "oauth2_client_credentials"],
                    "description": "Authentication type. If not specified, inferred from 'scheme' for backward compatibility.",
                },
                "scheme": {
                    "type": "string",
                    "required": False,
                    "description": "(Legacy) The authentication scheme (e.g., 'bearer', 'apikey'). Use 'type' field instead.",
                },
                "token": {
                    "type": "string",
                    "required": False,
                    "description": "The authentication token or API key (for static_bearer and static_apikey types).",
                },
                "token_url": {
                    "type": "string",
                    "required": False,
                    "description": "OAuth 2.0 token endpoint URL (required for oauth2_client_credentials type).",
                },
                "client_id": {
                    "type": "string",
                    "required": False,
                    "description": "OAuth 2.0 client identifier (required for oauth2_client_credentials type).",
                },
                "client_secret": {
                    "type": "string",
                    "required": False,
                    "description": "OAuth 2.0 client secret (required for oauth2_client_credentials type).",
                },
                "scope": {
                    "type": "string",
                    "required": False,
                    "description": "OAuth 2.0 scope as a space-separated string (optional for oauth2_client_credentials type).",
                },
                "token_cache_duration_seconds": {
                    "type": "integer",
                    "required": False,
                    "default": 3300,
                    "description": "How long to cache OAuth 2.0 tokens before refresh, in seconds (default: 3300 = 55 minutes).",
                },
            },
        }
        proxied_agents_schema["items"]["properties"]["request_timeout_seconds"] = {
            "type": "integer",
            "required": False,
            "description": "Optional timeout override for this specific agent.",
        }

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        app_info["class_name"] = "A2AProxyApp"
        super().__init__(app_info, **kwargs)

    def _get_component_class(self) -> Type[BaseProxyComponent]:
        """
        Returns the concrete A2AProxyComponent class.
        """
        return A2AProxyComponent
