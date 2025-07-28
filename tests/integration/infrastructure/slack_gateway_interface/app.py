"""
Custom Solace AI Connector App class for the Test Slack Gateway.
"""
from typing import Type
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from sam_slack.app import SlackGatewayApp
from .component import TestSlackGatewayComponent

# Module-level info dictionary required by SAC
info = {
    "class_name": "TestSlackGatewayApp",
    "description": "App class for the Test Slack Gateway used in integration testing.",
}

class TestSlackGatewayApp(SlackGatewayApp):
    """
    Custom App class for the Test Slack Gateway.
    It extends the real SlackGatewayApp but overrides the component class.
    """
    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the test-specific gateway component class for this app.
        """
        return TestSlackGatewayComponent
