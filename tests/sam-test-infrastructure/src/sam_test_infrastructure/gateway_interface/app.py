"""
Custom Solace AI Connector App class for the GDK-based Test Gateway.
Defines configuration schema (if any specific needed) and programmatically
creates the TestGatewayComponent.
"""
import logging
from typing import Any, Dict, List, Type

from pydantic import ValidationError

from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import BaseGatewayComponent

from .component import TestGatewayComponent

log = logging.getLogger(__name__)

info = {
    "class_name": "TestGatewayApp",
    "description": "App class for the GDK-based Test Gateway used in integration testing.",
}


class TestGatewayApp(BaseGatewayApp):
    """
    Custom App class for the GDK-based Test Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Specifies TestGatewayComponent as its operational component.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = []

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the TestGatewayApp.
        Most setup is handled by BaseGatewayApp.
        """
        log.debug(
            "%s Initializing TestGatewayApp...",
            app_info.get("name", "TestGatewayApp"),
        )

        app_info.setdefault("broker", {})
        app_info["broker"]["dev_mode"] = True

        super().__init__(app_info=app_info, **kwargs)
        log.debug("%s TestGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this app.
        """
        return TestGatewayComponent
