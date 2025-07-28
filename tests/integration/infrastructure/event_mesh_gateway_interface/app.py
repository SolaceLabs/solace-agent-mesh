"""
Custom Solace AI Connector App class for the Test Event Mesh Gateway.
"""
from typing import Type
from sam_event_mesh_gateway.app import EventMeshGatewayApp
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from .component import TestEventMeshGatewayComponent

# Module-level info dictionary required by SAC
info = {
    "class_name": "TestEventMeshGatewayApp",
    "description": "App class for the Test Event Mesh Gateway used in integration testing.",
}

class TestEventMeshGatewayApp(EventMeshGatewayApp):
    """
    Custom App class for the Test Event Mesh Gateway.
    It extends the real EventMeshGatewayApp but overrides the component class.
    """
    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the test-specific gateway component class for this app.
        """
        return TestEventMeshGatewayComponent
