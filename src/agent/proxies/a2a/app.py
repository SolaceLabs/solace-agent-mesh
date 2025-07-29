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
                "scheme": {
                    "type": "string",
                    "required": True,
                    "description": "The authentication scheme (e.g., 'bearer').",
                },
                "token": {
                    "type": "string",
                    "required": True,
                    "description": "The authentication token or API key.",
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
