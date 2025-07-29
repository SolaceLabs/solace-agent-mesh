"""
Custom Solace AI Connector App class for the Test Web Gateway.
"""

from typing import Type
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from src.solace_agent_mesh.gateway.http_sse.app import WebUIBackendApp
from .component import TestWebGatewayComponent

# Module-level info dictionary required by SAC
info = {
    "class_name": "TestWebGatewayApp",
    "description": "App class for the Test Web Gateway used in integration testing.",
}


class TestWebGatewayApp(WebUIBackendApp):
    """
    Custom App class for the Test Web Gateway.
    It extends the real WebUIBackendApp but overrides the component class.
    """

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the test-specific gateway component class for this app.
        """
        return TestWebGatewayComponent
