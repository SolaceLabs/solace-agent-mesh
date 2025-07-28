"""
Custom Solace AI Connector App class for the Test REST Gateway.
"""
from typing import Type
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from sam_rest_gateway.app import RestGatewayApp
from .component import TestRestGatewayComponent

# Module-level info dictionary required by SAC
info = {
    "class_name": "TestRestGatewayApp",
    "description": "App class for the Test REST Gateway used in integration testing.",
}

class TestRestGatewayApp(RestGatewayApp):
    """
    Custom App class for the Test REST Gateway.
    It extends the real RestGatewayApp but overrides the component class.
    """
    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the test-specific gateway component class for this app.
        """
        return TestRestGatewayComponent
