"""
Custom Solace AI Connector App class for the Test Webhook Gateway.
"""
from typing import Type
from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent
from sam_webhook_gateway.app import WebhookGatewayApp
from .component import TestWebhookGatewayComponent

# Module-level info dictionary required by SAC
info = {
    "class_name": "TestWebhookGatewayApp",
    "description": "App class for the Test Webhook Gateway used in integration testing.",
}

class TestWebhookGatewayApp(WebhookGatewayApp):
    """
    Custom App class for the Test Webhook Gateway.
    It extends the real WebhookGatewayApp but overrides the component class.
    """
    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the test-specific gateway component class for this app.
        """
        return TestWebhookGatewayComponent
